import json
import os
import boto3
import logging
from datetime import datetime
import re
from pydantic import BaseModel, ValidationError, Field

# Initialize DynamoDB and logging
TABLE_NAME = os.environ.get("TABLE_NAME", "regions")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Utility response classes
class SuccessResponse:
    @staticmethod
    def build(data):
        return {
            "statusCode": 200,
            "body": json.dumps(data),
            "headers": {"Content-Type": "application/json"}
        }

class ErrorResponse:
    @staticmethod
    def build(message, status_code):
        return {
            "statusCode": status_code,
            "body": json.dumps({"error": message}),
            "headers": {"Content-Type": "application/json"}
        }

# Validate PK and SK
def validate_keys(params):
    if not isinstance(params, dict):
        return False
    pk = params.get("PK")
    sk = params.get("SK")
    return isinstance(pk, str) and isinstance(sk, str) and pk and sk

# Transform item to JSON response
def transform_item_to_json(item):
    if not item:
        return None
    region_type = item.get("Type")
    result = {
        "id": item.get("PK").split("#")[-1] if "#" in item.get("PK", "") else item.get("PK"),
        "type": region_type,
        "code": item.get("Code"),
        "name": item.get("Name"),
        "isActive": True,  # Assuming all items are active
        "createdAt": item.get("created_date"),
        "updatedAt": item.get("updated_date"),
        "createdBy": item.get("created_by"),
        "updatedBy": item.get("updated_by")
    }
    if region_type != "STATE":
        result["stateCode"] = item.get("StateCode")
    if region_type in ["MANDAL", "VILLAGE", "HABITATION"]:
        result["districtCode"] = item.get("DistrictCode")
    if region_type in ["VILLAGE", "HABITATION"]:
        result["mandalCode"] = item.get("MandalCode")
    if region_type == "HABITATION":
        result["villageCode"] = item.get("VillageCode")
        result["path"] = item.get("Path")
    return result

