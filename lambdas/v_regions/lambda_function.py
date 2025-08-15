

import json
import os
import boto3
import logging
from shared.response_utils import SuccessResponse, ErrorResponse

# Add pydantic for schema validation
from pydantic import BaseModel, ValidationError, Field

# Region details schema
class RegionDetails(BaseModel):
    PK: str = Field(..., description="Region ID, must start with 'region-'")
    SK: str = Field(..., description="Region type or sub-ID")
    name: str
    created_date: str = None
    updated_date: str = None
    metadata: dict = None

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
                region = RegionDetails(**body)
                if not RegionDetails.validate_pk(region.PK):
                    logger.warning("PK does not start with 'region-'")
                    return ErrorResponse.build("PK must start with 'region-'", 400)
            except ValidationError as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid region details: {ve}", 400)
            item = region.dict(exclude_none=True)
            item.setdefault("created_date", context.aws_request_id if context else "")
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
                region = RegionDetails(**body)
                if not RegionDetails.validate_pk(region.PK):
                    logger.warning("PK does not start with 'region-'")
                    return ErrorResponse.build("PK must start with 'region-'", 400)
            except ValidationError as ve:
                logger.warning(f"Schema validation failed: {ve}")
                return ErrorResponse.build(f"Invalid region details: {ve}", 400)
            item = region.dict(exclude_none=True)
            item.setdefault("updated_date", context.aws_request_id if context else "")
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
