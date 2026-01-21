import json
import os
import boto3
import logging
import re
from datetime import datetime
from decimal import Decimal
import decimal
from pydantic import BaseModel, ValidationError, Field
from botocore.exceptions import ClientError
from shared.response_utils import SuccessResponse, ErrorResponse

TABLE_NAME = os.environ.get("TABLE_NAME", "v_devices_dev")
SIMCARDS_TABLE_NAME = os.environ.get("SIMCARDS_TABLE_NAME", "v_simcards_dev")
dynamodb = boto3.resource("dynamodb")
dynamodb_client = boto3.client("dynamodb")
table = dynamodb.Table(TABLE_NAME)
simcards_table = dynamodb.Table(SIMCARDS_TABLE_NAME)

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
    CreatedBy: str = None
    UpdatedBy: str = None

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
    CreatedBy: str = None
    UpdatedBy: str = None

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
    CreatedBy: str = None
    UpdatedBy: str = None

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
    CreatedBy: str = None
    UpdatedBy: str = None

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
    CreatedBy: str = None
    UpdatedBy: str = None

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
    CreatedBy: str = None
    UpdatedBy: str = None

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
    CreatedBy: str = None
    UpdatedBy: str = None

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
    # Log the full event for debugging
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    # Try multiple ways to extract the HTTP method
    method = (
        event.get("httpMethod") or 
        event.get("requestContext", {}).get("http", {}).get("method") or
        event.get("requestContext", {}).get("httpMethod")
    )
    
    # Log for debugging
    logger.info(f"Event keys: {list(event.keys())}")
    logger.info(f"Extracted method: {method}")
    
    # If method is still None, return detailed error
    if not method:
        logger.error("Could not extract HTTP method from event")
        return ErrorResponse.build("Could not determine HTTP method from request", 400)

    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return SuccessResponse.build({"message": "CORS preflight successful"}, 200)

    if method == "POST":
        # Extract path and path parameters
        path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path") or ""
        path_parameters = event.get("pathParameters") or {}
        
        # Check if this is a /devices/{deviceId}/sim/link request
        if path_parameters.get("deviceId") and "/sim/link" in path:
            device_id = path_parameters.get("deviceId")
            logger.info(f"Linking SIM to device: {device_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            sim_id = body.get("simId")
            if not sim_id:
                return ErrorResponse.build("simId is required in request body", 400)
            
            performed_by = body.get("performedBy", "system")
            ip_address = get_client_ip(event)
            
            # Validate deviceId format
            if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                return ErrorResponse.build("Invalid deviceId format", 400)
            
            # Check if device exists
            try:
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
            except Exception as e:
                logger.error(f"Error checking device existence: {str(e)}")
                return ErrorResponse.build(f"Error validating device: {str(e)}", 500)
            
            # Check if device already has a linked SIM
            try:
                existing_sim_response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "SIM_ASSOC#"
                    }
                )
                if existing_sim_response.get("Items"):
                    existing_sim_id = existing_sim_response["Items"][0].get("SIMId")
                    return ErrorResponse.build(f"Device {device_id} already has a linked SIM: {existing_sim_id}. Please unlink first.", 400)
            except Exception as e:
                logger.error(f"Error checking existing SIM link: {str(e)}")
                return ErrorResponse.build(f"Error checking existing link: {str(e)}", 500)
            
            # Validate SIM is available for linking
            is_valid, error_msg, sim_data = validate_sim_available(sim_id)
            if not is_valid:
                logger.warning(f"SIM validation failed: {error_msg}")
                return ErrorResponse.build(error_msg, 400)
            
            # Execute atomic transaction
            sim_provider = sim_data.get("provider", "Unknown")
            success, transaction_error = execute_sim_link_transaction(
                device_id, sim_id, sim_provider, performed_by, ip_address
            )
            
            if not success:
                logger.error(f"Transaction failed: {transaction_error}")
                return ErrorResponse.build(transaction_error, 500)
            
            logger.info(f"Successfully linked SIM {sim_id} to device {device_id}")
            return SuccessResponse.build({
                "message": "SIM linked successfully",
                "deviceId": device_id,
                "simId": sim_id,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, 200)
        
        # Check if this is a /devices/{deviceId}/sim/unlink request
        if path_parameters.get("deviceId") and "/sim/unlink" in path:
            device_id = path_parameters.get("deviceId")
            logger.info(f"Unlinking SIM from device: {device_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            performed_by = body.get("performedBy", "system")
            ip_address = get_client_ip(event)
            
            # Validate deviceId format
            if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                return ErrorResponse.build("Invalid deviceId format", 400)
            
            # Check if device exists
            try:
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
            except Exception as e:
                logger.error(f"Error checking device existence: {str(e)}")
                return ErrorResponse.build(f"Error validating device: {str(e)}", 500)
            
            # Check if device has a linked SIM
            try:
                sim_response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "SIM_ASSOC#"
                    }
                )
                items = sim_response.get("Items", [])
                if not items:
                    return ErrorResponse.build(f"No SIM card linked to device {device_id}", 404)
                
                sim_assoc = items[0]
                sim_id = sim_assoc.get("SIMId")
                
                if not sim_id:
                    logger.error(f"SIM_ASSOC for device {device_id} missing SIMId")
                    return ErrorResponse.build("Invalid SIM association data", 500)
                
            except Exception as e:
                logger.error(f"Error fetching linked SIM: {str(e)}")
                return ErrorResponse.build(f"Error fetching linked SIM: {str(e)}", 500)
            
            # Execute atomic transaction
            success, transaction_error = execute_sim_unlink_transaction(
                device_id, sim_id, performed_by, ip_address
            )
            
            if not success:
                logger.error(f"Transaction failed: {transaction_error}")
                return ErrorResponse.build(transaction_error, 500)
            
            logger.info(f"Successfully unlinked SIM {sim_id} from device {device_id}")
            return SuccessResponse.build({
                "message": "SIM unlinked successfully",
                "deviceId": device_id,
                "simId": sim_id,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, 200)
        
        # Check if this is a /installs/{installId}/devices/link request
        if path_parameters.get("installId") and "/devices/link" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Linking device(s) to install: {install_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Support both single deviceId and array of deviceIds
            device_ids = body.get("deviceIds") or ([body.get("deviceId")] if body.get("deviceId") else [])
            if not device_ids:
                return ErrorResponse.build("deviceId or deviceIds array is required in request body", 400)
            
            performed_by = body.get("performedBy", "system")
            reason = body.get("reason")
            ip_address = get_client_ip(event)
            
            # Validate install exists
            is_valid, error_msg = validate_install_exists(install_id)
            if not is_valid:
                return ErrorResponse.build(error_msg, 404)
            
            # Link each device
            results = []
            errors = []
            
            for device_id in device_ids:
                # Validate device format
                if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                    errors.append({"deviceId": device_id, "error": "Invalid deviceId format"})
                    continue
                
                # Validate device exists
                is_valid, error_msg = validate_device_exists(device_id)
                if not is_valid:
                    errors.append({"deviceId": device_id, "error": error_msg})
                    continue
                
                # Check if already linked
                if check_device_install_link(device_id, install_id):
                    errors.append({"deviceId": device_id, "error": f"Device already linked to install {install_id}"})
                    continue
                
                # Execute link transaction
                success, transaction_error = execute_install_device_link_transaction(
                    install_id, device_id, performed_by, ip_address, reason
                )
                
                if success:
                    results.append({"deviceId": device_id, "status": "linked"})
                else:
                    errors.append({"deviceId": device_id, "error": transaction_error})
            
            response_data = {
                "installId": install_id,
                "linked": results,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            if errors:
                response_data["errors"] = errors
            
            status_code = 200 if results else 400
            logger.info(f"Link operation complete: {len(results)} succeeded, {len(errors)} failed")
            return SuccessResponse.build(response_data, status_code)
        
        # Check if this is a /installs/{installId}/devices/unlink request
        if path_parameters.get("installId") and "/devices/unlink" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Unlinking device(s) from install: {install_id}")
            
            try:
                body = json.loads(event.get("body", "{}"))
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
                return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
            
            # Support both single deviceId and array of deviceIds
            device_ids = body.get("deviceIds") or ([body.get("deviceId")] if body.get("deviceId") else [])
            if not device_ids:
                return ErrorResponse.build("deviceId or deviceIds array is required in request body", 400)
            
            performed_by = body.get("performedBy", "system")
            reason = body.get("reason")
            ip_address = get_client_ip(event)
            
            # Validate install exists
            is_valid, error_msg = validate_install_exists(install_id)
            if not is_valid:
                return ErrorResponse.build(error_msg, 404)
            
            # Unlink each device
            results = []
            errors = []
            
            for device_id in device_ids:
                # Validate device format
                if not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                    errors.append({"deviceId": device_id, "error": "Invalid deviceId format"})
                    continue
                
                # Execute unlink transaction
                success, transaction_error = execute_install_device_unlink_transaction(
                    install_id, device_id, performed_by, ip_address, reason
                )
                
                if success:
                    results.append({"deviceId": device_id, "status": "unlinked"})
                else:
                    errors.append({"deviceId": device_id, "error": transaction_error})
            
            response_data = {
                "installId": install_id,
                "unlinked": results,
                "performedBy": performed_by,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            if errors:
                response_data["errors"] = errors
            
            status_code = 200 if results else 400
            logger.info(f"Unlink operation complete: {len(results)} succeeded, {len(errors)} failed")
            return SuccessResponse.build(response_data, status_code)
        
        # Default POST handler for creating entities
        try:
            item = json.loads(event.get("body", "{}"))
            if not isinstance(item, dict):
                raise ValueError("POST body must be a dict")
            item = convert_floats_to_decimal(item)
        except Exception as e:
            logger.error(f"Failed to parse body: {e}")
            return ErrorResponse.build(f"Malformed JSON body: {e}", 400)

        entity_type = item.get("EntityType")
        if not entity_type:
            return ErrorResponse.build("EntityType is required", 400)
        
        device_id = item.get("DeviceId")
        if not device_id:
            return ErrorResponse.build("DeviceId is required", 400)
        
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return ErrorResponse.build(f"Unknown EntityType: {entity_type}", 400)

        # Derive PK and SK
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for insert", 400)

        # Add PK and SK to item
        item["PK"] = pk
        item["SK"] = sk

        # Set timestamps if not provided
        timestamp = datetime.utcnow().isoformat() + "Z"
        if not item.get("CreatedDate"):
            item["CreatedDate"] = timestamp
        if not item.get("UpdatedDate"):
            item["UpdatedDate"] = timestamp
        # Set CreatedBy and UpdatedBy
        if item.get("CreatedBy"):
            if not item.get("UpdatedBy"):
                item["UpdatedBy"] = item["CreatedBy"]

        try:
            # Validate with Pydantic model
            validated_item = model(**item)
            
            # Insert new item with duplicate prevention
            table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
            )
            logger.info(f"Created new {entity_type} with PK={pk}, SK={sk}")
            return SuccessResponse.build({"created": item}, 201)
        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return ErrorResponse.build(f"Validation error: {str(e)}", 400)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Duplicate {entity_type} detected: PK={pk}, SK={sk}")
                return ErrorResponse.build(f"{entity_type} with ID {device_id} already exists", 409)
            logger.error(f"DynamoDB error: {str(e)}")
            return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
        except Exception as e:
            logger.error(f"Insert error: {str(e)}")
            return ErrorResponse.build(f"Insert error: {str(e)}", 500)
    
    elif method == "GET":
        # Extract path (HTTP API 2.0 uses rawPath, REST API uses path)
        path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path") or ""
        path_parameters = event.get("pathParameters") or {}
        params = event.get("queryStringParameters") or {}
        
        # Check if this is a /devices/{deviceId}/sim request (no EntityType required)
        if path_parameters.get("deviceId") and "/sim" in path:
            device_id = path_parameters.get("deviceId")
            logger.info(f"Fetching linked SIM for device: {device_id}")
            
            # Validate deviceId format
            if not device_id or not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                logger.warning(f"Invalid deviceId format: {device_id}")
                return ErrorResponse.build("Invalid deviceId format. Must be alphanumeric with optional _ or - (1-64 chars)", 400)
            
            try:
                # Check if device exists
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    logger.info(f"Device not found: {device_id}")
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
                
                # Query SIM_ASSOC entity for this device
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "SIM_ASSOC#"
                    }
                )
                items = response.get("Items", [])
                
                if not items:
                    logger.info(f"No SIM linked to device {device_id}")
                    return ErrorResponse.build(f"No SIM card linked to device {device_id}", 404)
                
                # Get the first (and should be only) SIM_ASSOC
                sim_assoc = items[0]
                sim_id = sim_assoc.get("SIMId")
                
                if not sim_id:
                    logger.error(f"SIM_ASSOC for device {device_id} missing SIMId")
                    return ErrorResponse.build("Invalid SIM association data", 500)
                
                # Fetch full SIM details from simcards table
                success, sim_data, error_msg = fetch_sim_details(sim_id)
                if not success:
                    logger.error(f"Failed to fetch SIM details: {error_msg}")
                    return ErrorResponse.build(error_msg, 500)
                
                # Merge SIM_ASSOC and SIM data
                result = {
                    "simId": sim_id,
                    "linkedDate": sim_assoc.get("CreatedDate"),
                    "linkStatus": sim_assoc.get("Status"),
                    "simDetails": sim_data
                }
                
                logger.info(f"Successfully fetched linked SIM {sim_id} for device {device_id}")
                return SuccessResponse.build(result)
                
            except ClientError as e:
                logger.error(f"Database error fetching SIM for {device_id}: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error fetching SIM for {device_id}: {str(e)}")
                return ErrorResponse.build(f"Error fetching SIM: {str(e)}", 500)
        
        # Check if this is a /devices/{deviceId}/configs request
        if path_parameters.get("deviceId") and "/configs" in path:
            device_id = path_parameters.get("deviceId")
            logger.info(f"Fetching configs for device: {device_id}")
            
            # Validate deviceId format
            if not device_id or not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                logger.warning(f"Invalid deviceId format: {device_id}")
                return ErrorResponse.build("Invalid deviceId format. Must be alphanumeric with optional _ or - (1-64 chars)", 400)
            
            try:
                # Check if device exists
                device_response = table.get_item(
                    Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                )
                if "Item" not in device_response:
                    logger.info(f"Device not found: {device_id}")
                    return ErrorResponse.build(f"Device {device_id} not found", 404)
                
                # Query all CONFIG entities for this device
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "CONFIG#"
                    }
                )
                items = response.get("Items", [])
                logger.info(f"Found {len(items)} config(s) for device {device_id}")
                return SuccessResponse.build(transform_items_to_json(items))
            except ClientError as e:
                logger.error(f"Database error fetching configs for {device_id}: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error fetching configs for {device_id}: {str(e)}")
                return ErrorResponse.build(f"Error fetching configs: {str(e)}", 500)
        
        # Check if this is a /installs/{installId}/devices request
        if path_parameters.get("installId") and "/devices" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Fetching devices for install: {install_id}")
            
            try:
                # Validate install exists
                is_valid, error_msg = validate_install_exists(install_id)
                if not is_valid:
                    return ErrorResponse.build(error_msg, 404)
                
                # Query all device associations for this install
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"INSTALL#{install_id}",
                        ":sk": "DEVICE_ASSOC#"
                    }
                )
                assoc_items = response.get("Items", [])
                
                # Fetch full device details for each linked device
                devices = []
                for assoc in assoc_items:
                    device_id = assoc.get("DeviceId")
                    if device_id:
                        device_response = table.get_item(
                            Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
                        )
                        if "Item" in device_response:
                            device_data = simplify(device_response["Item"])
                            device_data["linkedDate"] = assoc.get("LinkedDate")
                            device_data["linkedBy"] = assoc.get("LinkedBy")
                            device_data["linkStatus"] = assoc.get("Status")
                            devices.append(device_data)
                
                logger.info(f"Found {len(devices)} device(s) for install {install_id}")
                return SuccessResponse.build({
                    "installId": install_id,
                    "deviceCount": len(devices),
                    "devices": devices
                })
                
            except ClientError as e:
                logger.error(f"Database error: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return ErrorResponse.build(f"Error: {str(e)}", 500)
        
        # Check if this is a /devices/{deviceId}/install request
        if path_parameters.get("deviceId") and "/install" in path:
            device_id = path_parameters.get("deviceId")
            logger.info(f"Fetching install info for device: {device_id}")
            
            # Validate deviceId format
            if not device_id or not re.match(r"^[A-Za-z0-9_-]{1,64}$", device_id):
                return ErrorResponse.build("Invalid deviceId format", 400)
            
            try:
                # Validate device exists
                is_valid, error_msg = validate_device_exists(device_id)
                if not is_valid:
                    return ErrorResponse.build(error_msg, 404)
                
                # Query install association for this device
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"DEVICE#{device_id}",
                        ":sk": "INSTALL_ASSOC#"
                    }
                )
                assoc_items = response.get("Items", [])
                
                if not assoc_items:
                    return ErrorResponse.build(f"Device {device_id} is not linked to any installation", 404)
                
                # Get install details
                assoc = assoc_items[0]
                install_id = assoc.get("InstallId")
                
                if install_id:
                    install_response = table.get_item(
                        Key={"PK": f"INSTALL#{install_id}", "SK": "META"}
                    )
                    if "Item" in install_response:
                        install_data = simplify(install_response["Item"])
                        install_data["linkedDate"] = assoc.get("LinkedDate")
                        install_data["linkedBy"] = assoc.get("LinkedBy")
                        install_data["linkStatus"] = assoc.get("Status")
                        
                        logger.info(f"Found install {install_id} for device {device_id}")
                        return SuccessResponse.build(install_data)
                
                return ErrorResponse.build(f"Install details not found", 404)
                
            except ClientError as e:
                logger.error(f"Database error: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return ErrorResponse.build(f"Error: {str(e)}", 500)
        
        # Check if this is a /installs/{installId}/history request
        if path_parameters.get("installId") and "/history" in path:
            install_id = path_parameters.get("installId")
            logger.info(f"Fetching device link history for install: {install_id}")
            
            try:
                # Validate install exists
                is_valid, error_msg = validate_install_exists(install_id)
                if not is_valid:
                    return ErrorResponse.build(error_msg, 404)
                
                # Query history records
                response = table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                    ExpressionAttributeValues={
                        ":pk": f"INSTALL#{install_id}",
                        ":sk": "DEVICE_HISTORY#"
                    }
                )
                history_items = response.get("Items", [])
                
                # Simplify and sort by timestamp descending
                history = [simplify(item) for item in history_items]
                history.sort(key=lambda x: x.get("PerformedAt", ""), reverse=True)
                
                logger.info(f"Found {len(history)} history record(s) for install {install_id}")
                return SuccessResponse.build({
                    "installId": install_id,
                    "historyCount": len(history),
                    "history": history
                })
                
            except ClientError as e:
                logger.error(f"Database error: {str(e)}")
                return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return ErrorResponse.build(f"Error: {str(e)}", 500)
        
        # Default: GET /devices - list all devices with optional filters
        # EntityType defaults to "DEVICE" if not provided for backward compatibility
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
                    # Fetch repair history
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
                    
                    # Fetch linked SIM data
                    try:
                        sim_response = table.query(
                            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                            ExpressionAttributeValues={
                                ":pk": f"DEVICE#{device_id}",
                                ":sk": "SIM_ASSOC#"
                            }
                        )
                        sim_items = sim_response.get("Items", [])
                        if sim_items:
                            sim_assoc = sim_items[0]
                            sim_id = sim_assoc.get("SIMId")
                            if sim_id:
                                # Fetch full SIM details from simcards table
                                success, sim_data, error_msg = fetch_sim_details(sim_id)
                                if success:
                                    item["LinkedSIM"] = {
                                        "simId": sim_id,
                                        "linkedDate": sim_assoc.get("CreatedDate"),
                                        "linkStatus": sim_assoc.get("Status"),
                                        "simDetails": sim_data
                                    }
                                else:
                                    logger.warning(f"Failed to fetch SIM details for {sim_id}: {error_msg}")
                                    item["LinkedSIM"] = None
                            else:
                                item["LinkedSIM"] = None
                        else:
                            item["LinkedSIM"] = None
                    except Exception as e:
                        logger.error(f"Error fetching linked SIM for {device_id}: {str(e)}")
                        item["LinkedSIM"] = None
            
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
        if not entity_type:
            return ErrorResponse.build("EntityType is required", 400)
        
        device_id = item.get("DeviceId")
        if not device_id:
            return ErrorResponse.build("DeviceId is required", 400)
        
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return ErrorResponse.build(f"Unknown EntityType: {entity_type}", 400)

        # Derive PK and SK
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for update", 400)

        # Set UpdatedDate and UpdatedBy
        item["UpdatedDate"] = datetime.utcnow().isoformat() + "Z"
        if item.get("CreatedBy") and not item.get("UpdatedBy"):
            item["UpdatedBy"] = item["CreatedBy"]

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
        # Get query parameters - all values come from query string
        params = event.get("queryStringParameters") or {}
        entity_type = params.get("EntityType")
        device_id = params.get("DeviceId")
        
        if not entity_type:
            return ErrorResponse.build("EntityType is required for delete", 400)
        
        if not device_id:
            return ErrorResponse.build("DeviceId is required for delete", 400)

        # Build item dict for PK/SK derivation based on EntityType
        item = {
            "EntityType": entity_type,
            "DeviceId": device_id
        }
        
        # Add entity-specific required fields for SK construction
        # CONFIG requires: ConfigVersion, CreatedDate
        # REPAIR requires: RepairId, CreatedDate
        # INSTALL requires: InstallId, CreatedDate
        # RUNTIME requires: EventDate
        # SIM_ASSOC requires: SIMId
        # DEVICE only needs EntityType and DeviceId
        
        if entity_type == "CONFIG":
            config_version = params.get("ConfigVersion")
            created_date = params.get("CreatedDate")
            if not config_version or not created_date:
                return ErrorResponse.build("ConfigVersion and CreatedDate are required for CONFIG delete", 400)
            item["ConfigVersion"] = config_version
            item["CreatedDate"] = created_date
        elif entity_type == "REPAIR":
            repair_id = params.get("RepairId")
            created_date = params.get("CreatedDate")
            if not repair_id or not created_date:
                return ErrorResponse.build("RepairId and CreatedDate are required for REPAIR delete", 400)
            item["RepairId"] = repair_id
            item["CreatedDate"] = created_date
        elif entity_type == "INSTALL":
            install_id = params.get("InstallId")
            created_date = params.get("CreatedDate")
            if not install_id or not created_date:
                return ErrorResponse.build("InstallId and CreatedDate are required for INSTALL delete", 400)
            item["InstallId"] = install_id
            item["CreatedDate"] = created_date
        elif entity_type == "RUNTIME":
            event_date = params.get("EventDate")
            if not event_date:
                return ErrorResponse.build("EventDate is required for RUNTIME delete", 400)
            item["EventDate"] = event_date
        elif entity_type == "SIM_ASSOC":
            sim_id = params.get("SIMId")
            if not sim_id:
                return ErrorResponse.build("SIMId is required for SIM_ASSOC delete", 400)
            item["SIMId"] = sim_id
        # DEVICE doesn't need additional fields - just EntityType and DeviceId
        
        pk, sk = derive_pk_sk(item)
        if not pk or not sk:
            return ErrorResponse.build("Could not derive PK/SK for delete", 400)
        
        logger.info(f"Attempting to delete {entity_type} with PK={pk}, SK={sk}")
        
        try:
            table.delete_item(
                Key={
                    "PK": pk,
                    "SK": sk
                }
            )
            logger.info(f"Successfully deleted {entity_type} with PK={pk}, SK={sk}")
            return SuccessResponse.build({"deleted": {"PK": pk, "SK": sk, "EntityType": entity_type}})
        except Exception as e:
            logger.error(f"Delete error for {entity_type}: {str(e)}")
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
            "LinkedSIM": item.get("LinkedSIM"),  # <-- Add LinkedSIM here
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

