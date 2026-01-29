import json
import os
import boto3
import logging
from decimal import Decimal
from pydantic import BaseModel, ValidationError, Field

# DynamoDB setup
TABLE_NAME = os.environ.get("TABLE_NAME", "v_simcards_dev")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ----------------------------
# Pydantic model
# ----------------------------
class SimCardDetails(BaseModel):
    PK: str
    SK: str
    entityType: str = "SIMCARD"
    simCardNumber: str
    mobileNumber: str
    provider: str
    planType: str
    simType: str
    monthlyDataLimit: int
    status: str = "active"
    activationDate: str | None = None
    currentDataUsage: int = 0
    purchaseCost: int | None = None
    monthlyCharges: int | None = None
    isRoamingEnabled: bool = False
    changeHistory: list = Field(default_factory=list)
    linkedDeviceId: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
    createdBy: str | None = None
    updatedBy: str | None = None

    class Config:
        extra = "forbid"

# ----------------------------
# Helpers
# ----------------------------
def simplify(item):
    def simplify_value(v):
        if isinstance(v, Decimal):
            return int(v) if v == int(v) else float(v)
        if isinstance(v, dict):
            return {k: simplify_value(nv) for k, nv in v.items()}
        if isinstance(v, list):
            return [simplify_value(x) for x in v]
        return v

    return {k: simplify_value(v) for k, v in item.items()}


def build_response(body, status_code=200):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    logger.info(json.dumps(event))

    # Try multiple ways to extract the HTTP method (HTTP API 2.0 compatibility)
    method = (
        event.get("httpMethod") or 
        event.get("requestContext", {}).get("http", {}).get("method") or
        event.get("requestContext", {}).get("httpMethod")
    )
    
    # Extract path (HTTP API 2.0 uses rawPath, REST API uses path)
    path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path") or ""
    path_parameters = event.get("pathParameters") or {}

    # Log for debugging
    logger.info(f"Extracted method: {method}, path: {path}, pathParameters: {path_parameters}")

    if not method:
        logger.error("Could not extract HTTP method from event")
        return build_response({"error": "Could not determine HTTP method from request"}, 400)

    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return build_response({"message": "CORS preflight successful"}, 200)

    try:
        # ----------------------------
        # GET /simcards
        # ----------------------------
        if method == "GET" and not path_parameters:
            response = table.scan()
            items = response.get("Items", [])
            return build_response([simplify(item) for item in items])

        # ----------------------------
        # GET /simcards/{id}
        # ----------------------------
        elif method == "GET" and "id" in path_parameters:
            sim_id = path_parameters["id"]
            pk = f"SIMCARD#{sim_id}"
            sk = "ENTITY#SIMCARD"

            response = table.get_item(Key={"PK": pk, "SK": sk})
            item = response.get("Item")

            if not item:
                return build_response({"error": "SIM card not found"}, 404)

            return build_response(simplify(item))

        # ----------------------------
        # POST /simcards
        # ----------------------------
        elif method == "POST" and ("/simcards" in path or path == "/"):
            if not event.get("body"):
                return build_response({"error": "Missing request body"}, 400)

            try:
                data = json.loads(event["body"])
                sim = SimCardDetails(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Validation error: {e}")
                return build_response({"error": f"Invalid SIM card data: {str(e)}"}, 400)

            pk = f"SIMCARD#{sim.PK}"
            sk = "ENTITY#SIMCARD"

            item = sim.dict()
            item["PK"] = pk
            item["SK"] = sk
            
            # Set timestamps and by fields
            from datetime import datetime
            timestamp = datetime.utcnow().isoformat() + "Z"
            if not item.get("createdAt"):
                item["createdAt"] = timestamp
            if not item.get("updatedAt"):
                item["updatedAt"] = timestamp
            if item.get("createdBy") and not item.get("updatedBy"):
                item["updatedBy"] = item["createdBy"]

            table.put_item(Item=item)
            return build_response(simplify(item), 201)

        # ----------------------------
        # PUT /simcards/{id}
        # ----------------------------
        elif method == "PUT" and "id" in path_parameters:
            sim_id = path_parameters["id"]

            if not event.get("body"):
                return build_response({"error": "Missing request body"}, 400)

            try:
                data = json.loads(event["body"])
                sim = SimCardDetails(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Validation error: {e}")
                return build_response({"error": f"Invalid SIM card data: {str(e)}"}, 400)

            pk = f"SIMCARD#{sim_id}"
            sk = "ENTITY#SIMCARD"

            # Fetch existing item to track changes
            existing_response = table.get_item(Key={"PK": pk, "SK": sk})
            if "Item" not in existing_response:
                return build_response({"error": "SIM card not found"}, 404)
            
            existing_item = existing_response["Item"]

            item = sim.dict()
            item["PK"] = pk
            item["SK"] = sk
            
            # Set updatedAt and updatedBy
            from datetime import datetime
            timestamp = datetime.utcnow().isoformat() + "Z"
            item["updatedAt"] = timestamp
            if item.get("createdBy") and not item.get("updatedBy"):
                item["updatedBy"] = item["createdBy"]

            # Track changes for SIM cards
            changes = {}
            trackable_fields = ["status", "planType", "monthlyDataLimit", "monthlyCharges", 
                              "isRoamingEnabled", "provider", "mobileNumber", "simType"]
            
            for field in trackable_fields:
                old_value = existing_item.get(field)
                new_value = item.get(field)
                # Only track if field is being updated and value changed
                if field in item and old_value != new_value:
                    changes[field] = {
                        "from": simplify(old_value) if isinstance(old_value, (dict, list)) else old_value,
                        "to": simplify(new_value) if isinstance(new_value, (dict, list)) else new_value
                    }

            # Add changeHistory if there are changes
            if changes:
                history_entry = {
                    "timestamp": timestamp,
                    "action": "UPDATE",
                    "changes": changes,
                    "updatedBy": item.get("updatedBy", "system")
                }
                
                # Get existing changeHistory and append
                existing_history = existing_item.get("changeHistory", [])
                item["changeHistory"] = existing_history + [history_entry]
                
                logger.info(f"Recording SIM changes: {changes}")
            else:
                # Keep existing history if no changes
                item["changeHistory"] = existing_item.get("changeHistory", [])

            table.put_item(Item=item)
            return build_response(simplify(item))

        # ----------------------------
        # DELETE /simcards/{id}
        # ----------------------------
        elif method == "DELETE" and "id" in path_parameters:
            sim_id = path_parameters["id"]
            pk = f"SIMCARD#{sim_id}"
            sk = "ENTITY#SIMCARD"

            if "Item" not in table.get_item(Key={"PK": pk, "SK": sk}):
                return build_response({"error": "SIM card not found"}, 404)

            table.delete_item(Key={"PK": pk, "SK": sk})
            return build_response({"message": "SIM card deleted"})

        return build_response({"error": "Unsupported method"}, 405)

    except Exception:
        logger.exception("Unhandled error")
        return build_response({"error": "Internal server error"}, 500)
