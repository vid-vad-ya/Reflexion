"""Unit test script for LLMService logic validation using mocks."""

import sys
import os
import unittest.mock as mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydantic import BaseModel
from google.genai.errors import ClientError, ServerError
from app.services.llm import LLMService, LLMConfigurationError, LLMValidationError, LLMAPIError


class DemoSchema(BaseModel):
    language: str
    framework: str


def run_unit_tests():
    print("==================================================")
    print("LLMService Unit Logic Tests (Mocked)")
    print("==================================================")

    # 1. Missing API Key Test
    print("\n[1/6] Testing missing GEMINI_API_KEY...")
    svc_no_key = LLMService(api_key="", default_model="gemini-2.0-flash")
    try:
        _ = svc_no_key.client
        raise AssertionError("Should have raised LLMConfigurationError")
    except LLMConfigurationError as e:
        print(f"  [PASS] Raised LLMConfigurationError: {e}")

    # Setup Mock Client
    mock_client = mock.MagicMock()
    svc = LLMService(api_key="dummy_key", default_model="gemini-2.0-flash")
    svc._client = mock_client

    # 2. Text Generation Test
    print("\n[2/6] Testing generate_text()...")
    mock_text_resp = mock.MagicMock()
    mock_text_resp.text = "Hello world three"
    mock_client.models.generate_content.return_value = mock_text_resp

    text_res = svc.generate_text("Say hello in three words")
    assert text_res == "Hello world three"
    print(f"  [PASS] generate_text returned: '{text_res}'")

    # 3. Structured Output JSON Test (Parsed attribute)
    print("\n[3/6] Testing generate_json() with valid schema...")
    mock_json_resp = mock.MagicMock()
    mock_json_resp.text = '{"language": "Python", "framework": "FastAPI"}'
    mock_json_resp.parsed = DemoSchema(language="Python", framework="FastAPI")
    mock_client.models.generate_content.return_value = mock_json_resp

    json_res = svc.generate_json("Prompt", DemoSchema)
    assert isinstance(json_res, DemoSchema)
    assert json_res.language == "Python"
    assert json_res.framework == "FastAPI"
    print(f"  [PASS] generate_json returned validated object: {json_res}")

    # 4. Structured Output Validation Failure Test
    print("\n[4/6] Testing generate_json() validation failure...")
    mock_invalid_json = mock.MagicMock()
    mock_invalid_json.text = '{"unknown_field": "invalid"}'
    mock_invalid_json.parsed = None
    mock_client.models.generate_content.return_value = mock_invalid_json

    try:
        svc.generate_json("Prompt", DemoSchema)
        raise AssertionError("Should have raised LLMValidationError")
    except LLMValidationError as e:
        print(f"  [PASS] Raised LLMValidationError on invalid JSON: {e}")

    # 5. Non-retryable 404 Error Test
    print("\n[5/6] Testing 404 NOT_FOUND immediate failure (no retries)...")
    response_404 = mock.MagicMock()
    response_404.status_code = 404
    response_404.text = '{"error": {"code": 404, "message": "Model not found", "status": "NOT_FOUND"}}'
    err_404 = ClientError(404, response_404)
    fail_404_mock = mock.MagicMock(side_effect=err_404)
    mock_client.models.generate_content = fail_404_mock

    try:
        svc.generate_text("Test 404 prompt")
        raise AssertionError("Should have raised LLMAPIError immediately")
    except LLMAPIError as e:
        assert fail_404_mock.call_count == 1, f"404 must NOT retry! Call count was {fail_404_mock.call_count}"
        print(f"  [PASS] 404 error failed immediately on attempt 1 without retrying.")

    # 6. Transient Error Retry Test (Max 3 attempts)
    print("\n[6/6] Testing transient error retry logic (max 3 attempts)...")
    response_503 = mock.MagicMock()
    response_503.status_code = 503
    response_503.text = '{"error": {"code": 503, "message": "Service Unavailable"}}'
    err_503 = ServerError(503, response_503)

    fail_transient = mock.MagicMock(side_effect=[
        err_503,
        mock_text_resp,
    ])
    mock_client.models.generate_content = fail_transient

    retry_res = svc.generate_text("Test retry prompt")
    assert retry_res == "Hello world three"
    assert fail_transient.call_count == 2
    print(f"  [PASS] Retried transient 503 error and succeeded on attempt 2.")

    print("\n==================================================")
    print("ALL MOCK UNIT TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_unit_tests()
