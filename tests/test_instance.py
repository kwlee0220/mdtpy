"""
mdtpy.instance 모듈의 클래스/함수에 대한 단위 테스트.

HTTP I/O는 unittest.mock으로 가짜 처리하여 외부 서버 의존성 없이 구동된다.
대상:
    - HTTP 헬퍼 (_get/_put/_post/_delete)
    - connect()
    - MDTInstanceManager (resolve_reference 포함)
    - MDTInstanceCollection (__bool__/__len__/__iter__/__contains__/
        __getitem__/find/add/__delitem__/remove/remove_all)
    - MDTInstance (속성, 상태 검증, start/stop, reload_descriptor, __repr__)
    - StatusPoller / InstanceStartPoller / InstanceStopPoller
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

import pytest

import mdtpy.instance as instance_mod
from mdtpy.instance import (
    MDTInstanceManager,
    MDTInstanceCollection,
    MDTInstance,
    InstanceStartPoller,
    InstanceStopPoller,
    StatusPoller,
    DEFAULT_TIMEOUT,
    _get,
    _put,
    _post,
    _delete,
    connect,
)
from mdtpy.descriptor import InstanceDescriptor, MDTInstanceStatus
from mdtpy.exceptions import (
    InvalidResourceStateError,
    ResourceNotFoundError,
    MDTException,
)


BASE_URL = "http://mgr.example.com"
INSTANCE_ID = "test-id"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_descriptor(
    id: str = INSTANCE_ID,
    status: MDTInstanceStatus = MDTInstanceStatus.RUNNING,
    **kw,
) -> InstanceDescriptor:
    """단위 테스트용 InstanceDescriptor 인스턴스를 만든다."""
    return InstanceDescriptor(
        id=id,
        status=status,
        aas_id=kw.get("aas_id", f"aas-{id}"),
        base_endpoint=kw.get("base_endpoint"),
        aas_id_short=kw.get("aas_id_short"),
        global_asset_id=kw.get("global_asset_id"),
        asset_type=kw.get("asset_type"),
        asset_kind=kw.get("asset_kind"),
    )


def make_response(status_code: int = 200) -> MagicMock:
    """requests.Response 흉내를 내는 MagicMock을 반환한다."""
    resp = MagicMock(name=f"Response({status_code})")
    resp.status_code = status_code
    resp.headers = {"content-type": "application/json"}
    resp.text = ""
    resp.json.return_value = {}
    return resp


# --------------------------------------------------------------------------- #
# HTTP 헬퍼 테스트
# --------------------------------------------------------------------------- #

class TestHttpHelpers:
    """`_get/_put/_post/_delete` 헬퍼는 timeout 미지정 시 DEFAULT_TIMEOUT을
    적용하고, 호출자가 명시한 timeout이 있으면 그대로 보존해야 한다."""

    @patch("mdtpy.instance.requests.get")
    def test_get_applies_default_timeout(self, mock_get):
        mock_get.return_value = make_response()
        _get("http://x")
        mock_get.assert_called_once_with("http://x", timeout=DEFAULT_TIMEOUT)

    @patch("mdtpy.instance.requests.get")
    def test_get_preserves_explicit_timeout(self, mock_get):
        mock_get.return_value = make_response()
        _get("http://x", timeout=5)
        mock_get.assert_called_once_with("http://x", timeout=5)

    @patch("mdtpy.instance.requests.put")
    def test_put_applies_default_timeout(self, mock_put):
        _put("http://x", data="d")
        mock_put.assert_called_once_with("http://x", data="d", timeout=DEFAULT_TIMEOUT)

    @patch("mdtpy.instance.requests.post")
    def test_post_preserves_explicit_timeout(self, mock_post):
        _post("http://x", timeout=60)
        mock_post.assert_called_once_with("http://x", timeout=60)

    @patch("mdtpy.instance.requests.delete")
    def test_delete_applies_default_timeout(self, mock_delete):
        _delete("http://x")
        mock_delete.assert_called_once_with("http://x", timeout=DEFAULT_TIMEOUT)


# --------------------------------------------------------------------------- #
# connect()
# --------------------------------------------------------------------------- #

class TestConnect:
    def test_returns_manager_and_sets_globals(self):
        mgr = connect("http://srv/mgr")
        assert isinstance(mgr, MDTInstanceManager)
        assert mgr.url == "http://srv/mgr"
        assert instance_mod.mdt_inst_url == "http://srv/mgr"
        assert instance_mod.mdt_manager is mgr


# --------------------------------------------------------------------------- #
# MDTInstanceManager
# --------------------------------------------------------------------------- #

class TestMDTInstanceManager:
    def test_url_returns_base_url(self):
        mgr = MDTInstanceManager(BASE_URL)
        assert mgr.url == BASE_URL

    def test_instances_is_collection(self):
        mgr = MDTInstanceManager(BASE_URL)
        assert isinstance(mgr.instances, MDTInstanceCollection)

    def test_resolve_reference_empty_string_raises(self):
        mgr = MDTInstanceManager(BASE_URL)
        with pytest.raises(ValueError, match="Invalid reference"):
            mgr.resolve_reference("")

    def test_resolve_reference_param_wrong_arity_raises(self):
        mgr = MDTInstanceManager(BASE_URL)
        with pytest.raises(ValueError, match="parameter reference"):
            mgr.resolve_reference("param:only-one-segment")
        with pytest.raises(ValueError, match="parameter reference"):
            mgr.resolve_reference("param:a:b:c")

    def test_resolve_reference_oparg_wrong_arity_raises(self):
        mgr = MDTInstanceManager(BASE_URL)
        with pytest.raises(ValueError, match="operation argument"):
            mgr.resolve_reference("oparg:i:o:in")  # 4 segments, need 5

    def test_resolve_reference_oparg_invalid_direction_raises(self):
        mgr = MDTInstanceManager(BASE_URL)
        # operations[parts[2]] 까지는 진행되므로 instances 체인을 mock한다.
        op = MagicMock()
        with patch.object(MDTInstanceManager, "instances", new_callable=MagicMock) as m_insts:
            m_insts.__getitem__.return_value.operations.__getitem__.return_value = op
            with pytest.raises(ValueError, match="operation argument"):
                mgr.resolve_reference("oparg:i:o:invalid:arg")

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_resolve_reference_default_path(self, mock_parse, mock_get):
        mock_get.return_value = make_response()
        mock_parse.return_value = "http://endpoint/x"
        mgr = MDTInstanceManager(BASE_URL)
        ref = mgr.resolve_reference("custom-ref")
        assert ref.ref_string == "custom-ref"
        assert ref.endpoint == "http://endpoint/x"
        # URL 쿼리 인자에 ref_string이 들어갔는지 확인
        called_url = mock_get.call_args[0][0]
        assert called_url.startswith(f"{BASE_URL}/references/$url?ref=")
        assert "custom-ref" in called_url


# --------------------------------------------------------------------------- #
# MDTInstanceCollection
# --------------------------------------------------------------------------- #

class TestMDTInstanceCollection:
    def setup_method(self):
        self.coll = MDTInstanceCollection(BASE_URL)
        self.url_prefix = f"{BASE_URL}/instances"

    # __bool__ -------------------------------------------------------------- #

    def test_bool_is_always_true_without_http(self):
        """`__bool__`은 HTTP를 일으키지 않고 True를 반환해야 한다."""
        with patch("mdtpy.instance.requests.get") as mock_get:
            assert bool(self.coll) is True
            mock_get.assert_not_called()

    # __len__ / __iter__ ---------------------------------------------------- #

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_list_response")
    def test_len_returns_count_from_list_endpoint(self, mock_parse_list, mock_get):
        mock_get.return_value = make_response()
        mock_parse_list.return_value = [make_descriptor(id="a"), make_descriptor(id="b")]
        assert len(self.coll) == 2
        mock_get.assert_called_once_with(self.url_prefix)

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_list_response")
    def test_iter_yields_mdt_instance_objects(self, mock_parse_list, mock_get):
        mock_get.return_value = make_response()
        descs = [make_descriptor(id="a"), make_descriptor(id="b")]
        mock_parse_list.return_value = descs
        items = list(self.coll)
        assert all(isinstance(x, MDTInstance) for x in items)
        assert [x.id for x in items] == ["a", "b"]

    # __contains__ ---------------------------------------------------------- #

    @patch("mdtpy.instance._get")
    def test_contains_returns_true_on_200(self, mock_get):
        mock_get.return_value = make_response(200)
        assert (INSTANCE_ID in self.coll) is True

    @patch("mdtpy.instance._get")
    def test_contains_returns_false_on_404(self, mock_get):
        mock_get.return_value = make_response(404)
        assert (INSTANCE_ID in self.coll) is False

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_none_response")
    def test_contains_raises_on_5xx(self, mock_parse_none, mock_get):
        mock_get.return_value = make_response(500)
        mock_parse_none.side_effect = MDTException("server error")
        with pytest.raises(MDTException):
            _ = "x" in self.coll

    @patch("mdtpy.instance._get")
    def test_contains_url_encodes_special_chars(self, mock_get):
        mock_get.return_value = make_response(200)
        weird_id = "a/b c#d?"
        _ = weird_id in self.coll
        called_url = mock_get.call_args[0][0]
        # 슬래시·공백·해시·물음표 모두 %로 인코딩되어야 한다
        assert "/" not in called_url[len(self.url_prefix) + 1:]
        assert " " not in called_url
        assert "#" not in called_url
        assert "?" not in called_url

    # __getitem__ ----------------------------------------------------------- #

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_getitem_returns_instance_on_200(self, mock_parse, mock_get):
        mock_get.return_value = make_response(200)
        mock_parse.return_value = make_descriptor(id="abc")
        inst = self.coll["abc"]
        assert isinstance(inst, MDTInstance)
        assert inst.id == "abc"

    @patch("mdtpy.instance._get")
    def test_getitem_404_raises_resource_not_found(self, mock_get):
        mock_get.return_value = make_response(404)
        with pytest.raises(ResourceNotFoundError):
            _ = self.coll["missing"]

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_getitem_5xx_raises_mdt_exception(self, mock_parse, mock_get):
        mock_get.return_value = make_response(500)
        mock_parse.side_effect = MDTException("server error")
        with pytest.raises(MDTException):
            _ = self.coll["x"]

    # find ------------------------------------------------------------------ #

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_list_response")
    def test_find_passes_filter_query(self, mock_parse_list, mock_get):
        mock_get.return_value = make_response()
        mock_parse_list.return_value = []
        list(self.coll.find("status=RUNNING"))
        # _get(url, params={'filter': '...'}) 형태로 호출되어야 한다
        kwargs = mock_get.call_args.kwargs
        assert kwargs == {"params": {"filter": "status=RUNNING"}}

    # __delitem__ / remove / remove_all ------------------------------------ #

    @patch("mdtpy.instance._delete")
    @patch("mdtpy.instance.parse_none_response")
    def test_delitem_calls_delete_with_encoded_id(self, mock_parse_none, mock_delete):
        mock_delete.return_value = make_response(200)
        del self.coll["a/b"]
        called_url = mock_delete.call_args[0][0]
        assert called_url.startswith(self.url_prefix + "/")
        assert "/" not in called_url[len(self.url_prefix) + 1:]
        assert mock_parse_none.called

    @patch("mdtpy.instance._delete")
    @patch("mdtpy.instance.parse_none_response")
    def test_remove_delegates_to_delitem(self, mock_parse_none, mock_delete):
        """`remove(x)`는 `del self[x]`와 동일하게 동작해야 한다."""
        mock_delete.return_value = make_response(200)
        self.coll.remove("foo")
        assert mock_delete.called

    @patch("mdtpy.instance._delete")
    @patch("mdtpy.instance.parse_none_response")
    def test_remove_all_deletes_collection_endpoint(self, mock_parse_none, mock_delete):
        mock_delete.return_value = make_response(200)
        self.coll.remove_all()
        mock_delete.assert_called_once_with(self.url_prefix)

    # add ------------------------------------------------------------------- #

    def test_add_raises_value_error_when_dir_missing(self, tmp_path):
        with pytest.raises(ValueError, match="not a directory"):
            self.coll.add("inst-id", 8080, str(tmp_path / "does-not-exist"))

    @patch("mdtpy.instance._post")
    @patch("mdtpy.instance.parse_response")
    def test_add_zips_directory_and_posts(self, mock_parse, mock_post, tmp_path):
        # 디렉토리 안에 파일 하나 만들어둔다
        src = tmp_path / "bundle"
        src.mkdir()
        (src / "manifest.txt").write_text("hello")

        mock_post.return_value = make_response(200)
        mock_parse.return_value = make_descriptor(id="new-inst")

        inst = self.coll.add("new-inst", 9000, str(src))

        assert isinstance(inst, MDTInstance)
        assert inst.id == "new-inst"
        # POST 호출 인자 검증
        args, kwargs = mock_post.call_args
        assert args[0] == self.url_prefix
        assert "files" in kwargs and "bundle" in kwargs["files"]
        assert kwargs["data"] == {"id": "new-inst", "port": "9000"}
        assert kwargs.get("timeout") == 60

    @patch("mdtpy.instance._post")
    @patch("mdtpy.instance.parse_response")
    def test_add_cleans_up_temp_zip(self, mock_parse, mock_post, tmp_path):
        src = tmp_path / "bundle"
        src.mkdir()
        mock_post.return_value = make_response(200)
        mock_parse.return_value = make_descriptor(id="new-inst")

        before = set(tmp_path.iterdir())
        self.coll.add("new-inst", 9000, str(src))
        after = set(tmp_path.iterdir())
        # 임시 디렉토리(TemporaryDirectory)가 자동 정리되어 잔여 zip 파일이 남지 않는다
        assert after == before


# --------------------------------------------------------------------------- #
# MDTInstance — 속성/상태 검증
# --------------------------------------------------------------------------- #

class TestMDTInstanceProperties:
    def test_property_passthrough(self):
        desc = make_descriptor(
            id="i1",
            aas_id="aas-i1",
            aas_id_short="short",
            global_asset_id="global",
            base_endpoint="http://i1",
        )
        inst = MDTInstance(desc, BASE_URL)
        assert inst.id == "i1"
        assert inst.aas_id == "aas-i1"
        assert inst.aas_id_short == "short"
        assert inst.global_asset_id == "global"
        assert inst.base_endpoint == "http://i1"
        assert inst.descriptor is desc

    def test_status_is_passed_through(self):
        desc = make_descriptor(status=MDTInstanceStatus.STOPPED)
        inst = MDTInstance(desc, BASE_URL)
        assert inst.status == MDTInstanceStatus.STOPPED

    def test_is_running_true_only_for_running_status(self):
        running = MDTInstance(make_descriptor(status=MDTInstanceStatus.RUNNING), BASE_URL)
        stopped = MDTInstance(make_descriptor(status=MDTInstanceStatus.STOPPED), BASE_URL)
        assert running.is_running() is True
        assert stopped.is_running() is False

    def test_repr_contains_class_and_descriptor(self):
        inst = MDTInstance(make_descriptor(id="abc"), BASE_URL)
        r = repr(inst)
        assert "MDTInstance(" in r
        assert "abc" in r
        # 옛 클래스 이름이 노출되면 안 됨
        assert "HttpMDTInstance" not in r


class TestMDTInstanceCollections:
    """parameters / submodel_descriptors / operation_descriptors 는
    상태가 RUNNING이 아니면 InvalidResourceStateError를 발생시켜야 한다."""

    @pytest.mark.parametrize(
        "attr",
        ["parameters", "submodel_descriptors", "operation_descriptors"],
    )
    def test_property_raises_when_not_running(self, attr):
        inst = MDTInstance(make_descriptor(status=MDTInstanceStatus.STOPPED), BASE_URL)
        with pytest.raises(InvalidResourceStateError):
            getattr(inst, attr)


# --------------------------------------------------------------------------- #
# MDTInstance — start / stop / reload_descriptor
# --------------------------------------------------------------------------- #

class TestMDTInstanceLifecycle:
    @patch("mdtpy.instance._put")
    @patch("mdtpy.instance.parse_none_response")
    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_start_nowait_returns_descriptor_when_state_valid(
        self, mock_parse, mock_get, mock_parse_none, mock_put,
    ):
        mock_put.return_value = make_response(200)
        mock_get.return_value = make_response(200)
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.STARTING)

        inst = MDTInstance(make_descriptor(status=MDTInstanceStatus.STOPPED), BASE_URL)
        result = inst.start(nowait=True)
        assert result.status == MDTInstanceStatus.STARTING
        assert mock_parse_none.called  # 응답 검증이 실행됨

    @patch("mdtpy.instance._put")
    @patch("mdtpy.instance.parse_none_response")
    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_start_raises_if_state_neither_starting_nor_running(
        self, mock_parse, mock_get, mock_parse_none, mock_put,
    ):
        mock_put.return_value = make_response(200)
        mock_get.return_value = make_response(200)
        # PUT 후 reload 결과가 STOPPED라면 비정상
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.STOPPED)

        inst = MDTInstance(make_descriptor(status=MDTInstanceStatus.STOPPED), BASE_URL)
        with pytest.raises(InvalidResourceStateError):
            inst.start(nowait=True)

    @patch("mdtpy.instance._put")
    @patch("mdtpy.instance.parse_none_response")
    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_stop_nowait_returns_descriptor_when_state_valid(
        self, mock_parse, mock_get, mock_parse_none, mock_put,
    ):
        mock_put.return_value = make_response(200)
        mock_get.return_value = make_response(200)
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.STOPPING)

        inst = MDTInstance(make_descriptor(status=MDTInstanceStatus.RUNNING), BASE_URL)
        result = inst.stop(nowait=True)
        assert result.status == MDTInstanceStatus.STOPPING

    @patch("mdtpy.instance._put")
    @patch("mdtpy.instance.parse_none_response")
    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_stop_raises_if_state_neither_stopping_nor_stopped(
        self, mock_parse, mock_get, mock_parse_none, mock_put,
    ):
        mock_put.return_value = make_response(200)
        mock_get.return_value = make_response(200)
        # PUT 후 reload 결과가 RUNNING이라면 비정상
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.RUNNING)

        inst = MDTInstance(make_descriptor(status=MDTInstanceStatus.RUNNING), BASE_URL)
        with pytest.raises(InvalidResourceStateError):
            inst.stop(nowait=True)

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_reload_descriptor_updates_state(self, mock_parse, mock_get):
        mock_get.return_value = make_response()
        new_desc = make_descriptor(status=MDTInstanceStatus.RUNNING, id="i1")
        mock_parse.return_value = new_desc

        inst = MDTInstance(make_descriptor(status=MDTInstanceStatus.STOPPED, id="i1"), BASE_URL)
        result = inst.reload_descriptor()
        assert result is new_desc
        assert inst.status == MDTInstanceStatus.RUNNING


# --------------------------------------------------------------------------- #
# StatusPoller / InstanceStartPoller / InstanceStopPoller
# --------------------------------------------------------------------------- #

class _ImmediateDonePoller(StatusPoller):
    """is_done이 항상 True인 단순 폴러 — wait_for_done 즉시 반환 검증용."""

    def is_done(self) -> bool:  # pragma: no cover - trivial
        return True


class _NeverDonePoller(StatusPoller):
    """is_done이 항상 False — 타임아웃 검증용."""

    def is_done(self) -> bool:  # pragma: no cover - trivial
        return False


class TestStatusPoller:
    def test_wait_for_done_returns_immediately_when_done(self):
        poller = _ImmediateDonePoller(poll_interval=0.01)
        # 즉시 반환이어야 하므로 어떤 예외도 나지 않아야 한다
        poller.wait_for_done()

    def test_wait_for_done_raises_timeout_when_never_done(self):
        poller = _NeverDonePoller(poll_interval=0.01, timeout=0.05)
        with pytest.raises(TimeoutError):
            poller.wait_for_done()


class TestInstanceStartPoller:
    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_is_done_false_while_starting(self, mock_parse, mock_get):
        mock_get.return_value = make_response()
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.STARTING)

        poller = InstanceStartPoller(
            BASE_URL, init_desc=make_descriptor(status=MDTInstanceStatus.STARTING),
        )
        assert poller.is_done() is False

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_is_done_true_when_state_changes_from_starting(self, mock_parse, mock_get):
        mock_get.return_value = make_response()
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.RUNNING)

        poller = InstanceStartPoller(
            BASE_URL, init_desc=make_descriptor(status=MDTInstanceStatus.STARTING),
        )
        assert poller.is_done() is True
        assert poller.desc.status == MDTInstanceStatus.RUNNING

    def test_is_done_short_circuits_when_initial_state_not_starting(self):
        """초기 상태가 STARTING이 아니면 GET 없이 True를 반환해야 한다."""
        poller = InstanceStartPoller(
            BASE_URL, init_desc=make_descriptor(status=MDTInstanceStatus.RUNNING),
        )
        with patch("mdtpy.instance._get") as mock_get:
            assert poller.is_done() is True
            mock_get.assert_not_called()


class TestInstanceStopPoller:
    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_is_done_false_while_stopping(self, mock_parse, mock_get):
        mock_get.return_value = make_response()
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.STOPPING)

        poller = InstanceStopPoller(
            BASE_URL, init_desc=make_descriptor(status=MDTInstanceStatus.STOPPING),
        )
        assert poller.is_done() is False

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_is_done_true_when_transitions_to_stopped(self, mock_parse, mock_get):
        mock_get.return_value = make_response()
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.STOPPED)

        poller = InstanceStopPoller(
            BASE_URL, init_desc=make_descriptor(status=MDTInstanceStatus.STOPPING),
        )
        assert poller.is_done() is True

    @patch("mdtpy.instance._get")
    @patch("mdtpy.instance.parse_response")
    def test_is_done_true_when_transitions_to_failed(self, mock_parse, mock_get):
        """STOPPED가 아닌 다른 종료 상태(FAILED 등)이어도 폴링이 끝나야 한다.
        과거 회귀 케이스: STOPPING -> FAILED 시 무한 대기."""
        mock_get.return_value = make_response()
        mock_parse.return_value = make_descriptor(status=MDTInstanceStatus.FAILED)

        poller = InstanceStopPoller(
            BASE_URL, init_desc=make_descriptor(status=MDTInstanceStatus.STOPPING),
        )
        assert poller.is_done() is True
        assert poller.desc.status == MDTInstanceStatus.FAILED

    def test_is_done_short_circuits_when_initial_state_not_stopping(self):
        """초기 상태가 STOPPING이 아니면 GET 없이 True를 반환해야 한다."""
        poller = InstanceStopPoller(
            BASE_URL, init_desc=make_descriptor(status=MDTInstanceStatus.STOPPED),
        )
        with patch("mdtpy.instance._get") as mock_get:
            assert poller.is_done() is True
            mock_get.assert_not_called()
