

import json
import os
import boto3
import logging
from shared.response_utils import SuccessResponse, ErrorResponse

TABLE = os.environ.get("TABLE_NAME", "v_devices")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def validate_pk_sk(data):
    """Validate PK and SK presence and type."""
    if not isinstance(data, dict):
        return False
    pk = data.get("PK") or data.get("pk")
    sk = data.get("SK") or data.get("sk")
    return isinstance(pk, str) and isinstance(sk, str) and pk and sk

def lambda_handler(event, context):
    """
    Lambda handler for v_devices CRUD operations.
    Supports POST, GET, PUT, DELETE methods.
    """
    method = event.get("httpMethod") or event.get("requestContext",{}).get("http",{}).get("method")
    logger.info(f"Received event: {json.dumps(event)}")
    try:
        if method == "POST":
            body = json.loads(event.get("body", "{}"))
            if not validate_pk_sk(body):
                logger.warning("Missing or invalid PK/SK in POST body")
                return ErrorResponse.build("Missing or invalid PK or SK in body", 400)
            body.setdefault("created_date", context.aws_request_id if context else "")
            try:
                table.put_item(Item=body)
            except Exception as e:
                logger.error(f"DynamoDB put_item failed: {e}")
                return ErrorResponse.build("Database error", 500)
            return SuccessResponse.build({"message": "created", "item": body})

        if method == "GET":
            params = event.get("queryStringParameters") or event.get("pathParameters") or {}
            if not validate_pk_sk(params):
                logger.warning("Missing or invalid PK/SK in GET params")
                return ErrorResponse.build("Missing or invalid PK or SK for GET", 400)
            pk = params.get("PK") or params.get("pk")
            sk = params.get("SK") or params.get("sk")
            try:
                r = table.get_item(Key={"PK": pk, "SK": sk})
            except Exception as e:
                logger.error(f"DynamoDB get_item failed: {e}")
                return ErrorResponse.build("Database error", 500)
            return SuccessResponse.build(r.get("Item"))

        if method == "PUT":
            body = json.loads(event.get("body", "{}"))
            if not validate_pk_sk(body):
                logger.warning("Missing or invalid PK/SK in PUT body")
                return ErrorResponse.build("Missing or invalid PK or SK in body", 400)
            body.setdefault("updated_date", context.aws_request_id if context else "")
            try:
                table.put_item(Item=body)
            except Exception as e:
                logger.error(f"DynamoDB put_item failed: {e}")
                return ErrorResponse.build("Database error", 500)
            return SuccessResponse.build({"message": "updated", "item": body})

        if method == "DELETE":
            params = event.get("queryStringParameters") or {}
            if not validate_pk_sk(params):
                logger.warning("Missing or invalid PK/SK in DELETE params")
                return ErrorResponse.build("Missing or invalid PK or SK for DELETE", 400)
            pk = params.get("PK") or params.get("pk")
            sk = params.get("SK") or params.get("sk")
            try:
                table.delete_item(Key={"PK": pk, "SK": sk})
            except Exception as e:
                logger.error(f"DynamoDB delete_item failed: {e}")
                return ErrorResponse.build("Database error", 500)
            return SuccessResponse.build({"message": "deleted"})

        logger.warning(f"Unsupported method: {method}")
        return ErrorResponse.build("Unsupported method", 405)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return ErrorResponse.build("Internal server error", 500)
