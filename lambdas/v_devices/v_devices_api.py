
import json
import os
import boto3
import logging
from shared.response_utils import SuccessResponse, ErrorResponse
from pydantic import BaseModel, ValidationError, Field
from datetime import datetime
import getpass
from typing import Optional, List
from boto3.dynamodb.conditions import Key

def validate_pk_sk(data):
    if not isinstance(data, dict):
        return False
    pk = data.get("PK") or data.get("pk")
    sk = data.get("SK") or data.get("sk")
    return isinstance(pk, str) and isinstance(sk, str) and pk and sk




ALLOWED_RECORD_TYPES = {"DETAILS", "CONFIG", "REPAIR", "STATS"}

class DeviceDetails(BaseModel):
    PK: str = Field(..., description="Device ID, must start with 'device-'")
    SK: str = Field(..., description="Record type: DETAILS, CONFIG, REPAIR, STATS")
    name: Optional[str] = None
    created_date: Optional[str] = None
    updated_date: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[dict] = None
    created_by: Optional[str] = None
    is_deleted: Optional[bool] = False

def build_response(success, data=None, error=None):
    return {
        "success": success,
        "data": data,
        "error": error
    }


def lambda_handler(event, context):
    logger = logging.getLogger()
    log_level = os.environ.get("LOG_LEVEL", "DEBUG").upper()
    logger.setLevel(getattr(logging, log_level, logging.DEBUG))
    TABLE = os.environ.get("TABLE_NAME", "v_devices")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE)
    print("=== LAMBDA HANDLER STARTED ===")
    logger.error("Lambda handler started - DEBUG logging enabled")
    method = event.get("httpMethod") or event.get("requestContext",{}).get("http",{}).get("method")
    logger.info(f"Received event: {json.dumps(event)}")
    logger.debug(f"HTTP method: {method}")
    logger.debug(f"Raw event body: {event.get('body')}")
    user = event.get("requestContext", {}).get("authorizer", {}).get("principalId") or getpass.getuser()
    enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"
    # main handler logic follows
        # List/query endpoint: GET /devices?PK=...&record_type=...
    if method == "GET" and (event.get("rawPath", "").endswith("/devices") or event.get("resource", "").endswith("/devices")):
            params = event.get("queryStringParameters") or {}
            pk = params.get("PK") or params.get("pk")
            record_type = params.get("record_type")
            # main handler logic follows
            if method == "GET" and (event.get("rawPath", "").endswith("/devices") or event.get("resource", "").endswith("/devices")):
                params = event.get("queryStringParameters") or {}
                pk = params.get("PK") or params.get("pk")
                record_type = params.get("record_type")
                if not pk:
                    return build_response(False, error="Missing PK (device_id) for list query")
                key_cond = Key("device_id").eq(pk)
                if record_type:
                    if record_type not in ALLOWED_RECORD_TYPES:
                        return build_response(False, error=f"Invalid record_type: {record_type}")
                    key_cond = key_cond & Key("record_type_timestamp").begins_with(f"{record_type}#")
                try:
                    response = table.query(
                        KeyConditionExpression=key_cond,
                        FilterExpression="attribute_not_exists(is_deleted) OR is_deleted = :f",
                        ExpressionAttributeValues={":f": False}
                    )
                    items = response.get("Items", [])
                except Exception as e:
                    logger.error(f"DynamoDB query failed: {e}")
                    return build_response(False, error="Database error")
                return build_response(True, data=items)

            elif method == "POST":
                try:
                    body = json.loads(event.get("body", "{}"))
                except Exception as e:
                    logger.error(f"Failed to parse body: {e}")
                    return build_response(False, error=f"Malformed JSON body: {e}")
                try:
                    device = DeviceDetails(**body)
                except (ValidationError, ValueError) as ve:
                    logger.warning(f"Schema validation failed: {ve}")
                    return build_response(False, error=f"Invalid device details: {ve}")
                item = device.dict(exclude_none=True)
                record_type = item.get("SK")
                if record_type not in ALLOWED_RECORD_TYPES:
                    return build_response(False, error=f"Invalid record_type: {record_type}")
                if not record_type:
                    return build_response(False, error="Missing SK (record type) in request")
                sysdate = datetime.utcnow().isoformat() + "Z"
                version_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                for date_field in ("created_date", "updated_date"):
                    if item.get(date_field):
                        try:
                            datetime.fromisoformat(item[date_field].replace("Z", ""))
                        except Exception:
                            return build_response(False, error=f"Invalid date format for {date_field}")
                    else:
                        item[date_field] = sysdate
                if not item.get("status"):
                    item["status"] = "active"
                if not item.get("metadata"):
                    item["metadata"] = {}
                if not item.get("created_by"):
                    item["created_by"] = user
                item["updated_by"] = user
                db_item = dict(item)
                db_item["device_id"] = db_item.pop("PK")
                db_item["record_type_timestamp"] = f"{record_type}#{version_str}"
                db_item["record_type"] = record_type
                db_item["is_deleted"] = False
                try:
                    table.put_item(
                        Item=db_item,
                        ConditionExpression="attribute_not_exists(device_id) AND attribute_not_exists(record_type_timestamp)"
                    )
                    if enable_audit:
                        logger.info(json.dumps({
                            "action": "insert",
                            "user": user,
                            "timestamp": sysdate,
                            "item": db_item
                        }))
                except Exception as e:
                    if "ConditionalCheckFailedException" in str(e):
                        logger.warning("Duplicate item detected, not inserted.")
                        if enable_audit:
                            logger.info(json.dumps({
                                "action": "skip_duplicate",
                                "user": user,
                                "timestamp": sysdate,
                                "item": db_item
                            }))
                        return build_response(False, error="Duplicate item: already exists")
                    logger.error(f"DynamoDB put_item failed: {e}")
                    if enable_audit:
                        logger.info(json.dumps({
                            "action": "error",
                            "user": user,
                            "timestamp": sysdate,
                            "item": db_item,
                            "error": str(e)
                        }))
                    return build_response(False, error="Database error")
                return build_response(True, data={"message": "created", "item": db_item})

            elif method == "GET":
                params = event.get("queryStringParameters") or event.get("pathParameters") or {}
                if not validate_pk_sk(params):
                    logger.warning("Missing or invalid PK/SK in GET params")
                    return build_response(False, error="Missing or invalid PK or SK for GET")
                pk = params.get("PK") or params.get("pk")
                sk = params.get("SK") or params.get("sk")
                try:
                    r = table.get_item(Key={"device_id": pk, "record_type_timestamp": sk})
                except Exception as e:
                    logger.error(f"DynamoDB get_item failed: {e}")
                    return build_response(False, error="Database error")
                item = r.get("Item")
                if item and not item.get("is_deleted", False):
                    return build_response(True, data=item)
                else:
                    return build_response(False, error="Item not found or deleted")

            elif method == "PUT":
                try:
                    body = json.loads(event.get("body", "{}"))
                except Exception as e:
                    logger.error(f"Failed to parse body: {e}")
                    return build_response(False, error=f"Malformed JSON body: {e}")
                try:
                    device = DeviceDetails(**body)
                except (ValidationError, ValueError) as ve:
                    logger.warning(f"Schema validation failed: {ve}")
                    return build_response(False, error=f"Invalid device details: {ve}")
                item = device.dict(exclude_none=True)
                record_type = item.get("SK")
                if record_type not in ALLOWED_RECORD_TYPES:
                    return build_response(False, error=f"Invalid record_type: {record_type}")
                if not record_type:
                    return build_response(False, error="Missing SK (record type) in request")
                sysdate = datetime.utcnow().isoformat() + "Z"
                version_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                item["updated_date"] = sysdate
                if not item.get("status"):
                    item["status"] = "active"
                if not item.get("metadata"):
                    item["metadata"] = {}
                if not item.get("created_by"):
                    item["created_by"] = user
                item["updated_by"] = user
                db_item = dict(item)
                db_item["device_id"] = db_item.pop("PK")
                db_item["record_type_timestamp"] = f"{record_type}#{version_str}"
                db_item["record_type"] = record_type
                db_item["is_deleted"] = False
                try:
                    response = table.update_item(
                        Key={"device_id": db_item["device_id"], "record_type_timestamp": db_item["record_type_timestamp"]},
                        UpdateExpression="SET " + ", ".join(f"{k} = :{k}" for k in db_item if k not in ["device_id", "record_type_timestamp"]),
                        ExpressionAttributeValues={f":{k}": v for k, v in db_item.items() if k not in ["device_id", "record_type_timestamp"]},
                        ConditionExpression="attribute_exists(device_id) AND attribute_exists(record_type_timestamp)",
                        ReturnValues="ALL_NEW"
                    )
                    if enable_audit:
                        logger.info(json.dumps({
                            "action": "update",
                            "user": user,
                            "timestamp": sysdate,
                            "item": db_item,
                            "new_values": response.get("Attributes", {})
                        }))
                except Exception as e:
                    logger.error(f"DynamoDB update_item failed: {e}")
                    return build_response(False, error="Database error")
                return build_response(True, data={"message": "updated", "item": db_item})

            elif method == "DELETE":
                params = event.get("queryStringParameters") or {}
                if not validate_pk_sk(params):
                    logger.warning("Missing or invalid PK/SK in DELETE params")
                    return build_response(False, error="Missing or invalid PK or SK for DELETE")
                pk = params.get("PK") or params.get("pk")
                sk = params.get("SK") or params.get("sk")
                try:
                    # Soft delete: set is_deleted = True
                    table.update_item(
                        Key={"device_id": pk, "record_type_timestamp": sk},
                        UpdateExpression="SET is_deleted = :t",
                        ExpressionAttributeValues={":t": True},
                        ConditionExpression="attribute_exists(device_id) AND attribute_exists(record_type_timestamp)"
                    )
                    if enable_audit:
                        logger.info(json.dumps({
                            "action": "delete",
                            "user": user,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "device_id": pk,
                            "record_type_timestamp": sk
                        }))
                except Exception as e:
                    logger.error(f"DynamoDB soft delete failed: {e}")
                    return build_response(False, error="Database error")
                return build_response(True, data={"message": "deleted"})

            else:
                logger.warning(f"Unsupported method: {method}")
                return build_response(False, error="Unsupported method")
