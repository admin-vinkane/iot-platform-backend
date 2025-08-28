import json
import os
import boto3
import logging
from datetime import datetime
import re
from shared.response_utils import SuccessResponse, ErrorResponse
from pydantic import BaseModel, ValidationError, Field

# Initialize DynamoDB and logging
TABLE_NAME = os.environ.get("TABLE_NAME", "regions")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

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
    region_type = item.get("RegionType")
    result = {
        "id": item.get("PK").split("#")[-1] if "#" in item.get("PK", "") else item.get("PK"),
        "type": region_type,
        "code": item.get("RegionCode"),
        "name": item.get("RegionName"),
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
        region_type = data.get("RegionType")
        required = []
        if region_type == "STATE":
            required = ["PK", "SK", "RegionType", "RegionCode", "RegionName"]
        elif region_type == "DISTRICT":
            required = ["PK", "SK", "RegionType", "RegionCode", "RegionName", "StateCode"]
        elif region_type == "MANDAL":
            required = ["PK", "SK", "RegionType", "RegionCode", "RegionName", "StateCode", "DistrictCode"]
        elif region_type == "VILLAGE":
            required = ["PK", "SK", "RegionType", "RegionCode", "RegionName", "StateCode", "DistrictCode", "MandalCode"]
        elif region_type == "HABITATION":
            required = ["PK", "SK", "RegionType", "RegionCode", "RegionName", "StateCode", "DistrictCode", "MandalCode", "VillageCode", "Path"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            raise ValueError(f"Missing required fields for {region_type}: {', '.join(missing)}")

    PK: str = None
    SK: str = None
    RegionType: str = None
    RegionCode: str = None
    RegionName: str = None
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
        return pk.startswith(("STATE#", "DISTRICT#", "MANDAL#", "VILLAGE#")) and sk.startswith(("STATE#", "DISTRICT#", "MANDAL#", "VILLAGE#", "HABITATION#"))

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
            if item.get("RegionType") not in allowed_types:
                logger.error(f"Invalid Type: {item.get('RegionType')}")
                return ErrorResponse.build(f"Invalid Type: {item.get('RegionType')}", 400)

            # Validate code format
            if not re.match(r"^[A-Z0-9_]{2,32}$", item.get("RegionCode", "")):
                logger.error(f"Invalid code format: {item.get('RegionCode')}")
                return ErrorResponse.build("Invalid code format", 400)

            # Validate name length
            if not isinstance(item.get("RegionName"), str) or len(item.get("RegionName")) > 128:
                logger.error(f"Invalid or too long name: {item.get('RegionName')}")
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
            # parent check
            region_type = item.get("RegionType")
            region_code = item.get("RegionCode")
            region_name = item.get("RegionName")
            state_code = item.get("StateCode")
            district_code = item.get("DistrictCode")
            mandal_code = item.get("MandalCode")
            village_code = item.get("VillageCode")
            path = item.get("Path")
            # Validate required fields based on RegionType
            if not region_type or not region_code or not region_name:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'RegionType, RegionCode, and RegionName are required'})
                }
            
            # Define PK, SK, and parent check based on RegionType
            if region_type == 'STATE':
                pk = f"STATE#{region_code}"
                sk = f"STATE#{region_code}"
                parent_check = None  # No parent for State
            elif region_type == 'DISTRICT':
                if not state_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode is required for DISTRICT'})
                    }
                pk = f"STATE#{state_code}"
                sk = f"DISTRICT#{region_code}"
                parent_check = {'PK': pk, 'SK': f"STATE#{state_code}"}
            elif region_type == 'MANDAL':
                if not state_code or not district_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode and DistrictCode are required for MANDAL'})
                    }
                pk = f"DISTRICT#{district_code}"
                sk = f"MANDAL#{region_code}"
                parent_check = {'PK': f"STATE#{state_code}", 'SK': f"DISTRICT#{district_code}"}
            elif region_type == 'VILLAGE':
                if not state_code or not district_code or not mandal_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode, DistrictCode, and MandalCode are required for VILLAGE'})
                    }
                pk = f"MANDAL#{mandal_code}"
                sk = f"VILLAGE#{region_code}"
                parent_check = {'PK': f"DISTRICT#{district_code}", 'SK': f"MANDAL#{mandal_code}"}
            elif region_type == 'HABITATION':
                if not state_code or not district_code or not mandal_code or not village_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode, DistrictCode, MandalCode, and VillageCode are required for HABITATION'})
                    }
                pk = f"VILLAGE#{village_code}"
                sk = f"HABITATION#{region_code}"
                parent_check = {'PK': f"MANDAL#{mandal_code}", 'SK': f"VILLAGE#{village_code}"}
                if not path:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'Path is required for HABITATION'})
                    }
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid RegionType. Must be STATE, DISTRICT, MANDAL, VILLAGE, or HABITATION'})
                }
        
        # Check if parent exists (if applicable)
        if parent_check:
            try:
                response = table.get_item(Key=parent_check)
                if 'Item' not in response:
                    return ErrorResponse.build(f"Parent record {parent_check['SK']} does not exist", 400)
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
                    # Default list: query items under a sample PK, using SK prefix for types
                    response = table.query(
                        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                        ExpressionAttributeValues={":pk": "STATE#TS", ":sk": "STATE#"}
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
