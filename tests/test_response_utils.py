import pytest
from shared.response_utils import SuccessResponse, ErrorResponse

def test_success_response():
    # Test a successful response
    data = {"key": "value"}
    resp = SuccessResponse.build(data)
    assert resp["statusCode"] == 200
    assert "key" in resp["body"]
    assert resp["body"] == '{"key": "value"}'  # Ensure the body is serialized correctly

def test_error_response():
    # Test an error response
    error_message = "Something went wrong"
    status_code = 400
    resp = ErrorResponse.build(error_message, status_code)
    assert resp["statusCode"] == status_code
    assert error_message in resp["body"]
    assert resp["body"] == '{"error": "Something went wrong"}'  # Ensure the body is serialized correctly