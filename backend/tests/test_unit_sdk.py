import io
import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from sdk.dam_client import DAMClient


class TestDAMClientSDK:
    def test_init_normalizes_base_url_and_defaults(self):
        client = DAMClient("http://localhost:8000///", "test-key", "demo-app")
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == "test-key"
        assert client.app_id == "demo-app"
        assert client.timeout == 35

    def test_init_custom_timeout(self):
        client = DAMClient("http://api.example.com", "key", "app", timeout=10)
        assert client.timeout == 10

    @patch("sdk.dam_client.urlopen")
    def test_verify_payload_and_headers_default(self, mock_urlopen):
        expected_response = {
            "job_id": "test-job-id",
            "hallucination_score": 0.0,
            "claims": []
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(expected_response).encode("utf-8")
        mock_response.__enter__.return_value = io.BytesIO(json.dumps(expected_response).encode("utf-8"))
        mock_urlopen.return_value = mock_response

        client = DAMClient("http://127.0.0.1:8000", "my-secret-key", "chat-app")
        result = client.verify("France is in Europe.")

        assert result == expected_response
        assert mock_urlopen.call_count == 1
        req = mock_urlopen.call_args[0][0]

        # Inspect request
        assert req.full_url == "http://127.0.0.1:8000/verify"
        assert req.headers["Authorization"] == "Bearer my-secret-key"
        assert req.headers["Content-type"] == "application/json"
        assert mock_urlopen.call_args[1]["timeout"] == 35

        body = json.loads(req.data.decode("utf-8"))
        assert body["text"] == "France is in Europe."
        assert body["source_app_id"] == "chat-app"
        assert body["context"] == ""
        assert "confidence_threshold" not in body

    @patch("sdk.dam_client.urlopen")
    def test_verify_with_context_and_threshold(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = io.BytesIO(b'{"status": "ok"}')
        mock_urlopen.return_value = mock_response

        client = DAMClient("http://127.0.0.1:8000", "key", "app", timeout=15)
        result = client.verify("Fact.", context="Surrounding context", confidence_threshold=0.85)

        assert result == {"status": "ok"}
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["context"] == "Surrounding context"
        assert body["confidence_threshold"] == 0.85
        assert mock_urlopen.call_args[1]["timeout"] == 15

    @patch("sdk.dam_client.urlopen")
    def test_verify_propagates_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/verify",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"message": "Invalid key"}}')
        )

        client = DAMClient("http://127.0.0.1:8000", "bad-key", "app")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            client.verify("Text.")
        assert exc_info.value.code == 401

    @patch("sdk.dam_client.urlopen")
    def test_verify_propagates_network_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        client = DAMClient("http://127.0.0.1:8000", "key", "app")
        with pytest.raises(TimeoutError):
            client.verify("Text.")
