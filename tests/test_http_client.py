"""
mdtpy.http_client 모듈의 함수들에 대한 단위 테스트.

대상 함수:
    - parse_none_response(resp)
    - parse_response(resp, result_cls=None)
    - parse_list_response(resp, result_cls=None)
    - to_exception(resp)

requests.Response는 unittest.mock으로 가짜 처리한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from mdtpy.exceptions import MDTException, RemoteError, ResourceNotFoundError
from mdtpy.http_client import (
    parse_list_response,
    parse_none_response,
    parse_response,
    to_exception,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_response(
    status_code: int = 200,
    json_data=None,
    content_type: str = "application/json",
    text: str = "",
) -> MagicMock:
    resp = MagicMock(name=f"Response({status_code})")
    resp.status_code = status_code
    resp.headers = {"content-type": content_type}
    resp.json.return_value = json_data
    resp.text = text
    return resp


@dataclass
class _SampleDescriptor:
    """parse_response/parse_list_response의 result_cls 자리에 쓸 dummy dataclass.

    `from_dict` 클래스메서드만 만족하면 충분하다.
    """

    name: str
    value: int

    @classmethod
    def from_dict(cls, data: dict) -> "_SampleDescriptor":
        return cls(name=data["name"], value=data["value"])


# --------------------------------------------------------------------------- #
# parse_none_response
# --------------------------------------------------------------------------- #

class TestParseNoneResponse:
    @pytest.mark.parametrize("code", [200, 201, 204, 299])
    def test_returns_none_for_success_status_codes(self, code):
        # 본문 검사 없이 그냥 통과해야 한다
        assert parse_none_response(make_response(status_code=code)) is None

    @pytest.mark.parametrize("code", [400, 404, 500, 503])
    def test_raises_for_non_success_status_codes(self, code):
        resp = make_response(status_code=code, json_data={"messages": [{"text": "boom"}]})
        # to_exception이 RemoteError를 반환 → parse_none_response가 raise한다
        with pytest.raises(MDTException):
            parse_none_response(resp)


# --------------------------------------------------------------------------- #
# parse_response
# --------------------------------------------------------------------------- #

class TestParseResponse:
    def test_returns_raw_json_when_result_cls_is_none(self):
        resp = make_response(json_data={"a": 1})
        assert parse_response(resp) == {"a": 1}

    def test_uses_result_cls_from_dict(self):
        resp = make_response(json_data={"name": "x", "value": 42})
        result = parse_response(resp, _SampleDescriptor)
        assert isinstance(result, _SampleDescriptor)
        assert result.name == "x"
        assert result.value == 42

    def test_returns_text_for_text_plain(self):
        resp = make_response(content_type="text/plain", text="hello world")
        assert parse_response(resp) == "hello world"

    def test_text_plain_with_charset_suffix_works(self):
        """`text/plain; charset=utf-8`처럼 파라미터가 붙어도 처리되어야 한다."""
        resp = make_response(content_type="text/plain; charset=utf-8", text="ok")
        assert parse_response(resp) == "ok"

    def test_unsupported_content_type_raises_mdt_exception(self):
        resp = make_response(content_type="application/octet-stream")
        with pytest.raises(MDTException, match="Unsupported content type"):
            parse_response(resp)

    def test_non_success_status_raises(self):
        resp = make_response(status_code=500, json_data={"messages": [{"text": "fail"}]})
        with pytest.raises(MDTException):
            parse_response(resp)


# --------------------------------------------------------------------------- #
# parse_list_response
# --------------------------------------------------------------------------- #

class TestParseListResponse:
    def test_returns_list_of_parsed_items(self):
        resp = make_response(
            json_data=[{"name": "a", "value": 1}, {"name": "b", "value": 2}]
        )
        result = parse_list_response(resp, _SampleDescriptor)
        assert len(result) == 2
        assert all(isinstance(x, _SampleDescriptor) for x in result)
        assert [x.name for x in result] == ["a", "b"]
        assert [x.value for x in result] == [1, 2]

    def test_empty_list_response(self):
        resp = make_response(json_data=[])
        assert parse_list_response(resp, _SampleDescriptor) == []

    def test_non_success_status_raises(self):
        resp = make_response(
            status_code=404, json_data={"messages": [{"text": "no"}]}
        )
        with pytest.raises(MDTException):
            parse_list_response(resp, _SampleDescriptor)


# --------------------------------------------------------------------------- #
# to_exception
# --------------------------------------------------------------------------- #

class TestToException:
    # ----- messages 우선 처리 ----- #

    def test_messages_present_returns_remote_error_with_first_text(self):
        resp = make_response(
            json_data={"messages": [{"text": "first error"}, {"text": "second"}]}
        )
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "first error" in str(exc)

    # ----- code 분기: 명시적으로 매핑된 케이스 ----- #

    def test_illegal_argument_raises_remote_error(self):
        """`java.lang.IllegalArgumentException`은 직접 raise한다."""
        resp = make_response(
            json_data={"code": "java.lang.IllegalArgumentException",
                       "message": "bad arg"}
        )
        with pytest.raises(RemoteError, match="bad arg"):
            to_exception(resp)

    def test_internal_exception_returns_remote_error(self):
        """`utils.InternalException`은 RemoteError를 반환한다 (raise 아님)."""
        resp = make_response(
            json_data={"code": "utils.InternalException", "message": "internal"}
        )
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "internal" in str(exc)

    @pytest.mark.parametrize(
        "code",
        ["java.lang.NullPointerException", "java.lang.UnsupportedOperationException"],
    )
    def test_npe_and_unsupported_op_raise(self, code):
        resp = make_response(json_data={"code": code, "message": "msg"})
        with pytest.raises(RemoteError) as excinfo:
            to_exception(resp)
        assert code in str(excinfo.value)
        assert "msg" in str(excinfo.value)

    @pytest.mark.parametrize(
        "code",
        [
            "org.springframework.web.servlet.resource.NoResourceFoundException",
            "org.springframework.web.HttpRequestMethodNotSupportedException",
        ],
    )
    def test_spring_exceptions_raise_with_text(self, code):
        resp = make_response(json_data={"code": code, "text": "spring err"})
        with pytest.raises(RemoteError, match="spring err"):
            to_exception(resp)

    def test_resource_not_found_raises_resource_not_found_error(self):
        resp = make_response(
            json_data={"code": "mdt.model.ResourceNotFoundException",
                       "message": "missing"}
        )
        with pytest.raises(ResourceNotFoundError, match="missing"):
            to_exception(resp)

    # ----- code 분기: 동적 import 경로 ----- #

    def test_unknown_code_falls_back_to_remote_error(self):
        """알려지지 않은 code는 안전한 RemoteError 폴백으로 처리된다.

        과거에는 importlib으로 동적 import를 시도했으나 신뢰할 수 없는
        서버가 임의 모듈을 로드시킬 위험이 있어 제거했다 (회귀 가드)."""
        resp = make_response(
            json_data={"code": "unknown.module.SomeError", "message": "msg"}
        )
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "unknown.module.SomeError" in str(exc)
        assert "msg" in str(exc)

    def test_text_content_type_returns_remote_error(self):
        """`Content-Type: text/*`인 경우 JSON 파싱 없이 본문 그대로 RemoteError로
        포장한다 (fa3st.to_exception과 일치하는 동작)."""
        resp = make_response(content_type="text/plain", text="plain failure")
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "plain failure" in str(exc)

    # ----- 둘 다 없는 경우 ----- #

    def test_no_messages_no_code_returns_remote_error_with_text(self):
        resp = make_response(json_data={"other": "stuff"}, text="raw body")
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "raw body" in str(exc)