def validate_sim_available(sim_id):
    """
    Validate that a SIM card exists, is active, and not already linked to another device.
    Returns (is_valid, error_message, sim_data)
    """
    try:
        # Fetch SIM card from simcards table
        response = simcards_table.get_item(
            Key={
                "PK": f"SIMCARD#{sim_id}",
                "SK": "ENTITY#SIMCARD"
            }
        )
        
        if "Item" not in response:
            return False, f"SIM card {sim_id} not found", None
        
        sim_data = response["Item"]
        
        # Check if SIM is active
        if sim_data.get("status") != "active":
            return False, f"SIM card {sim_id} is not active (status: {sim_data.get('status')})", None
        
        # Check if SIM is already linked to another device
        linked_device = sim_data.get("linkedDeviceId")
        if linked_device:
            return False, f"SIM card {sim_id} is already linked to device {linked_device}", None
        
        return True, None, sim_data
    
    except ClientError as e:
        logger.error(f"Error validating SIM {sim_id}: {str(e)}")
        return False, f"Database error validating SIM: {e.response['Error']['Message']}", None
    except Exception as e:
        logger.error(f"Unexpected error validating SIM {sim_id}: {str(e)}")
        return False, f"Unexpected error: {str(e)}", None

def execute_sim_link_transaction(device_id, sim_id, sim_provider, performed_by, ip_address):
    """
    Execute atomic transaction to link SIM to device across both tables.
    Creates SIM_ASSOC in devices table and updates linkedDeviceId in simcards table.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    try:
        # Prepare transaction items
        transact_items = [
            {
                # Create SIM_ASSOC in devices table
                "Put": {
                    "TableName": TABLE_NAME,
                    "Item": {
                        "PK": {"S": f"DEVICE#{device_id}"},
                        "SK": {"S": f"SIM_ASSOC#{sim_id}"},
                        "DeviceId": {"S": device_id},
                        "SIMId": {"S": sim_id},
                        "Provider": {"S": sim_provider},
                        "Status": {"S": "linked"},
                        "EntityType": {"S": "SIM_ASSOC"},
                        "CreatedDate": {"S": timestamp},
                        "UpdatedDate": {"S": timestamp}
                    }
                }
            },
            {
                # Update SIM card in simcards table
                "Update": {
                    "TableName": SIMCARDS_TABLE_NAME,
                    "Key": {
                        "PK": {"S": f"SIMCARD#{sim_id}"},
                        "SK": {"S": "ENTITY#SIMCARD"}
                    },
                    "UpdateExpression": "SET linkedDeviceId = :deviceId, updatedAt = :timestamp, changeHistory = list_append(if_not_exists(changeHistory, :empty_list), :new_history)",
                    "ExpressionAttributeValues": {
                        ":deviceId": {"S": device_id},
                        ":timestamp": {"S": timestamp},
                        ":empty_list": {"L": []},
                        ":new_history": {
                            "L": [
                                {
                                    "M": {
                                        "timestamp": {"S": timestamp},
                                        "action": {"S": "linked"},
                                        "deviceId": {"S": device_id},
                                        "performedBy": {"S": performed_by},
                                        "ipAddress": {"S": ip_address}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        ]
        
        # Execute transaction
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully linked SIM {sim_id} to device {device_id}")
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            logger.error(f"Transaction cancelled for linking SIM {sim_id} to device {device_id}: {str(e)}")
            return False, "Transaction failed. One or more operations could not be completed."
        else:
            logger.error(f"Error executing link transaction: {str(e)}")
            return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in link transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"

def execute_sim_unlink_transaction(device_id, sim_id, performed_by, ip_address):
    """
    Execute atomic transaction to unlink SIM from device across both tables.
    Deletes SIM_ASSOC from devices table and clears linkedDeviceId in simcards table.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    try:
        # Prepare transaction items
        transact_items = [
            {
                # Delete SIM_ASSOC from devices table
                "Delete": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": {"S": f"DEVICE#{device_id}"},
                        "SK": {"S": f"SIM_ASSOC#{sim_id}"}
                    }
                }
            },
            {
                # Update SIM card in simcards table
                "Update": {
                    "TableName": SIMCARDS_TABLE_NAME,
                    "Key": {
                        "PK": {"S": f"SIMCARD#{sim_id}"},
                        "SK": {"S": "ENTITY#SIMCARD"}
                    },
                    "UpdateExpression": "REMOVE linkedDeviceId SET updatedAt = :timestamp, changeHistory = list_append(if_not_exists(changeHistory, :empty_list), :new_history)",
                    "ExpressionAttributeValues": {
                        ":timestamp": {"S": timestamp},
                        ":empty_list": {"L": []},
                        ":new_history": {
                            "L": [
                                {
                                    "M": {
                                        "timestamp": {"S": timestamp},
                                        "action": {"S": "unlinked"},
                                        "deviceId": {"S": device_id},
                                        "performedBy": {"S": performed_by},
                                        "ipAddress": {"S": ip_address}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        ]
        
        # Execute transaction
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully unlinked SIM {sim_id} from device {device_id}")
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            logger.error(f"Transaction cancelled for unlinking SIM {sim_id} from device {device_id}: {str(e)}")
            return False, "Transaction failed. One or more operations could not be completed."
        else:
            logger.error(f"Error executing unlink transaction: {str(e)}")
            return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in unlink transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"

def get_client_ip(event):
    """
    Extract client IP address from event.
    """
    # Try HTTP API 2.0 format
    ip = event.get("requestContext", {}).get("http", {}).get("sourceIp")
    if ip:
        return ip
    
    # Try REST API format
    ip = event.get("requestContext", {}).get("identity", {}).get("sourceIp")
    if ip:
        return ip
    
    # Fallback
    return "unknown"

def fetch_sim_details(sim_id):
    """
    Fetch full SIM card details from simcards table.
    Returns (success, sim_data, error_message)
    """
    try:
        response = simcards_table.get_item(
            Key={
                "PK": f"SIMCARD#{sim_id}",
                "SK": "ENTITY#SIMCARD"
            }
        )
        
        if "Item" not in response:
            return False, None, f"SIM card {sim_id} not found"
        
        return True, simplify(response["Item"]), None
    
    except ClientError as e:
        logger.error(f"Error fetching SIM {sim_id}: {str(e)}")
        return False, None, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error fetching SIM {sim_id}: {str(e)}")
        return False, None, f"Unexpected error: {str(e)}"


# ============================================================================
# INSTALL-DEVICE LINKING FUNCTIONS
# ============================================================================

def validate_install_exists(install_id):
    """Validate that an install record exists."""
    try:
        response = table.get_item(
            Key={"PK": f"INSTALL#{install_id}", "SK": "META"}
        )
        if "Item" not in response:
            return False, f"Install {install_id} not found"
        return True, None
    except Exception as e:
        logger.error(f"Error checking install existence: {str(e)}")
        return False, f"Error validating install: {str(e)}"


def validate_device_exists(device_id):
    """Validate that a device record exists."""
    try:
        response = table.get_item(
            Key={"PK": f"DEVICE#{device_id}", "SK": "META"}
        )
        if "Item" not in response:
            return False, f"Device {device_id} not found"
        return True, None
    except Exception as e:
        logger.error(f"Error checking device existence: {str(e)}")
        return False, f"Error validating device: {str(e)}"


def check_device_install_link(device_id, install_id):
    """Check if a device is already linked to a specific install."""
    try:
        response = table.get_item(
            Key={
                "PK": f"DEVICE#{device_id}",
                "SK": f"INSTALL_ASSOC#{install_id}"
            }
        )
        return "Item" in response
    except Exception as e:
        logger.error(f"Error checking device-install link: {str(e)}")
        return False


def create_install_device_history(install_id, device_id, action, performed_by, ip_address, reason=None):
    """Create a history record for install-device link/unlink operations."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    history_item = {
        "PK": f"INSTALL#{install_id}",
        "SK": f"DEVICE_HISTORY#{timestamp}#{device_id}",
        "EntityType": "INSTALL_DEVICE_HISTORY",
        "InstallId": install_id,
        "DeviceId": device_id,
        "Action": action,  # "LINKED" or "UNLINKED"
        "PerformedBy": performed_by,
        "PerformedAt": timestamp,
        "IPAddress": ip_address
    }
    
    if reason:
        history_item["Reason"] = reason
    
    try:
        table.put_item(Item=history_item)
        logger.info(f"Created history record for {action}: Install {install_id} <-> Device {device_id}")
        return True, None
    except Exception as e:
        logger.error(f"Error creating history record: {str(e)}")
        return False, f"Error creating history: {str(e)}"


def execute_install_device_link_transaction(install_id, device_id, performed_by, ip_address, reason=None):
    """
    Execute atomic transaction to link a device to an install.
    Creates bidirectional associations and history record.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Prepare transaction items
    transact_items = [
        {
            "Put": {
                "TableName": TABLE_NAME,
                "Item": {
                    "PK": {"S": f"INSTALL#{install_id}"},
                    "SK": {"S": f"DEVICE_ASSOC#{device_id}"},
                    "EntityType": {"S": "INSTALL_DEVICE_ASSOC"},
                    "InstallId": {"S": install_id},
                    "DeviceId": {"S": device_id},
                    "Status": {"S": "active"},
                    "LinkedDate": {"S": timestamp},
                    "LinkedBy": {"S": performed_by},
                    "CreatedDate": {"S": timestamp},
                    "UpdatedDate": {"S": timestamp}
                },
                "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)"
            }
        },
        {
            "Put": {
                "TableName": TABLE_NAME,
                "Item": {
                    "PK": {"S": f"DEVICE#{device_id}"},
                    "SK": {"S": f"INSTALL_ASSOC#{install_id}"},
                    "EntityType": {"S": "DEVICE_INSTALL_ASSOC"},
                    "DeviceId": {"S": device_id},
                    "InstallId": {"S": install_id},
                    "Status": {"S": "active"},
                    "LinkedDate": {"S": timestamp},
                    "LinkedBy": {"S": performed_by},
                    "CreatedDate": {"S": timestamp},
                    "UpdatedDate": {"S": timestamp}
                },
                "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)"
            }
        }
    ]
    
    try:
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully linked device {device_id} to install {install_id}")
        
        # Create history record (non-transactional, but logged)
        create_install_device_history(install_id, device_id, "LINKED", performed_by, ip_address, reason)
        
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            reasons = e.response.get('CancellationReasons', [])
            if any(r.get('Code') == 'ConditionalCheckFailed' for r in reasons):
                return False, f"Device {device_id} is already linked to install {install_id}"
            return False, f"Transaction failed: {str(reasons)}"
        logger.error(f"Transaction error: {str(e)}")
        return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"


def execute_install_device_unlink_transaction(install_id, device_id, performed_by, ip_address, reason=None):
    """
    Execute atomic transaction to unlink a device from an install.
    Deletes bidirectional associations and creates history record.
    """
    
    # Prepare transaction items
    transact_items = [
        {
            "Delete": {
                "TableName": TABLE_NAME,
                "Key": {
                    "PK": {"S": f"INSTALL#{install_id}"},
                    "SK": {"S": f"DEVICE_ASSOC#{device_id}"}
                },
                "ConditionExpression": "attribute_exists(PK) AND attribute_exists(SK)"
            }
        },
        {
            "Delete": {
                "TableName": TABLE_NAME,
                "Key": {
                    "PK": {"S": f"DEVICE#{device_id}"},
                    "SK": {"S": f"INSTALL_ASSOC#{install_id}"}
                },
                "ConditionExpression": "attribute_exists(PK) AND attribute_exists(SK)"
            }
        }
    ]
    
    try:
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        logger.info(f"Successfully unlinked device {device_id} from install {install_id}")
        
        # Create history record
        create_install_device_history(install_id, device_id, "UNLINKED", performed_by, ip_address, reason)
        
        return True, None
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'TransactionCanceledException':
            reasons = e.response.get('CancellationReasons', [])
            if any(r.get('Code') == 'ConditionalCheckFailed' for r in reasons):
                return False, f"Device {device_id} is not linked to install {install_id}"
            return False, f"Transaction failed: {str(reasons)}"
        logger.error(f"Transaction error: {str(e)}")
        return False, f"Database error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in transaction: {str(e)}")
        return False, f"Unexpected error: {str(e)}"