# Pydantic model for validation
class RegionDetails(BaseModel):
    @classmethod
    def validate_for_type(cls, data):
        region_type = data.get("Type")
        required = []
        if region_type == "STATE":
            required = ["PK", "SK", "Type", "Code", "Name"]
        elif region_type == "DISTRICT":
            required = ["PK", "SK", "Type", "Code", "Name", "StateCode"]
        elif region_type == "MANDAL":
            required = ["PK", "SK", "Type", "Code", "Name", "StateCode", "DistrictCode"]
        elif region_type == "VILLAGE":
            required = ["PK", "SK", "Type", "Code", "Name", "StateCode", "DistrictCode", "MandalCode"]
        elif region_type == "HABITATION":
            required = ["PK", "SK", "Type", "Code", "Name", "StateCode", "DistrictCode", "MandalCode", "VillageCode", "Path"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            raise ValueError(f"Missing required fields for {region_type}: {', '.join(missing)}")

    PK: str = None
    SK: str = None
    Type: str = None
    Code: str = None
    Name: str = None
    StateCode: str = None
    DistrictCode: str = None
    MandalCode: str = None
    VillageCode: str = None
    Path: str = None
    created_date: str = None
    updated_date: str = None
    created_by: str = None
    updated_by: str = None

    class Config:
        extra = "forbid"

    @classmethod
    def validate_pk_sk(cls, pk: str, sk: str) -> bool:
        return pk.startswith(("STATE#", "DISTRICT#", "MANDAL#", "VILLAGE#")) and sk.startswith("TYPE#")

# Lambda handler
def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    logger.debug(f"HTTP method: {method}")

    try:
        if method == "POST":
            try:
                body = json.loads(event.get("body", "{}"))
                logger.debug(f"Parsed body: {body}")
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)

            try:
                RegionDetails.validate_for_type(body)
                region = RegionDetails(**body)
                logger.debug(f"RegionDetails object: {region}")
            except (ValidationError, ValueError) as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid region details: {ve}", 400)

            item = region.dict(exclude_none=True)
            allowed_types = {"STATE", "DISTRICT", "MANDAL", "VILLAGE", "HABITATION"}
            if item.get("Type") not in allowed_types:
                logger.error(f"Invalid Type: {item.get('Type')}")
                return ErrorResponse.build(f"Invalid Type: {item.get('Type')}", 400)

            # Validate code format
            if not re.match(r"^[A-Z0-9_]{2,32}$", item.get("Code", "")):
                logger.error(f"Invalid code format: {item.get('Code')}")
                return ErrorResponse.build("Invalid code format", 400)

            # Validate name length
            if not isinstance(item.get("Name"), str) or len(item.get("Name")) > 128:
                logger.error(f"Invalid or too long name: {item.get('Name')}")
                return ErrorResponse.build("Invalid or too long name", 400)

            # Validate dates
            sysdate = datetime.utcnow().isoformat() + "Z"
            for date_field in ("created_date", "updated_date"):
                if item.get(date_field):
                    try:
                        datetime.fromisoformat(item[date_field].replace("Z", ""))
                    except Exception:
                        return ErrorResponse.build(f"Invalid date format for {date_field}", 400)
                else:
                    item[date_field] = sysdate

            if not item.get("created_by"):
                item["created_by"] = "admin"
            item["updated_by"] = "admin"

            # Validate parent existence
            parent_type = None
            parent_pk = None
            if item["Type"] == "DISTRICT":
                parent_type = "STATE"
                parent_pk = f"STATE#{item.get('StateCode')}"
            elif item["Type"] == "MANDAL":
                parent_type = "DISTRICT"
                parent_pk = f"DISTRICT#{item.get('DistrictCode')}"
            elif item["Type"] == "VILLAGE":
                parent_type = "MANDAL"
                parent_pk = f"MANDAL#{item.get('MandalCode')}"
            elif item["Type"] == "HABITATION":
                parent_type = "VILLAGE"
                parent_pk = f"VILLAGE#{item.get('VillageCode')}"

            if parent_type and parent_pk:
                try:
                    parent_resp = table.query(
                        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                        ExpressionAttributeValues={":pk": parent_pk, ":sk": f"TYPE#{parent_type}"}
                    )
                    if not parent_resp.get("Items"):
                        return ErrorResponse.build(f"Parent {parent_type} with PK {parent_pk} does not exist", 400)
                except Exception as e:
                    logger.error(f"Failed to validate parent: {e}")
                    return ErrorResponse.build("Database error", 500)

            # Audit logging
            user = event.get("requestContext", {}).get("authorizer", {}).get("principalId", "admin")
            enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"

            try:
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
                )
                if enable_audit:
                    logger.info(json.dumps({
                        "action": "insert",
                        "user": user,
                        "timestamp": sysdate,
                        "item": item
                    }))
            except Exception as e:
                if "ConditionalCheckFailedException" in str(e):
                    logger.warning("Duplicate item detected, not inserted.")
                    if enable_audit:
                        logger.info(json.dumps({
                            "action": "skip_duplicate",
                            "user": user,
                            "timestamp": sysdate,
                            "item": item
                        }))
                    return ErrorResponse.build("Duplicate item: already exists", 409)
                logger.error(f"DynamoDB put_item failed: {e}")
                if enable_audit:
                    logger.info(json.dumps({
                        "action": "error",
                        "user": user,
                        "timestamp": sysdate,
                        "item": item,
                        "error": str(e)
                    }))
                return ErrorResponse.build("Database error", 500)

            return SuccessResponse.build({"message": "created", "item": transform_item_to_json(item)})

        if method == "GET":
            params = event.get("queryStringParameters") or event.get("pathParameters") or {}
            if validate_keys(params):
                pk = params.get("PK")
                sk = params.get("SK")
                try:
                    r = table.get_item(Key={"PK": pk, "SK": sk})
                    item = r.get("Item")
                    if not item:
                        return ErrorResponse.build("Item not found", 404)
                    return SuccessResponse.build(transform_item_to_json(item))
                except Exception as e:
                    logger.error(f"DynamoDB get_item failed: {e}")
                    return ErrorResponse.build("Database error", 500)
            else:
                try:
                    response = table.query(
                        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                        ExpressionAttributeValues={":pk": "STATE#TS", ":sk": "TYPE#STATE"}
                    )
                    items = response.get("Items", [])
                    return SuccessResponse.build([transform_item_to_json(item) for item in items])
                except Exception as e:
                    logger.error(f"DynamoDB query failed: {e}")
                    return ErrorResponse.build("Database error", 500)

        if method == "PUT":
            try:
                body = json.loads(event.get("body", "{}"))
                logger.debug(f"Parsed body: {body}")
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)

            try:
                RegionDetails.validate_for_type(body)
                region = RegionDetails(**body)
            except (ValidationError, ValueError) as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid region details: {ve}", 400)

            item = region.dict(exclude_none=True)
            sysdate = datetime.utcnow().isoformat() + "Z"
            item["updated_date"] = sysdate
            if not item.get("created_by"):
                item["created_by"] = "admin"
            item["updated_by"] = "admin"

            user = event.get("requestContext", {}).get("authorizer", {}).get("principalId", "admin")
            enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"

            try:
                response = table.update_item(
                    Key={"PK": item["PK"], "SK": item["SK"]},
                    UpdateExpression="SET " + ", ".join(f"{k} = :{k}" for k in item if k not in ["PK", "SK"]),
                    ExpressionAttributeValues={f":{k}": v for k, v in item.items() if k not in ["PK", "SK"]},
                    ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
                    ReturnValues="ALL_NEW"
                )
                if enable_audit:
                    logger.info(json.dumps({
                        "action": "update",
                        "user": user,
                        "timestamp": sysdate,
                        "item": item,
                        "new_values": response.get("Attributes", {})
                    }))
                return SuccessResponse.build({"message": "updated", "item": transform_item_to_json(item)})
            except Exception as e:
                logger.error(f"DynamoDB update_item failed: {e}")
                if enable_audit:
                    logger.info(json.dumps({
                        "action": "error",
                        "user": user,
                        "timestamp": sysdate,
                        "item": item,
                        "error": str(e)
                    }))
                return ErrorResponse.build("Database error", 500)

        if method == "DELETE":
            params = event.get("queryStringParameters") or {}
            if not validate_keys(params):
                logger.warning("Missing or invalid PK/SK in DELETE params")
                return ErrorResponse.build("Missing or invalid PK or SK for DELETE", 400)

            pk = params.get("PK")
            sk = params.get("SK")
            user = event.get("requestContext", {}).get("authorizer", {}).get("principalId", "admin")
            enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"

            try:
                table.delete_item(Key={"PK": pk, "SK": sk})
                if enable_audit:
                    logger.info(json.dumps({
                        "action": "delete",
                        "user": user,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "PK": pk,
                        "SK": sk
                    }))
                return SuccessResponse.build({"message": "deleted"})
            except Exception as e:
                logger.error(f"DynamoDB delete_item failed: {e}")
                if enable_audit:
                    logger.info(json.dumps({
                        "action": "error",
                        "user": user,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "PK": pk,
                        "SK": sk,
                        "error": str(e)
                    }))
                return ErrorResponse.build("Database error", 500)

        logger.warning(f"Unsupported method: {method}")
        return ErrorResponse.build("Unsupported method", 405)

    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return ErrorResponse.build("Internal server error", 500)
