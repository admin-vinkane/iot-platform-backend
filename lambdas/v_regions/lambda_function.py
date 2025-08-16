

import json
import os
import boto3
import logging
from shared.response_utils import SuccessResponse, ErrorResponse

# Add pydantic for schema validation
from pydantic import BaseModel, ValidationError, Field

# Region details schema
class RegionDetails(BaseModel):
    @classmethod
    def validate_for_type(cls, data):
        region_type = data.get("region_type")
        required = []
        if region_type == "STATE":
            required = ["region_id", "region_type_parent_id", "region_type", "state_code", "state_name", "state_display_name"]
        elif region_type == "DISTRICT":
            required = ["region_id", "region_type_parent_id", "region_type", "district_code", "district_name", "district_display_name", "parent_id"]
        elif region_type == "MANDAL":
            required = ["region_id", "region_type_parent_id", "region_type", "mandal_code", "mandal_name", "mandal_display_name", "parent_id"]
        elif region_type == "VILLAGE":
            required = ["region_id", "region_type_parent_id", "region_type", "village_code", "village_name", "village_display_name", "parent_id"]
        elif region_type == "HABITATION":
                required = [
                    "region_id", "region_type_parent_id", "region_type",
                    "habitation_code", "habitation_name", "habitation_display_name", "parent_id",
                    "motor_capacity", "tank_capacity"
                ]
        missing = [f for f in required if not data.get(f)]
        if missing:
            raise ValueError(f"Missing required fields for {region_type}: {', '.join(missing)}")
    region_id: str = None
    region_type_parent_id: str = None
    region_type: str = None
    # State fields
    state_code: str = None
    state_name: str = None
    state_display_name: str = None
    # District fields
    district_code: str = None
    district_name: str = None
    district_display_name: str = None
    # Mandal fields
    mandal_code: str = None
    mandal_name: str = None
    mandal_display_name: str = None
    # Village fields
    village_code: str = None
    village_name: str = None
    village_display_name: str = None
    # Habitation fields
    habitation_code: str = None
    habitation_name: str = None
    habitation_display_name: str = None
    motor_capacity: str = None
    tank_capacity: str = None
    # Common fields
    parent_id: str = None
    created_date: str = None
    updated_date: str = None
    created_by: str = None
    updated_by: str = None

    class Config:
        extra = "forbid"  # Disallow extra fields

    @classmethod
    def validate_pk(cls, pk: str) -> bool:
        return pk.startswith("region-")

TABLE = os.environ.get("TABLE_NAME", "v_regions")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def validate_pk_sk(data):
    """Validate PK and SK presence and type."""
    if not isinstance(data, dict):
        return False
    pk = data.get("PK") or data.get("pk")
    sk = data.get("SK") or data.get("sk")
    return isinstance(pk, str) and isinstance(sk, str) and pk and sk

