import json
import os
import boto3
import logging
from datetime import datetime
from decimal import Decimal
import decimal
from pydantic import BaseModel, ValidationError, Field
from botocore.exceptions import ClientError

# Placeholder for SuccessResponse and ErrorResponse
class SuccessResponse:
    @staticmethod
    def build(data, status_code=200):
        return {
            "statusCode": status_code,
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

TABLE_NAME = os.environ.get("TABLE_NAME", "v_devices_dev")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

class DeviceMeta(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    DeviceName: str
    DeviceType: str
    SerialNumber: str
    Status: str
    Location: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None

    class Config:
        extra = "forbid"

class DeviceConfig(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    ConfigVersion: str
    ConfigData: dict
    AppliedBy: str
    Status: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None

    class Config:
        extra = "forbid"

class DeviceRepair(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    RepairId: str
    Description: str
    Cost: Decimal = Field(ge=0)
    Technician: str
    Status: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None

    class Config:
        extra = "forbid"
        arbitrary_types_allowed = True

class DeviceInstall(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    InstallId: str
    Location: dict
    Installer: str
    Notes: str
    Status: str
    Warranty: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None

    class Config:
        extra = "forbid"

class DeviceRuntime(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    Metrics: dict
    Events: list
    Status: str
    EntityType: str
    EventDate: str = None
    ttl: int = None
    CreatedDate: str = None
    UpdatedDate: str = None

    class Config:
        extra = "forbid"

class SimMeta(BaseModel):
    PK: str
    SK: str
    SIMId: str
    MobileNumber: str
    Provider: str
    Plan: str
    DataUsage: Decimal = Field(ge=0)
    AssignedDeviceId: str
    Status: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None

    class Config:
        extra = "forbid"
        arbitrary_types_allowed = True

class SimAssoc(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    SIMId: str
    Provider: str
    Status: str
    EntityType: str
    CreatedDate: str = None
    UpdatedDate: str = None

    class Config:
        extra = "forbid"

ENTITY_MODEL_MAP = {
    "DEVICE": DeviceMeta,
    "CONFIG": DeviceConfig,
    "REPAIR": DeviceRepair,
    "INSTALL": DeviceInstall,
    "RUNTIME": DeviceRuntime,
    "SIM": SimMeta,
    "SIM_ASSOC": SimAssoc
}

def lambda_handler(event, context):
    method = event.get("httpMethod")
    if method == "POST":
        try:
            item = json.loads(event.get("body", "{}"))
            if not isinstance(item, dict):
                raise ValueError("POST body must be a dict")
            item = convert_floats_to_decimal(item)
        except Exception as e:
            logger.error(f"Failed to parse body: {e}")
            return ErrorResponse.build(f"Malformed JSON body: {e}", 400)

        entity_type = item.get("EntityType")
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return ErrorResponse.build(f"Unknown EntityType: {entity_type}", 400)

        # Derive PK and SK
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for update", 400)

        # Remove PK and SK from update fields
        update_fields = {k: v for k, v in item.items() if k not in ["PK", "SK"]}

        # Build UpdateExpression and ExpressionAttributeValues
        reserved_keywords = {"Status", "Location"}  # <-- Add Location here
        update_expr_parts = []
        expr_attr_names = {}
        expr_attr_vals = {}

        for k, v in update_fields.items():
            if k in reserved_keywords:
                update_expr_parts.append(f"#attr_{k} = :{k}")
                expr_attr_names[f"#attr_{k}"] = k
            else:
                update_expr_parts.append(f"{k} = :{k}")
            expr_attr_vals[f":{k}"] = v

        update_expr = "SET " + ", ".join(update_expr_parts)

        try:
            table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_attr_vals,
                ExpressionAttributeNames=expr_attr_names if expr_attr_names else None,
                ReturnValues="ALL_NEW"
            )
            return SuccessResponse.build({"updated": item})
        except Exception as e:
            logger.error(f"Update error: {str(e)}")
            return ErrorResponse.build(f"Update error: {str(e)}", 500)
    
    elif method == "GET":
        params = event.get("queryStringParameters") or {}
        device_type = params.get("DeviceType")
        status = params.get("Status")

        filter_expression = []
        expression_values = {}

        if device_type:
            filter_expression.append("DeviceType = :dt")
            expression_values[":dt"] = device_type
        if status:
            filter_expression.append("Status = :st")
            expression_values[":st"] = status

        filter_expression.append("EntityType = :et")
        expression_values[":et"] = "DEVICE"

        try:
            if filter_expression:
                from boto3.dynamodb.conditions import Attr
                fe = Attr("EntityType").eq("DEVICE")
                if device_type:
                    fe = fe & Attr("DeviceType").eq(device_type)
                if status:
                    fe = fe & Attr("Status").eq(status)
                response = table.scan(
                    FilterExpression=fe
                )
            else:
                response = table.scan(
                    FilterExpression="EntityType = :et",
                    ExpressionAttributeValues={":et": "DEVICE"}
                )

            items = response.get("Items", [])
            for item in items:
                device_id = item.get("DeviceId")
                if device_id:
                    try:
                        repair_response = table.query(
                            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                            ExpressionAttributeValues={
                                ":pk": f"DEVICE#{device_id}",
                                ":sk": "REPAIR#"
                            }
                        )
                        repair_items = [simplify(r) for r in repair_response.get("Items", [])]
                        logger.info(f"***** repair_items: {repair_items}")
                        item["RepairHistory"] = repair_items
                    except Exception as e:
                        logger.error(f"Error fetching repair history for {device_id}: {str(e)}")
                        item["RepairHistory"] = []
            
            return SuccessResponse.build(transform_items_to_json(items))
        except Exception as e:
            logger.error(f"DynamoDB scan error: {str(e)}")
            return ErrorResponse.build(f"DynamoDB scan error: {str(e)}", 500)

    elif method == "PUT":
        try:
            item = json.loads(event.get("body", "{}"))
            if not isinstance(item, dict):
                raise ValueError("PUT body must be a dict")
            item = convert_floats_to_decimal(item)
        except Exception as e:
            logger.error(f"Failed to parse body: {e}")
            return ErrorResponse.build(f"Malformed JSON body: {e}", 400)

        entity_type = item.get("EntityType")
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return ErrorResponse.build(f"Unknown EntityType: {entity_type}", 400)

        # Derive PK and SK
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for update", 400)

        # Remove PK and SK from update fields
        update_fields = {k: v for k, v in item.items() if k not in ["PK", "SK"]}

        # Build UpdateExpression and ExpressionAttributeValues
        reserved_keywords = {"Status", "Location"}  # <-- Add Location here
        update_expr_parts = []
        expr_attr_names = {}
        expr_attr_vals = {}

        for k, v in update_fields.items():
            if k in reserved_keywords:
                update_expr_parts.append(f"#attr_{k} = :{k}")
                expr_attr_names[f"#attr_{k}"] = k
            else:
                update_expr_parts.append(f"{k} = :{k}")
            expr_attr_vals[f":{k}"] = v

        update_expr = "SET " + ", ".join(update_expr_parts)

        try:
            table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_attr_vals,
                ExpressionAttributeNames=expr_attr_names if expr_attr_names else None,
                ReturnValues="ALL_NEW"
            )
            return SuccessResponse.build({"updated": item})
        except Exception as e:
            logger.error(f"Update error: {str(e)}")
            return ErrorResponse.build(f"Update error: {str(e)}", 500)
        
    elif method == "DELETE":
        params = event.get("queryStringParameters") or {}
        entity_type = params.get("EntityType")
        if not entity_type:
            return ErrorResponse.build("EntityType is required for delete", 400)

        # Build item dict from query params for PK/SK derivation
        item = {k: v for k, v in params.items()}
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for delete", 400)
        try:
            table.delete_item(
                Key={
                    "PK": pk,
                    "SK": sk
                }
            )
            return SuccessResponse.build({"deleted": {"PK": pk, "SK": sk}})
        except Exception as e:
            logger.error(f"Delete error: {str(e)}")
            return ErrorResponse.build(f"Delete error: {str(e)}", 500)

    return ErrorResponse.build("Method not allowed", 405)

def convert_floats_to_decimal(obj):
    """
    Recursively convert all float values in a dict or list to decimal.Decimal.
    """
    if isinstance(obj, float):
        logger.debug(f"Converting float to Decimal: {obj}")
        return decimal.Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(v) for v in obj]
    else:
        return obj

def simplify(item):
    """
    Recursively convert DynamoDB item values to native Python types,
    including Decimal to int/float for JSON serialization.
    """
    def simplify_value(v):
        if isinstance(v, Decimal):
            return int(v) if v == int(v) else float(v)
        if isinstance(v, dict):
            return {k: simplify_value(nv) for k, nv in v.items()}
        if isinstance(v, list):
            return [simplify_value(x) for x in v]
        return v

    return {k: simplify_value(v) for k, v in item.items()}

def transform_items_to_json(items):
    """Transform a list of DynamoDB items to a list of JSON objects for devices."""
    if not items:
        return []

    # Build a lookup for InstallId by DeviceId
    install_lookup = {}
    for item in items:
        item = simplify(item)
        if item.get("EntityType") == "INSTALL" and item.get("DeviceId") and item.get("InstallId"):
            install_lookup[item["DeviceId"]] = item["InstallId"]

    results = []
    for item in items:
        item = simplify(item)
        if not item or not isinstance(item, dict):
            continue

        entity_type = item.get("EntityType")
        if not entity_type:
            continue

        result = {
            "id": item.get("PK").split("#")[-1] if "#" in item.get("PK", "") else item.get("PK"),
            "type": entity_type,
            "deviceId": item.get("DeviceId"),
            "deviceName": item.get("DeviceName"),
            "deviceType": item.get("DeviceType"),
            "serialNumber": item.get("SerialNumber"),
            "status": item.get("Status"),
            "currentLocation": item.get("Location"),
            "createdAt": item.get("CreatedDate"),
            "updatedAt": item.get("UpdatedDate"),
            "RepairHistory": item.get("RepairHistory"),
            "InstallId": install_lookup.get(item.get("DeviceId")),  # <-- Add InstallId here
            "PK": item.get("PK"),
            "SK": item.get("SK")
        }
        if entity_type == "CONFIG":
            result["configVersion"] = item.get("ConfigVersion")
            result["configData"] = item.get("ConfigData")
            result["appliedBy"] = item.get("AppliedBy")
        elif entity_type == "REPAIR":
            result["repairId"] = item.get("RepairId")
            result["description"] = item.get("Description")
            result["cost"] = item.get("Cost")
            result["technician"] = item.get("Technician")
        elif entity_type == "INSTALL":
            result["installId"] = item.get("InstallId")
            result["installer"] = item.get("Installer")
            result["notes"] = item.get("Notes")
            result["warranty"] = item.get("Warranty")
        elif entity_type == "RUNTIME":
            result["metrics"] = item.get("Metrics")
            result["events"] = item.get("Events")
            result["eventDate"] = item.get("EventDate")
            result["ttl"] = item.get("ttl")
        elif entity_type == "SIM":
            result["simId"] = item.get("SIMId")
            result["mobileNumber"] = item.get("MobileNumber")
            result["provider"] = item.get("Provider")
            result["plan"] = item.get("Plan")
            result["dataUsage"] = item.get("DataUsage")
            result["assignedDeviceId"] = item.get("AssignedDeviceId")
        elif entity_type == "SIM_ASSOC":
            result["simId"] = item.get("SIMId")
            result["provider"] = item.get("Provider")

        results.append(result)

    return results

def derive_pk_sk(item):
    """
    Derive PK and SK values based on EntityType and other fields.
    """
    entity_type = item.get("EntityType")
    if entity_type == "DEVICE":
        pk = f'DEVICE#{item.get("DeviceId")}'
        sk = "META"
    elif entity_type == "CONFIG":
        pk = f'DEVICE#{item.get("DeviceId")}'
        version = item.get("ConfigVersion", "V1.0")
        created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
        sk = f'CONFIG#{version}#{created}'
    elif entity_type == "REPAIR":
        pk = f'DEVICE#{item.get("DeviceId")}'
        repair_id = item.get("RepairId", "REP")
        created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
        sk = f'REPAIR#{repair_id}#{created[:10]}'
    elif entity_type == "INSTALL":
        pk = f'DEVICE#{item.get("DeviceId")}'
        install_id = item.get("InstallId", "INS")
        created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
        sk = f'INSTALL#{install_id}#{created[:10]}'
    elif entity_type == "RUNTIME":
        pk = f'DEVICE#{item.get("DeviceId")}'
        event_date = item.get("EventDate", datetime.utcnow().isoformat() + "Z")
        sk = f'RUNTIME#{event_date}'
    elif entity_type == "SIM":
        pk = f'SIM#{item.get("SIMId")}'
        sk = "META"
    elif entity_type == "SIM_ASSOC":
        pk = f'DEVICE#{item.get("DeviceId")}'
        sim_id = item.get("SIMId", "SIM")
        sk = f'SIM_ASSOC#{sim_id}'
    else:
        pk = None
        sk = None
    return pk, sk