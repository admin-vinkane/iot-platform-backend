import json
import os
import boto3
import logging
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ValidationError, Field
from shared.response_utils import SuccessResponse, ErrorResponse


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
    # CreatedDate: str
    # UpdatedDate: str
    EntityType: str

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
    # CreatedDate: str
    # UpdatedDate: str
    EntityType: str

    class Config:
        extra = "forbid"

class DeviceRepair(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    RepairId: str
    Description: str
    Cost: float
    Technician: str
    Status: str
    # CreatedDate: str
    # UpdatedDate: str
    EntityType: str

    class Config:
        extra = "forbid"

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
    # CreatedDate: str
    # UpdatedDate: str
    EntityType: str

    class Config:
        extra = "forbid"

class DeviceRuntime(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    Metrics: dict
    Events: list
    Status: str
    # CreatedDate: str
    # UpdatedDate: str
    EntityType: str
    EventDate: str = None
    ttl: int = None

    class Config:
        extra = "forbid"

class SimMeta(BaseModel):
    PK: str
    SK: str
    SIMId: str
    MobileNumber: str
    Provider: str
    Plan: str
    DataUsage: int
    AssignedDeviceId: str
    Status: str
    # CreatedDate: str
    # UpdatedDate: str
    EntityType: str

    class Config:
        extra = "forbid"

class SimAssoc(BaseModel):
    PK: str
    SK: str
    DeviceId: str
    SIMId: str
    Provider: str
    Status: str
    # CreatedDate: str
    # UpdatedDate: str
    EntityType: str

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
        except Exception as e:
            logger.error(f"Failed to parse body: {e}")
            return ErrorResponse.build(f"Malformed JSON body: {e}", 400)

        entity_type = item.get("EntityType")
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return ErrorResponse.build(f"Unknown EntityType: {entity_type}", 400)

        # Derive PK and SK if not present
        if entity_type == "DEVICE":
            item["PK"] = f'DEVICE#{item.get("DeviceId")}'
            item["SK"] = "META"
        elif entity_type == "CONFIG":
            item["PK"] = f'DEVICE#{item.get("DeviceId")}'
            version = item.get("ConfigVersion", "V1.0")
            created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
            item["SK"] = f'CONFIG#{version}#{created}'
        elif entity_type == "REPAIR":
            item["PK"] = f'DEVICE#{item.get("DeviceId")}'
            repair_id = item.get("RepairId", "REP")
            created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
            item["SK"] = f'REPAIR#{repair_id}#{created[:10]}'
        elif entity_type == "INSTALL":
            item["PK"] = f'DEVICE#{item.get("DeviceId")}'
            install_id = item.get("InstallId", "INS")
            created = item.get("CreatedDate", datetime.utcnow().isoformat() + "Z")
            item["SK"] = f'INSTALL#{install_id}#{created[:10]}'
        elif entity_type == "RUNTIME":
            item["PK"] = f'DEVICE#{item.get("DeviceId")}'
            event_date = item.get("EventDate", datetime.utcnow().isoformat() + "Z")
            item["SK"] = f'RUNTIME#{event_date}'
        elif entity_type == "SIM":
            item["PK"] = f'SIM#{item.get("SIMId")}'
            item["SK"] = "META"
        elif entity_type == "SIM_ASSOC":
            item["PK"] = f'DEVICE#{item.get("DeviceId")}'
            sim_id = item.get("SIMId", "SIM")
            item["SK"] = f'SIM_ASSOC#{sim_id}'
        else:
            return ErrorResponse.build(f"Cannot derive PK/SK for EntityType: {entity_type}", 400)

        try:
            validated = model(**item)
        except ValidationError as ve:
            return ErrorResponse.build(str(ve), 400)

        # Always initialize CreatedDate and UpdatedDate to sysdate, even if fields don't exist
        now_iso = datetime.utcnow().isoformat() + "Z"
        item["CreatedDate"] = now_iso
        item["UpdatedDate"] = now_iso

        try:
            table.put_item(Item=validated.dict())
            return SuccessResponse.build({"inserted": validated.dict()})
        except Exception as e:
            logger.error(f"DynamoDB error: {str(e)}")
            return ErrorResponse.build(f"DynamoDB error: {str(e)}", 500)

    elif method == "GET":
        params = event.get("queryStringParameters") or {}
        device_type = params.get("DeviceType")
        status = params.get("Status")

        # Scan for all devices by default
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
            return SuccessResponse.build(transform_items_to_json(items))
        except Exception as e:
            logger.error(f"DynamoDB scan error: {str(e)}")
            return ErrorResponse.build(f"DynamoDB scan error: {str(e)}", 500)

    return ErrorResponse.build("Method not allowed", 405)

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
    
    results = []
    for item in items:
        item = simplify(item)  # <-- Add this line to convert Decimals
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
            "PK": item.get("PK"),
            "SK": item.get("SK")
        }
        # Add extra fields for other entity types
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