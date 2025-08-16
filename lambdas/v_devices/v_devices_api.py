import json
import os
import boto3
import logging
from shared.response_utils import SuccessResponse, ErrorResponse
from pydantic import BaseModel, ValidationError, Field

def validate_pk_sk(data):
    if not isinstance(data, dict):
        return False
    pk = data.get("PK") or data.get("pk")
    sk = data.get("SK") or data.get("sk")
    return isinstance(pk, str) and isinstance(sk, str) and pk and sk

class DeviceDetails(BaseModel):
    PK: str = Field(..., description="Device ID, must start with 'device-'")
    SK: str = Field(..., description="Device type or sub-ID")
    name: str
    created_date: str = None
    updated_date: str = None
    status: str = None
    metadata: dict = None
    class Config:
        extra = "forbid"
    @classmethod
    def validate_pk(cls, pk: str) -> bool:
        return pk.startswith("device-")

TABLE = os.environ.get("TABLE_NAME", "v_devices")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def lambda_handler(event, context):
    print("=== LAMBDA HANDLER STARTED ===")
    logger.error("Lambda handler started - DEBUG logging enabled")
    method = event.get("httpMethod") or event.get("requestContext",{}).get("http",{}).get("method")
    logger.info(f"Received event: {json.dumps(event)}")
    logger.debug(f"HTTP method: {method}")
    logger.debug(f"Raw event body: {event.get('body')}")
    try:
        if method == "POST":
            try:
                logger.debug("Parsing event body...")
                body = json.loads(event.get("body", "{}"))
                logger.debug(f"Parsed body: {body}")
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            try:
                device = DeviceDetails(**body)
            except (ValidationError, ValueError) as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid device details: {ve}", 400)
            item = device.dict(exclude_none=True)
            from datetime import datetime
            sysdate = datetime.utcnow().isoformat() + "Z"
            for date_field in ("created_date", "updated_date"):
                if item.get(date_field):
                    try:
                        datetime.fromisoformat(item[date_field].replace("Z", ""))
                    except Exception:
                        return ErrorResponse.build(f"Invalid date format for {date_field}", 400)
                else:
                    item[date_field] = sysdate
            if not item.get("status"):
                item["status"] = "active"
            if not item.get("metadata"):
                item["metadata"] = {}
            try:
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
                )
            except Exception as e:
                if "ConditionalCheckFailedException" in str(e):
                    logger.warning("Duplicate item detected, not inserted.")
                    return ErrorResponse.build("Duplicate item: already exists", 409)
                logger.error(f"DynamoDB put_item failed: {e}")
                return ErrorResponse.build("Database error", 500)
            return SuccessResponse.build({"message": "created", "item": item})

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
            try:
                device = DeviceDetails(**body)
            except (ValidationError, ValueError) as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid device details: {ve}", 400)
            item = device.dict(exclude_none=True)
            from datetime import datetime
            sysdate = datetime.utcnow().isoformat() + "Z"
            item["updated_date"] = sysdate
            if not item.get("status"):
                item["status"] = "active"
            if not item.get("metadata"):
                item["metadata"] = {}
            try:
                response = table.update_item(
                    Key={"PK": item["PK"], "SK": item["SK"]},
                    UpdateExpression="SET " + ", ".join(f"{k} = :{k}" for k in item if k not in ["PK", "SK"]),
                    ExpressionAttributeValues={f":{k}": v for k, v in item.items() if k not in ["PK", "SK"]},
                    ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
                    ReturnValues="ALL_NEW"
                )
            except Exception as e:
                logger.error(f"DynamoDB update_item failed: {e}")
                return ErrorResponse.build("Database error", 500)
            return SuccessResponse.build({"message": "updated", "item": item})

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
