
import json
from typing import Any, Dict, Optional

class SuccessResponse:
    @staticmethod
    def build(body: Any = None, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> dict:
        """
        Returns a standard API Gateway success response with CORS headers.
        """
        return build_response(status_code, body, headers)

class ErrorResponse:
    @staticmethod
    def build(message: str = None, status_code: int = 400, headers: Optional[Dict[str, str]] = None) -> dict:
        """
        Returns a standard API Gateway error response with CORS headers and a message.
        """
        if not message:
            message = ERROR_RESPONSES.get(status_code, "Unknown error")
        return build_response(status_code, {"error": message}, headers)
import json

def build_response(status_code, body=None, headers=None):
    base_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
    }
    if headers:
        base_headers.update(headers)
    return {
        "statusCode": status_code,
        "body": json.dumps(body) if body is not None else "",
        "headers": base_headers,
        "isBase64Encoded": False
    }

ERROR_RESPONSES = {
    400: "Bad Request: The request could not be understood by the server due to malformed syntax",
    401: "Unauthorized: Authentication is required and has failed or has not yet been provided",
    403: "Forbidden: You do not have permission to access this resource",
    404: "Not Found: The requested resource could not be found",
    405: "Method Not Allowed: The method specified in the request is not allowed for the resource",
    408: "Request Timeout: The server timed out waiting for the request",
    409: "Conflict: The request could not be completed due to a conflict with the current state of the resource",
    410: "Gone: The requested resource is no longer available and will not be available again",
    411: "Length Required: The request did not specify the length of its content, which is required by the requested resource",
    412: "Precondition Failed: The server does not meet one of the preconditions that the requester put on the request",
    413: "Payload Too Large: The request is larger than the server is willing or able to process",
    414: "URI Too Long: The URI provided was too long for the server to process",
    415: "Unsupported Media Type: The request entity has a media type which the server or resource does not support",
    416: "Range Not Satisfiable: The requested range cannot be satisfied and is out of bounds",
    417: "Expectation Failed: The server cannot meet the requirements of the Expect request-header field",
    418: "I'm a teapot: The server refuses to brew coffee because it is a teapot",
    419: "Authentication Timeout: The user's session has expired and requires re-authentication",
    420: "Enhance Your Calm: The user has sent too many requests in a given amount of time",
    421: "Misdirected Request: The request was directed at a server that is not able to produce a response",
    422: "Unprocessable Entity: The request was well-formed but was unable to be followed due to semantic errors",
    423: "Locked: The resource that is being accessed is locked",
    424: "Failed Dependency: The request failed due to failure of a previous request",
    425: "Too Early: The server is unwilling to risk processing a request that might be replayed",
    426: "Upgrade Required: The client should switch to a different protocol",
    428: "Precondition Required: The origin server requires the request to be conditional",
    429: "Too Many Requests: The user has sent too many requests in a given amount of time",
    431: "Request Header Fields Too Large: The server is unwilling to process the request because its header fields are too large",
    451: "Unavailable For Legal Reasons: The server is denying access to the resource as a consequence of a legal demand",
    500: "Internal Server Error: The server encountered an unexpected condition that prevented it from fulfilling the request",
    501: "Not Implemented: The server does not support the functionality required to fulfill the request",
    502: "Bad Gateway: The server, while acting as a gateway or proxy, received an invalid response from the upstream server",
    503: "Service Unavailable: The server is currently unable to handle the request due to temporary overloading or maintenance of the server",
    504: "Gateway Timeout: The server, while acting as a gateway or proxy, did not receive a timely response from the upstream server",
    505: "HTTP Version Not Supported: The server does not support the HTTP protocol version that was used in the request",
    511: "Network Authentication Required: The client needs to authenticate to gain network access"
}

def error_response(status_code):
    message = ERROR_RESPONSES.get(status_code, "Unknown error")
    return build_response(status_code, {"error": message})