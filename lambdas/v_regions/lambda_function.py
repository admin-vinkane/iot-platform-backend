

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
            required = ["region_id", "region_type_parent_id", "region_type", "habitation_code", "habitation_name", "habitation_display_name", "parent_id"]
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
    Lambda handler for v_regions CRUD operations.
    Supports POST, GET, PUT, DELETE methods.
    """
    method = event.get("httpMethod") or event.get("requestContext",{}).get("http",{}).get("method")
    logger.info(f"Received event: {json.dumps(event)}")
    try:
        if method == "POST":
            body = json.loads(event.get("body", "{}"))
            # Validate schema
            try:
                RegionDetails.validate_for_type(body)
                region = RegionDetails(**body)
            except (ValidationError, ValueError) as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid region details: {ve}", 400)
            item = region.dict(exclude_none=True)
            # Default created_date and updated_date to sysdate if null
            from datetime import datetime
            sysdate = datetime.utcnow().isoformat() + "Z"
            if not item.get("created_date"):
                item["created_date"] = sysdate
            if not item.get("updated_date"):
                item["updated_date"] = sysdate
            # Default created_by to 'admin' if null, updated_by always to 'admin'
            if not item.get("created_by"):
                item["created_by"] = "admin"
            item["updated_by"] = "admin"
            try:
                table.put_item(Item=item)
            except Exception as e:
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
            try:
                table.put_item(Item=item)
            except Exception as e:
                logger.error(f"DynamoDB put_item failed: {e}")
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
