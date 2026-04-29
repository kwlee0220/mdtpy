"""
mdtpy.fa3st 모듈의 클래스/함수에 대한 단위 테스트.

대상:
    - Message 데이터클래스 (JSONWizard 통합)
    - encode_base64url / decode_base64url 라운드트립 + 패딩 처리
    - read_none_response / read_response / read_file_response 상태 코드 분기
    - call_get / call_put / call_post / call_patch / call_delete
        (정상 흐름, deserializer 적용, ConnectionError → MDTInstanceConnectionError,
         timeout/verify 적용 검증)
    - to_exception (text/* / messages / code 분기 — http_client.to_exception에 위임)

requests.Response와 requests.{request,delete}는 mock 처리한다.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from mdtpy.exceptions import (
    MDTException,
    MDTInstanceConnectionError,
    RemoteError,
    ResourceNotFoundError,
)
from mdtpy.fa3st import (
    DEFAULT_TIMEOUT,
    JSON_HEADERS,
    VERIFY_TLS,
    Message,
    call_delete,
    call_get,
    call_patch,
    call_post,
    call_put,
    decode_base64url,
    encode_base64url,
    read_file_response,
    read_none_response,
    read_response,
    to_exception,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_response(
    status_code: int = 200,
    text: str = "",
    json_data=None,
    content: bytes = b"",
    content_type: str = "application/json",
) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.content = content
    resp.headers = {"content-type": content_type, "Content-Type": content_type}
    resp.json.return_value = json_data
    return resp


# --------------------------------------------------------------------------- #
# Message
# --------------------------------------------------------------------------- #

class TestMessage:
    def test_construction_and_attribute_access(self):
        m = Message(message_type="Error", text="boom", code="X1", timestamp="2026-01-01T00:00:00Z")
        assert m.message_type == "Error"
        assert m.text == "boom"
        assert m.code == "X1"
        assert m.timestamp == "2026-01-01T00:00:00Z"

    def test_is_frozen(self):
        m = Message(message_type="Error", text="t", code="c", timestamp="ts")
        with pytest.raises((AttributeError, Exception)):
            m.text = "changed"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# base64url / url codecs
# --------------------------------------------------------------------------- #

class TestBase64UrlCodec:
    @pytest.mark.parametrize(
        "value",
        [
            "simple",
            "with/slash:and:colons",
            "https://example.com/aas/123",
            "",
            "한글 문자열",
        ],
    )
    def test_roundtrip(self, value):
        encoded = encode_base64url(value)
        assert isinstance(encoded, str)
        # URL-safe Base64 출력에는 '/'와 '+'가 등장하지 않아야 한다
        assert "/" not in encoded and "+" not in encoded
        assert decode_base64url(encoded) == value

    def test_decode_handles_missing_padding(self):
        """짧은 문자열을 인코딩하면 출력에서 `=` 패딩을 제거한 형태가 흔하다.
        decode_base64url이 패딩을 자동으로 보충해 정상 디코딩되어야 한다."""
        encoded = encode_base64url("ab")  # 인코딩 결과는 'YWI=' 또는 'YWI'
        without_padding = encoded.rstrip("=")
        assert decode_base64url(without_padding) == "ab"


# --------------------------------------------------------------------------- #
# read_none_response / read_response / read_file_response
# --------------------------------------------------------------------------- #

class TestReadNoneResponse:
    @pytest.mark.parametrize("code", [200, 201, 204, 299])
    def test_returns_none_for_2xx(self, code):
        assert read_none_response(make_response(status_code=code)) is None

    def test_raises_for_non_2xx(self):
        resp = make_response(
            status_code=500,
            json_data={"messages": [{"text": "boom"}]},
        )
        with pytest.raises(MDTException):
            read_none_response(resp)


class TestReadResponse:
    def test_204_returns_none(self):
        assert read_response(make_response(status_code=204)) is None

    def test_2xx_returns_text(self):
        resp = make_response(status_code=200, text="hello")
        assert read_response(resp) == "hello"

    def test_non_2xx_raises(self):
        resp = make_response(
            status_code=500,
            json_data={"messages": [{"text": "fail"}]},
        )
        with pytest.raises(MDTException):
            read_response(resp)


class TestReadFileResponse:
    def test_204_returns_none(self):
        assert read_file_response(make_response(status_code=204)) is None

    def test_2xx_returns_content_type_and_bytes(self):
        resp = make_response(
            status_code=200,
            content=b"\x89PNG\r\n",
            content_type="image/png",
        )
        result = read_file_response(resp)
        assert result == ("image/png", b"\x89PNG\r\n")

    def test_non_2xx_raises(self):
        resp = make_response(
            status_code=500,
            json_data={"messages": [{"text": "fail"}]},
        )
        with pytest.raises(MDTException):
            read_file_response(resp)


# --------------------------------------------------------------------------- #
# call_get / call_put / call_post / call_patch / call_delete
# --------------------------------------------------------------------------- #

class TestCallGet:
    @patch("mdtpy.fa3st.requests.request")
    def test_uses_get_method_with_default_timeout_and_verify(self, mock_request):
        mock_request.return_value = make_response(status_code=200, text="raw")
        assert call_get("http://x") == "raw"
        # method=GET, verify=VERIFY_TLS, timeout=DEFAULT_TIMEOUT 검증
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert args[1] == "http://x"
        assert kwargs["verify"] is VERIFY_TLS
        assert kwargs["timeout"] == DEFAULT_TIMEOUT

    @patch("mdtpy.fa3st.requests.request")
    def test_applies_deserializer_when_text_present(self, mock_request):
        mock_request.return_value = make_response(status_code=200, text='{"k":1}')
        result = call_get("http://x", deserializer=lambda s: {"parsed": s})
        assert result == {"parsed": '{"k":1}'}

    @patch("mdtpy.fa3st.requests.request")
    def test_returns_none_for_204_without_calling_deserializer(self, mock_request):
        mock_request.return_value = make_response(status_code=204)
        sentinel = MagicMock()
        assert call_get("http://x", deserializer=sentinel) is None
        sentinel.assert_not_called()

    @patch("mdtpy.fa3st.requests.request")
    def test_connection_error_wrapped(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("nope")
        with pytest.raises(MDTInstanceConnectionError) as excinfo:
            call_get("http://unreachable")
        assert "http://unreachable" in str(excinfo.value)
        assert isinstance(excinfo.value.cause, requests.exceptions.ConnectionError)


class TestCallPut:
    @patch("mdtpy.fa3st.requests.request")
    def test_sends_data_with_put_method(self, mock_request):
        mock_request.return_value = make_response(status_code=200, text="ok")
        assert call_put("http://x", data="payload") == "ok"
        args, kwargs = mock_request.call_args
        assert args[0] == "PUT"
        assert kwargs["data"] == "payload"

    @patch("mdtpy.fa3st.requests.request")
    def test_connection_error_wrapped(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("nope")
        with pytest.raises(MDTInstanceConnectionError):
            call_put("http://x", data="d")


class TestCallPost:
    @patch("mdtpy.fa3st.requests.request")
    def test_sets_json_content_type_header_and_post_method(self, mock_request):
        mock_request.return_value = make_response(status_code=200, text="ok")
        call_post("http://x", data="{}")
        args, kwargs = mock_request.call_args
        assert args[0] == "POST"
        assert kwargs["headers"] == JSON_HEADERS

    @patch("mdtpy.fa3st.requests.request")
    def test_applies_deserializer(self, mock_request):
        mock_request.return_value = make_response(status_code=200, text="raw")
        result = call_post("http://x", data="{}", deserializer=str.upper)
        assert result == "RAW"

    @patch("mdtpy.fa3st.requests.request")
    def test_connection_error_wrapped(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("nope")
        with pytest.raises(MDTInstanceConnectionError):
            call_post("http://x", data="{}")


class TestCallPatch:
    @patch("mdtpy.fa3st.requests.request")
    def test_sets_json_content_type_header_and_patch_method(self, mock_request):
        mock_request.return_value = make_response(status_code=200, text="ok")
        call_patch("http://x", json_str='{"a":1}')
        args, kwargs = mock_request.call_args
        assert args[0] == "PATCH"
        assert kwargs["headers"] == JSON_HEADERS
        assert kwargs["data"] == '{"a":1}'

    @patch("mdtpy.fa3st.requests.request")
    def test_connection_error_wrapped(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("nope")
        with pytest.raises(MDTInstanceConnectionError):
            call_patch("http://x", json_str="{}")


class TestCallDelete:
    @patch("mdtpy.fa3st.requests.delete")
    def test_returns_none_on_success(self, mock_delete):
        mock_delete.return_value = make_response(status_code=204)
        assert call_delete("http://x") is None
        # timeout/verify이 적용되어 있어야 한다
        kwargs = mock_delete.call_args.kwargs
        assert kwargs["timeout"] == DEFAULT_TIMEOUT
        assert kwargs["verify"] is VERIFY_TLS

    @patch("mdtpy.fa3st.requests.delete")
    def test_raises_mdt_exception_on_error_response(self, mock_delete):
        mock_delete.return_value = make_response(
            status_code=404,
            json_data={"messages": [{"text": "missing"}]},
        )
        with pytest.raises(MDTException):
            call_delete("http://x")

    @patch("mdtpy.fa3st.requests.delete")
    def test_connection_error_wrapped(self, mock_delete):
        mock_delete.side_effect = requests.exceptions.ConnectionError("nope")
        with pytest.raises(MDTInstanceConnectionError):
            call_delete("http://x")


# --------------------------------------------------------------------------- #
# to_exception
# --------------------------------------------------------------------------- #

class TestToException:
    def test_text_content_type_returns_remote_error_with_text(self):
        """`Content-Type: text/plain` 같이 텍스트 응답은 본문 그대로 RemoteError로
        포장한다 (JSON 파싱을 시도하지 않음)."""
        resp = make_response(
            status_code=500,
            text="plain failure",
            content_type="text/plain",
        )
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "plain failure" in str(exc)

    def test_messages_key_returns_remote_error_with_first_text(self):
        resp = make_response(
            status_code=500,
            json_data={"messages": [{"text": "first"}, {"text": "second"}]},
        )
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "first" in str(exc)

    def test_illegal_argument_raises_remote_error(self):
        resp = make_response(
            status_code=400,
            json_data={"code": "java.lang.IllegalArgumentException", "message": "bad"},
        )
        with pytest.raises(RemoteError, match="bad"):
            to_exception(resp)

    def test_internal_exception_returns_remote_error(self):
        resp = make_response(
            status_code=500,
            json_data={"code": "utils.InternalException", "message": "oops"},
        )
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "oops" in str(exc)

    @pytest.mark.parametrize(
        "code",
        ["java.lang.NullPointerException", "java.lang.UnsupportedOperationException"],
    )
    def test_npe_and_unsupported_op_raise(self, code):
        resp = make_response(
            status_code=500,
            json_data={"code": code, "message": "msg"},
        )
        with pytest.raises(RemoteError) as excinfo:
            to_exception(resp)
        assert code in str(excinfo.value)

    @pytest.mark.parametrize(
        "code",
        [
            "org.springframework.web.servlet.resource.NoResourceFoundException",
            "org.springframework.web.HttpRequestMethodNotSupportedException",
        ],
    )
    def test_spring_exceptions_raise_with_text(self, code):
        resp = make_response(
            status_code=404,
            json_data={"code": code, "text": "spring err"},
        )
        with pytest.raises(RemoteError, match="spring err"):
            to_exception(resp)

    def test_resource_not_found_raises_resource_not_found_error(self):
        resp = make_response(
            status_code=404,
            json_data={"code": "mdt.model.ResourceNotFoundException", "message": "missing"},
        )
        with pytest.raises(ResourceNotFoundError, match="missing"):
            to_exception(resp)

    def test_unknown_code_falls_back_to_remote_error(self):
        """알려지지 않은 code는 동적 import 없이 안전한 RemoteError 폴백."""
        resp = make_response(
            status_code=500,
            json_data={"code": "unknown.module.SomeError", "message": "msg"},
        )
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "unknown.module.SomeError" in str(exc)
        assert "msg" in str(exc)

    def test_no_messages_no_code_returns_remote_error_with_text(self):
        resp = make_response(
            status_code=500,
            json_data={"other": "x"},
            text="raw body",
        )
        exc = to_exception(resp)
        assert isinstance(exc, RemoteError)
        assert "raw body" in str(exc)
