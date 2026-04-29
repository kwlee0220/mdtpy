"""
mdtpy.submodel 모듈의 클래스에 대한 단위 테스트.

대상:
    - SubmodelService               : 속성/타입 분류, read/write,
                                      submodel_element_url 검증, invoke 동기/비동기,
                                      get_operation_async_result, element_reference
    - SubmodelServiceCollection     : Data/InformationModel/Simulation/AI/TimeSeries
                                      서브모델별 분기, Operation descriptor 미존재 에러,
                                      Mapping 인터페이스, get_by_id, find_by_semantic_id
    - SubmodelElementCollection     : 경로 캐시, __iter__/__len__/__contains__가 캐시 공유,
                                      __setitem__ write→add 폴백 + 캐시 무효화,
                                      __delitem__/refresh의 캐시 무효화,
                                      get_value/update_value/get_attachment 위임

HTTP는 fa3st.call_* 또는 element_reference 단위로 mock한다.
"""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest

from basyx.aas import model

from mdtpy.aas_misc import (
    Endpoint,
    OperationHandle,
    OperationResult,
    ProtocolInformation,
)
from mdtpy.descriptor import (
    MDTOperationDescriptor,
    MDTSubmodelDescriptor,
    SEMANTIC_ID_AI_SUBMODEL,
    SEMANTIC_ID_DATA_SUBMODEL,
    SEMANTIC_ID_INFOR_MODEL_SUBMODEL,
    SEMANTIC_ID_SIMULATION_SUBMODEL,
    SEMANTIC_ID_TIME_SERIES_SUBMODEL,
)
from mdtpy.exceptions import InvalidResourceStateError, ResourceNotFoundError
from mdtpy.reference import DefaultElementReference, ElementReference
from mdtpy.submodel import (
    SubmodelElementCollection,
    SubmodelService,
    SubmodelServiceCollection,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_sm_desc(
    id: str = "sm1",
    id_short: str = "Data",
    semantic_id: str = SEMANTIC_ID_DATA_SUBMODEL,
    endpoint: str | None = "http://srv/sm1",
) -> MDTSubmodelDescriptor:
    return MDTSubmodelDescriptor(
        id=id,
        id_short=id_short,
        semantic_id=semantic_id,
        endpoint=endpoint,
    )


def make_op_desc(id: str = "op", input_args=None, output_args=None) -> MDTOperationDescriptor:
    return MDTOperationDescriptor(
        id=id,
        operation_type="sync",
        input_arguments=input_args or [],
        output_arguments=output_args or [],
    )


def make_instance_mock(id: str = "i1", op_desc_dict=None) -> MagicMock:
    """`SubmodelServiceCollection.__init__`이 사용하는 instance 자리의 mock."""
    inst = MagicMock()
    inst.id = id
    inst.operation_descriptors = op_desc_dict if op_desc_dict is not None else {}
    return inst


# --------------------------------------------------------------------------- #
# SubmodelService — 속성 / 타입 분류
# --------------------------------------------------------------------------- #

class TestSubmodelServiceProperties:
    def test_basic_property_passthrough(self):
        desc = make_sm_desc(
            id="sm1",
            id_short="Data",
            semantic_id="https://x/y",
            endpoint="http://srv/sm",
        )
        svc = SubmodelService("inst-1", desc)
        assert svc.instance_id == "inst-1"
        assert svc.id == "sm1"
        assert svc.id_short == "Data"
        assert svc.semantic_id_str == "https://x/y"
        assert svc.service_endpoint == "http://srv/sm"

    def test_service_endpoint_returns_none_when_descriptor_endpoint_none(self):
        svc = SubmodelService("inst", make_sm_desc(endpoint=None))
        assert svc.service_endpoint is None

    def test_endpoint_wraps_protocol_info_with_http_v11(self):
        svc = SubmodelService("inst", make_sm_desc(endpoint="http://srv/x"))
        ep = svc.endpoint
        assert isinstance(ep, Endpoint)
        assert ep.interface == "SUBMODEL"
        assert isinstance(ep.protocolInformation, ProtocolInformation)
        assert ep.protocolInformation.href == "http://srv/x"
        assert ep.protocolInformation.endpointProtocol == "HTTP"
        assert ep.protocolInformation.endpointProtocolVersion == "1.1"

    @pytest.mark.parametrize(
        "semantic_id, predicate, expected",
        [
            (SEMANTIC_ID_INFOR_MODEL_SUBMODEL, "is_information_model", True),
            (SEMANTIC_ID_DATA_SUBMODEL, "is_data", True),
            (SEMANTIC_ID_SIMULATION_SUBMODEL, "is_simulation", True),
            (SEMANTIC_ID_AI_SUBMODEL, "is_ai", True),
            (SEMANTIC_ID_TIME_SERIES_SUBMODEL, "is_time_series", True),
            ("https://other/semantic", "is_data", False),
            ("https://other/semantic", "is_simulation", False),
        ],
    )
    def test_type_predicates(self, semantic_id, predicate, expected):
        svc = SubmodelService("i", make_sm_desc(semantic_id=semantic_id))
        assert getattr(svc, predicate)() is expected


# --------------------------------------------------------------------------- #
# SubmodelService — submodel_element_url
# --------------------------------------------------------------------------- #

class TestSubmodelElementUrl:
    def test_returns_prefix_when_path_empty(self):
        svc = SubmodelService("i", make_sm_desc(endpoint="http://srv/sm"))
        assert svc.submodel_element_url("") == "http://srv/sm/submodel-elements"

    def test_appends_quoted_path(self):
        svc = SubmodelService("i", make_sm_desc(endpoint="http://srv/sm"))
        url = svc.submodel_element_url("Path with space")
        # 공백은 %20으로 인코딩되어야 한다
        assert "Path%20with%20space" in url
        assert "Path with space" not in url

    def test_raises_when_endpoint_not_set(self):
        svc = SubmodelService("i", make_sm_desc(endpoint=None))
        with pytest.raises(InvalidResourceStateError):
            svc.submodel_element_url("anything")


# --------------------------------------------------------------------------- #
# SubmodelService — read / write (fa3st 호출 mock)
# --------------------------------------------------------------------------- #

class TestSubmodelServiceReadWrite:
    @patch("mdtpy.submodel.fa3st.call_get")
    def test_read_calls_fa3st_with_endpoint(self, mock_get):
        mock_get.return_value = MagicMock(spec=model.Submodel)
        svc = SubmodelService("i", make_sm_desc(endpoint="http://srv/sm"))
        svc.read()
        called_url = mock_get.call_args[0][0]
        assert called_url == "http://srv/sm"

    def test_read_raises_when_endpoint_missing(self):
        svc = SubmodelService("i", make_sm_desc(endpoint=None))
        with pytest.raises(InvalidResourceStateError):
            svc.read()

    @patch("mdtpy.submodel.fa3st.call_put")
    @patch("mdtpy.submodel.basyx_serde.to_json", return_value='{"x":1}')
    def test_write_serializes_and_puts(self, _mock_to_json, mock_put):
        svc = SubmodelService("i", make_sm_desc(endpoint="http://srv/sm"))
        sm = MagicMock(spec=model.Submodel)
        svc.write(sm)
        called_url = mock_put.call_args[0][0]
        called_body = mock_put.call_args[0][1]
        assert called_url == "http://srv/sm"
        assert called_body == '{"x":1}'

    def test_write_raises_when_endpoint_missing(self):
        svc = SubmodelService("i", make_sm_desc(endpoint=None))
        with pytest.raises(InvalidResourceStateError):
            svc.write(MagicMock(spec=model.Submodel))


# --------------------------------------------------------------------------- #
# SubmodelService — invoke (sync/async) / get_operation_async_result
# --------------------------------------------------------------------------- #

class TestSubmodelServiceInvocations:
    @patch("mdtpy.submodel.fa3st.call_post")
    def test_invoke_operation_sync_posts_to_invoke_endpoint(self, mock_post):
        mock_post.return_value = MagicMock(spec=OperationResult)
        svc = SubmodelService("i", make_sm_desc(endpoint="http://srv/sm"))
        svc.invoke_operation_sync(
            "MyOp", [], [], timeout=datetime.timedelta(seconds=1)
        )
        called_url = mock_post.call_args[0][0]
        assert called_url == "http://srv/sm/submodel-elements/MyOp/invoke"
        # deserializer는 OperationResult.from_json
        assert mock_post.call_args.kwargs["deserializer"] == OperationResult.from_json

    @patch("mdtpy.submodel.fa3st.call_post")
    def test_invoke_operation_async_uses_async_query(self, mock_post):
        mock_post.return_value = MagicMock(spec=OperationHandle)
        svc = SubmodelService("i", make_sm_desc(endpoint="http://srv/sm"))
        svc.invoke_operation_async(
            "MyOp", [], [], timeout=datetime.timedelta(seconds=1)
        )
        called_url = mock_post.call_args[0][0]
        assert called_url == "http://srv/sm/submodel-elements/MyOp/invoke?async=true"
        assert mock_post.call_args.kwargs["deserializer"] == OperationHandle.from_json

    @patch("mdtpy.submodel.fa3st.call_get")
    def test_get_operation_async_result_uses_handle_id_in_path(self, mock_get):
        mock_get.return_value = MagicMock(spec=OperationResult)
        svc = SubmodelService("i", make_sm_desc(endpoint="http://srv/sm"))
        handle = OperationHandle(handle_id="h-42")
        svc.get_operation_async_result("MyOp", handle)
        called_url = mock_get.call_args[0][0]
        assert called_url == "http://srv/sm/submodel-elements/MyOp/operation-results/h-42"
        assert mock_get.call_args.kwargs["deserializer"] == OperationResult.from_json


# --------------------------------------------------------------------------- #
# SubmodelService — element_reference / submodel_elements
# --------------------------------------------------------------------------- #

class TestSubmodelServiceReferences:
    def test_element_reference_builds_correct_ref_string_and_endpoint(self):
        svc = SubmodelService(
            "inst-1", make_sm_desc(id_short="Data", endpoint="http://srv/sm")
        )
        ref = svc.element_reference("Path.x")
        assert isinstance(ref, DefaultElementReference)
        assert ref.ref_string == "inst-1:Data:Path.x"
        assert ref.endpoint == "http://srv/sm/submodel-elements/Path.x"

    def test_submodel_elements_property_returns_collection(self):
        svc = SubmodelService("i", make_sm_desc(endpoint="http://srv/sm"))
        assert isinstance(svc.submodel_elements, SubmodelElementCollection)


# --------------------------------------------------------------------------- #
# SubmodelServiceCollection
# --------------------------------------------------------------------------- #

class TestSubmodelServiceCollection:
    def test_data_and_information_model_use_plain_submodel_service(self):
        sm_descs = {
            "Data": make_sm_desc(id="sm-data", id_short="Data",
                                 semantic_id=SEMANTIC_ID_DATA_SUBMODEL),
            "Info": make_sm_desc(id="sm-info", id_short="Info",
                                 semantic_id=SEMANTIC_ID_INFOR_MODEL_SUBMODEL),
        }
        coll = SubmodelServiceCollection(make_instance_mock(), sm_descs)
        assert len(coll) == 2
        assert isinstance(coll["Data"], SubmodelService)
        assert isinstance(coll["Info"], SubmodelService)

    def test_simulation_uses_operation_submodel_service(self):
        op_dict = {"Sim": make_op_desc(id="op-sim")}
        sm_descs = {
            "Sim": make_sm_desc(id="sm-sim", id_short="Sim",
                                semantic_id=SEMANTIC_ID_SIMULATION_SUBMODEL),
        }
        # AASOperationService 생성자는 HTTP를 일으키므로 mock 처리
        with patch("mdtpy.operation.AASOperationService"):
            coll = SubmodelServiceCollection(
                make_instance_mock(op_desc_dict=op_dict), sm_descs,
            )
        from mdtpy.operation import OperationSubmodelService
        assert isinstance(coll["Sim"], OperationSubmodelService)

    def test_simulation_without_operation_descriptor_raises(self):
        """Simulation/AI 서브모델이 있는데 매칭되는 operation descriptor가 없으면
        ResourceNotFoundError를 발생시켜야 한다."""
        sm_descs = {
            "Sim": make_sm_desc(id="sm-sim", id_short="Sim",
                                semantic_id=SEMANTIC_ID_SIMULATION_SUBMODEL),
        }
        with pytest.raises(ResourceNotFoundError):
            SubmodelServiceCollection(make_instance_mock(op_desc_dict={}), sm_descs)

    def test_time_series_uses_time_series_service(self):
        sm_descs = {
            "TS": make_sm_desc(id="sm-ts", id_short="TS",
                               semantic_id=SEMANTIC_ID_TIME_SERIES_SUBMODEL),
        }
        coll = SubmodelServiceCollection(make_instance_mock(), sm_descs)
        from mdtpy.timeseries import TimeSeriesService
        assert isinstance(coll["TS"], TimeSeriesService)

    def test_unknown_semantic_id_is_silently_skipped(self):
        """현 구현은 알 수 없는 semantic_id를 그냥 건너뛴다 (회귀 가드)."""
        sm_descs = {
            "Other": make_sm_desc(semantic_id="https://unknown/sm"),
        }
        coll = SubmodelServiceCollection(make_instance_mock(), sm_descs)
        assert len(coll) == 0

    def test_getitem_unknown_id_short_raises_resource_not_found(self):
        coll = SubmodelServiceCollection(make_instance_mock(), {})
        with pytest.raises(ResourceNotFoundError):
            _ = coll["missing"]

    def test_iter_yields_id_shorts(self):
        sm_descs = {
            "Data": make_sm_desc(id_short="Data"),
            "Info": make_sm_desc(id_short="Info",
                                 semantic_id=SEMANTIC_ID_INFOR_MODEL_SUBMODEL),
        }
        coll = SubmodelServiceCollection(make_instance_mock(), sm_descs)
        assert set(iter(coll)) == {"Data", "Info"}

    def test_contains_uses_id_short(self):
        sm_descs = {"Data": make_sm_desc(id_short="Data")}
        coll = SubmodelServiceCollection(make_instance_mock(), sm_descs)
        assert "Data" in coll
        assert "Other" not in coll

    def test_get_by_id_returns_matching_service(self):
        sm_descs = {
            "Data": make_sm_desc(id="sm-data", id_short="Data"),
            "Info": make_sm_desc(id="sm-info", id_short="Info",
                                 semantic_id=SEMANTIC_ID_INFOR_MODEL_SUBMODEL),
        }
        coll = SubmodelServiceCollection(make_instance_mock(), sm_descs)
        svc = coll.get_by_id("sm-info")
        assert svc.id == "sm-info"
        assert svc.id_short == "Info"

    def test_get_by_id_missing_raises_resource_not_found(self):
        coll = SubmodelServiceCollection(make_instance_mock(), {})
        with pytest.raises(ResourceNotFoundError):
            coll.get_by_id("missing")

    def test_find_by_semantic_id_filters_collection(self):
        sm_descs = {
            "D1": make_sm_desc(id="d1", id_short="D1",
                               semantic_id=SEMANTIC_ID_DATA_SUBMODEL),
            "D2": make_sm_desc(id="d2", id_short="D2",
                               semantic_id=SEMANTIC_ID_DATA_SUBMODEL),
            "I1": make_sm_desc(id="i1", id_short="I1",
                               semantic_id=SEMANTIC_ID_INFOR_MODEL_SUBMODEL),
        }
        coll = SubmodelServiceCollection(make_instance_mock(), sm_descs)
        matches = coll.find_by_semantic_id(SEMANTIC_ID_DATA_SUBMODEL)
        assert {svc.id_short for svc in matches} == {"D1", "D2"}


# --------------------------------------------------------------------------- #
# SubmodelElementCollection
# --------------------------------------------------------------------------- #

class TestSubmodelElementCollection:
    def _make_coll(self):
        svc = SubmodelService(
            "inst-1", make_sm_desc(id_short="Data", endpoint="http://srv/sm")
        )
        return SubmodelElementCollection(svc), svc

    # element_reference --------------------------------------------------- #

    def test_element_reference_builds_endpoint_for_path(self):
        coll, _ = self._make_coll()
        ref = coll.element_reference("foo.bar")
        assert ref.ref_string == "inst-1:Data:foo.bar"
        assert ref.endpoint == "http://srv/sm/submodel-elements/foo.bar"

    # __iter__/__len__/__contains__ + cache ------------------------------- #

    def test_iter_returns_pathes_from_root_reference(self):
        coll, _ = self._make_coll()
        root_ref = MagicMock()
        root_ref.pathes.return_value = ["a", "b", "c"]
        with patch.object(coll, "element_reference", return_value=root_ref):
            assert list(coll) == ["a", "b", "c"]
        # 처음 호출이므로 한 번만 fetch
        root_ref.pathes.assert_called_once()

    def test_len_uses_same_cache_as_iter(self):
        coll, _ = self._make_coll()
        root_ref = MagicMock()
        root_ref.pathes.return_value = ["a", "b"]
        with patch.object(coll, "element_reference", return_value=root_ref):
            list(coll)         # 캐시 채움
            assert len(coll) == 2  # 캐시에서 가져옴
        # 두 번 호출됐어도 pathes()는 단 한 번만 fetch되어야 한다
        root_ref.pathes.assert_called_once()

    def test_contains_uses_cache_not_http(self):
        coll, _ = self._make_coll()
        root_ref = MagicMock()
        root_ref.pathes.return_value = ["a", "b"]
        with patch.object(coll, "element_reference", return_value=root_ref):
            list(coll)  # 캐시 채움
            assert ("a" in coll) is True
            assert ("z" in coll) is False
        # contains 두 번 호출에도 pathes()는 1회
        root_ref.pathes.assert_called_once()

    def test_refresh_invalidates_cache(self):
        coll, _ = self._make_coll()
        root_ref = MagicMock()
        root_ref.pathes.side_effect = [["a"], ["a", "b"]]
        with patch.object(coll, "element_reference", return_value=root_ref):
            assert list(coll) == ["a"]
            coll.refresh()
            assert list(coll) == ["a", "b"]
        assert root_ref.pathes.call_count == 2

    # __getitem__ --------------------------------------------------------- #

    def test_getitem_calls_read_on_element_reference(self):
        coll, _ = self._make_coll()
        ref = MagicMock()
        ref.read.return_value = "the-element"
        with patch.object(coll, "element_reference", return_value=ref) as m_er:
            assert coll["x.y"] == "the-element"
            m_er.assert_called_once_with("x.y")

    # __setitem__ --------------------------------------------------------- #

    def test_setitem_writes_when_path_exists(self):
        coll, _ = self._make_coll()
        ref = MagicMock()
        ref.write.return_value = None
        with patch.object(coll, "element_reference", return_value=ref):
            coll["x"] = MagicMock(spec=model.SubmodelElement)
        ref.write.assert_called_once()
        ref.add.assert_not_called()

    def test_setitem_falls_back_to_add_on_resource_not_found(self):
        coll, _ = self._make_coll()
        ref = MagicMock()
        ref.write.side_effect = ResourceNotFoundError("missing")
        ref.add.return_value = None
        with patch.object(coll, "element_reference", return_value=ref):
            coll["new-x"] = MagicMock(spec=model.SubmodelElement)
        ref.write.assert_called_once()
        ref.add.assert_called_once()

    def test_setitem_invalidates_cache(self):
        coll, _ = self._make_coll()
        # 캐시를 채운 뒤 setitem이 무효화하는지 확인
        root_ref = MagicMock()
        root_ref.pathes.side_effect = [["a"], ["a", "new"]]

        write_ref = MagicMock()
        write_ref.write.return_value = None

        # element_reference("") → root_ref, element_reference("new") → write_ref
        def by_path(path):
            return root_ref if path == "" else write_ref

        with patch.object(coll, "element_reference", side_effect=by_path):
            list(coll)  # 캐시 채움
            coll["new"] = MagicMock(spec=model.SubmodelElement)
            assert list(coll) == ["a", "new"]  # 다시 fetch되어야 한다
        assert root_ref.pathes.call_count == 2

    # __delitem__ --------------------------------------------------------- #

    def test_delitem_calls_remove_and_invalidates_cache(self):
        coll, _ = self._make_coll()
        root_ref = MagicMock()
        root_ref.pathes.side_effect = [["a", "b"], ["a"]]
        del_ref = MagicMock()

        def by_path(path):
            return root_ref if path == "" else del_ref

        with patch.object(coll, "element_reference", side_effect=by_path):
            list(coll)  # 캐시 채움
            del coll["b"]
            assert list(coll) == ["a"]
        del_ref.remove.assert_called_once()
        assert root_ref.pathes.call_count == 2

    # 단순 위임 메서드 ----------------------------------------------------- #

    def test_get_value_delegates_to_read_value(self):
        coll, _ = self._make_coll()
        ref = MagicMock()
        ref.read_value.return_value = 42
        with patch.object(coll, "element_reference", return_value=ref):
            assert coll.get_value("x") == 42
        ref.read_value.assert_called_once()

    def test_update_value_delegates_to_update_value(self):
        coll, _ = self._make_coll()
        ref = MagicMock()
        with patch.object(coll, "element_reference", return_value=ref):
            coll.update_value("x", 99)
        ref.update_value.assert_called_once_with(99)

    def test_get_attachment_delegates_to_get_attachment(self):
        coll, _ = self._make_coll()
        ref = MagicMock()
        ref.get_attachment.return_value = b"bytes"
        with patch.object(coll, "element_reference", return_value=ref):
            assert coll.get_attachment("x") == b"bytes"
        ref.get_attachment.assert_called_once()