def lambda_handler(event, context):
    logger.error("Lambda handler started - DEBUG logging enabled")
    """
    Lambda handler for v_regions CRUD operations.
    Supports POST, GET, PUT, DELETE methods.
    """
    method = event.get("httpMethod") or event.get("requestContext",{}).get("http",{}).get("method")
    logger.info(f"Received event: {json.dumps(event)}")
    # Debug: Log method and raw body
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

            # Validate schema
            try:
                logger.debug("Validating schema for region_type...")
                RegionDetails.validate_for_type(body)
                logger.debug("Schema validation passed.")
                region = RegionDetails(**body)
                logger.debug(f"RegionDetails object: {region}")
            except (ValidationError, ValueError) as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid region details: {ve}", 400)

            item = region.dict(exclude_none=True)
            logger.debug(f"DynamoDB item to be written: {item}")
            # Value constraints
            allowed_types = {"STATE", "DISTRICT", "MANDAL", "VILLAGE", "HABITATION"}
            if item.get("region_type") not in allowed_types:
                logger.error(f"Invalid region_type: {item.get('region_type')}")
                return ErrorResponse.build(f"Invalid region_type: {item.get('region_type')}", 400)
            # Length/format checks
            import re
            code_fields = [k for k in item if k.endswith("_code")]
            for code in code_fields:
                if not re.match(r"^[A-Z0-9_\-]{2,32}$", str(item[code])):
                    logger.error(f"Invalid code format for {code}: {item[code]}")
                    return ErrorResponse.build(f"Invalid code format for {code}", 400)
            name_fields = [k for k in item if k.endswith("_name") or k.endswith("_display_name")]
            for name in name_fields:
                if not isinstance(item[name], str) or len(item[name]) > 128:
                    logger.error(f"Invalid or too long name for {name}: {item[name]}")
                    return ErrorResponse.build(f"Invalid or too long name for {name}", 400)
            # Date validity
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
            # Default created_by to 'admin' if null, updated_by always to 'admin'
            if not item.get("created_by"):
                item["created_by"] = "admin"
            item["updated_by"] = "admin"
            # Parent existence/referential integrity
            parent_id = item.get("parent_id")
            parent_type = None
            if item["region_type"] == "DISTRICT":
                parent_type = "STATE"
            elif item["region_type"] == "MANDAL":
                parent_type = "DISTRICT"
            elif item["region_type"] == "VILLAGE":
                parent_type = "MANDAL"
            elif item["region_type"] == "HABITATION":
                parent_type = "VILLAGE"
            if parent_id and parent_type:
                parent_key = None
                # Try to find parent by region_id or code
                for k in (f"{parent_type.lower()}_code", "region_id"):
                    if k in item:
                        parent_key = {"region_id": f"region-{parent_id}"} if k == "region_id" else {f"{k}": parent_id}
                        break
                if parent_key:
                    parent_resp = table.scan(
                        FilterExpression=f"region_type = :ptype AND {list(parent_key.keys())[0]} = :pid",
                        ExpressionAttributeValues={":ptype": parent_type, ":pid": parent_id}
                    )
                    if not parent_resp.get("Items"):
                        return ErrorResponse.build(f"Parent {parent_type} with id/code {parent_id} does not exist", 400)
            import getpass
            user = event.get("requestContext", {}).get("authorizer", {}).get("principalId") or getpass.getuser()
            enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"
            try:
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(region_id) AND attribute_not_exists(region_type_parent_id)"
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
            # Validate schema
            try:
                RegionDetails.validate_for_type(body)
                region = RegionDetails(**body)
            except (ValidationError, ValueError) as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid region details: {ve}", 400)
            item = region.dict(exclude_none=True)
            from datetime import datetime
            sysdate = datetime.utcnow().isoformat() + "Z"
            item["updated_date"] = sysdate
            # Default created_by to 'admin' if null, updated_by always to 'admin'
            if not item.get("created_by"):
                item["created_by"] = "admin"
            item["updated_by"] = "admin"
            import getpass
            user = event.get("requestContext", {}).get("authorizer", {}).get("principalId") or getpass.getuser()
            enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"
            try:
                response = table.update_item(
                    Key={"region_id": item["region_id"], "region_type_parent_id": item["region_type_parent_id"]},
                    UpdateExpression="SET " + ", ".join(f"{k} = :{k}" for k in item if k not in ["region_id", "region_type_parent_id"]),
                    ExpressionAttributeValues={f":{k}": v for k, v in item.items() if k not in ["region_id", "region_type_parent_id"]},
                    ConditionExpression="attribute_exists(region_id) AND attribute_exists(region_type_parent_id)",
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
            except Exception as e:
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
            return SuccessResponse.build({"message": "updated", "item": item})

        if method == "DELETE":
            params = event.get("queryStringParameters") or {}
            if not validate_pk_sk(params):
                logger.warning("Missing or invalid PK/SK in DELETE params")
                return ErrorResponse.build("Missing or invalid PK or SK for DELETE", 400)
            pk = params.get("PK") or params.get("pk")
            sk = params.get("SK") or params.get("sk")
            import getpass
            user = event.get("requestContext", {}).get("authorizer", {}).get("principalId") or getpass.getuser()
            enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"
            try:
                table.delete_item(Key={"PK": pk, "SK": sk})
                if enable_audit:
                    logger.info(json.dumps({
                        "action": "delete",
                        "user": user,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "region_id": pk,
                        "region_type_parent_id": sk
                    }))
            except Exception as e:
                logger.error(f"DynamoDB delete_item failed: {e}")
                if enable_audit:
                    logger.info(json.dumps({
                        "action": "error",
                        "user": user,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "region_id": pk,
                        "region_type_parent_id": sk,
                        "error": str(e)
                    }))
                return ErrorResponse.build("Database error", 500)
            return SuccessResponse.build({"message": "deleted"})

        logger.warning(f"Unsupported method: {method}")
        return ErrorResponse.build("Unsupported method", 405)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return ErrorResponse.build("Internal server error", 500)
