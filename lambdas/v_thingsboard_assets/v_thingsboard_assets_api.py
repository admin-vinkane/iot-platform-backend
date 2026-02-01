"""
Thingsboard Assets API Lambda
Manages synchronization of region hierarchy and device-habitat linking with Thingsboard.

Endpoints:
- POST /thingsboard/sync-regions: Sync entire region hierarchy to Thingsboard
- GET /thingsboard/assets: List assets from Thingsboard
- POST /thingsboard/assets: Create asset in Thingsboard
- POST /thingsboard/assets/{assetId}/attributes: Set asset attributes
- POST /thingsboard/assets/{assetId}/relate-device: Create relation between asset and device
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple

import boto3
from botocore.exceptions import ClientError

# Import shared utilities
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.response_utils import SuccessResponse, ErrorResponse
from shared.thingsboard_utils import (
    sync_region_hierarchy_to_thingsboard,
    create_or_get_asset,
    set_asset_attributes,
    create_asset_relation,
    get_asset_by_name,
    get_asset_profiles,
    get_asset_relation_types
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB setup
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME", "v_devices_dev")
table = dynamodb.Table(TABLE_NAME)


def get_region_hierarchy_from_db() -> Dict[str, list]:
    """
    Fetch all region hierarchy data from DynamoDB for syncing to Thingsboard.
    
    Returns:
        Dict: Region hierarchy data with states, districts, mandals, villages, habitations
    """
    try:
        regions_data = {
            "states": [],
            "districts": [],
            "mandals": [],
            "villages": [],
            "habitations": []
        }
        
        # Query all states
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": "STATE#",
                ":sk": "STATE#"
            }
        )
        regions_data["states"] = [simplify(item) for item in response.get("Items", [])]
        
        # Query all districts
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": "DISTRICT#",
                ":sk": "DISTRICT#"
            }
        )
        regions_data["districts"] = [simplify(item) for item in response.get("Items", [])]
        
        # Query all mandals
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": "MANDAL#",
                ":sk": "MANDAL#"
            }
        )
        regions_data["mandals"] = [simplify(item) for item in response.get("Items", [])]
        
        # Query all villages
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": "VILLAGE#",
                ":sk": "VILLAGE#"
            }
        )
        regions_data["villages"] = [simplify(item) for item in response.get("Items", [])]
        
        # Query all habitations
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": "HABITATION#",
                ":sk": "HABITATION#"
            }
        )
        regions_data["habitations"] = [simplify(item) for item in response.get("Items", [])]
        
        logger.info(f"Fetched region hierarchy: {len(regions_data['states'])} states, "
                   f"{len(regions_data['districts'])} districts, {len(regions_data['mandals'])} mandals, "
                   f"{len(regions_data['villages'])} villages, {len(regions_data['habitations'])} habitations")
        
        return regions_data
        
    except Exception as e:
        logger.error(f"Error fetching region hierarchy from DB: {str(e)}")
        raise


def sync_regions_handler(event: Dict, context: Any) -> Dict:
    """
    Handle POST /thingsboard/sync-regions request.
    Syncs entire region hierarchy to Thingsboard.
    
    Returns:
        Dict: Success/error response with sync results
    """
    try:
        logger.info("Starting region hierarchy sync to Thingsboard")
        
        # Get region hierarchy from DynamoDB
        regions_data = get_region_hierarchy_from_db()
        
        # Sync to Thingsboard
        sync_results = sync_region_hierarchy_to_thingsboard(regions_data)
        
        return SuccessResponse.build({
            "message": "Region hierarchy sync completed",
            "results": sync_results
        })
        
    except Exception as e:
        logger.error(f"Region sync failed: {str(e)}")
        return ErrorResponse.build(f"Region sync failed: {str(e)}", 500)


def list_assets_handler(event: Dict, context: Any) -> Dict:
    """
    Handle GET /thingsboard/assets request.
    Lists assets from Thingsboard.
    
    Returns:
        Dict: Success response with asset list
    """
    try:
        logger.info("Fetching asset profiles from Thingsboard")
        
        profiles = get_asset_profiles()
        
        if profiles is None:
            return ErrorResponse.build("Failed to fetch asset profiles", 500)
        
        return SuccessResponse.build({
            "assetProfiles": profiles,
            "count": len(profiles)
        })
        
    except Exception as e:
        logger.error(f"Failed to list assets: {str(e)}")
        return ErrorResponse.build(f"Failed to list assets: {str(e)}", 500)


def create_asset_handler(event: Dict, context: Any) -> Dict:
    """
    Handle POST /thingsboard/assets request.
    Creates a new asset in Thingsboard.
    
    Request body:
        {
            "name": "Asset Name",
            "type": "Asset Type"  (e.g., "State", "District", "Village")
        }
    
    Returns:
        Dict: Success response with created asset details
    """
    try:
        body = json.loads(event.get("body", "{}"))
        
        asset_name = body.get("name")
        asset_type = body.get("type")
        
        if not asset_name or not asset_type:
            return ErrorResponse.build("Missing required fields: 'name' and 'type'", 400)
        
        logger.info(f"Creating asset: {asset_name} (type: {asset_type})")
        
        asset = create_or_get_asset(asset_name, asset_type)
        
        if not asset:
            return ErrorResponse.build(f"Failed to create asset: {asset_name}", 500)
        
        return SuccessResponse.build({
            "message": f"Asset created: {asset_name}",
            "asset": asset
        }, 201)
        
    except Exception as e:
        logger.error(f"Failed to create asset: {str(e)}")
        return ErrorResponse.build(f"Failed to create asset: {str(e)}", 500)


def set_asset_attributes_handler(event: Dict, context: Any) -> Dict:
    """
    Handle POST /thingsboard/assets/{assetId}/attributes request.
    Sets attributes for an asset.
    
    Path parameters:
        assetId: UUID of the asset
    
    Request body:
        {
            "code": "BALA",
            "hierarchy": "RAN/TG"
        }
    
    Returns:
        Dict: Success/error response
    """
    try:
        path_parameters = event.get("pathParameters", {}) or {}
        asset_id = path_parameters.get("assetId")
        
        if not asset_id:
            return ErrorResponse.build("Missing path parameter: assetId", 400)
        
        body = json.loads(event.get("body", "{}"))
        
        if not body:
            return ErrorResponse.build("Request body cannot be empty", 400)
        
        logger.info(f"Setting attributes for asset {asset_id}: {body}")
        
        success = set_asset_attributes(asset_id, body)
        
        if not success:
            return ErrorResponse.build("Failed to set asset attributes", 500)
        
        return SuccessResponse.build({
            "message": f"Attributes set for asset {asset_id}",
            "assetId": asset_id,
            "attributes": body
        })
        
    except Exception as e:
        logger.error(f"Failed to set asset attributes: {str(e)}")
        return ErrorResponse.build(f"Failed to set asset attributes: {str(e)}", 500)


def relate_device_to_asset_handler(event: Dict, context: Any) -> Dict:
    """
    Handle POST /thingsboard/assets/{assetId}/relate-device request.
    Creates a relation between a habitation asset and a device.
    
    Path parameters:
        assetId: UUID of the asset (habitation)
    
    Request body:
        {
            "deviceId": "device UUID",
            "relationType": "CONTAINS"  (optional, defaults to "CONTAINS")
        }
    
    Returns:
        Dict: Success/error response
    """
    try:
        path_parameters = event.get("pathParameters", {}) or {}
        asset_id = path_parameters.get("assetId")
        
        if not asset_id:
            return ErrorResponse.build("Missing path parameter: assetId", 400)
        
        body = json.loads(event.get("body", "{}"))
        
        device_id = body.get("deviceId")
        relation_type = body.get("relationType", "CONTAINS")
        
        if not device_id:
            return ErrorResponse.build("Missing required field: deviceId", 400)
        
        logger.info(f"Creating relation from asset {asset_id} to device {device_id}")
        
        success = create_asset_relation(asset_id, device_id, relation_type)
        
        if not success:
            return ErrorResponse.build("Failed to create asset relation", 500)
        
        return SuccessResponse.build({
            "message": f"Relation created from asset {asset_id} to device {device_id}",
            "fromAsset": asset_id,
            "toDevice": device_id,
            "relationType": relation_type
        })
        
    except Exception as e:
        logger.error(f"Failed to create device relation: {str(e)}")
        return ErrorResponse.build(f"Failed to create device relation: {str(e)}", 500)


def simplify(item):
    """Convert DynamoDB item to plain Python dict."""
    if isinstance(item, dict):
        if "M" in item:
            return {k: simplify(v) for k, v in item["M"].items()}
        elif "L" in item:
            return [simplify(v) for v in item["L"]]
        elif "S" in item:
            return item["S"]
        elif "N" in item:
            try:
                return float(item["N"]) if "." in item["N"] else int(item["N"])
            except:
                return item["N"]
        elif "BOOL" in item:
            return item["BOOL"]
        elif "NULL" in item:
            return None
    return item


def lambda_handler(event, context):
    """Main Lambda handler for Thingsboard Assets API."""
    try:
        http_method = event.get("httpMethod", "").upper()
        path = event.get("path", "")
        path_parameters = event.get("pathParameters", {}) or {}
        
        logger.info(f"{http_method} {path} - pathParameters: {path_parameters}")
        
        # POST /thingsboard/sync-regions
        if http_method == "POST" and "/sync-regions" in path:
            return sync_regions_handler(event, context)
        
        # GET /thingsboard/assets
        if http_method == "GET" and "/assets" in path and not path_parameters.get("assetId"):
            return list_assets_handler(event, context)
        
        # POST /thingsboard/assets
        if http_method == "POST" and "/assets" in path and not path_parameters.get("assetId"):
            return create_asset_handler(event, context)
        
        # POST /thingsboard/assets/{assetId}/attributes
        if http_method == "POST" and "/attributes" in path and path_parameters.get("assetId"):
            return set_asset_attributes_handler(event, context)
        
        # POST /thingsboard/assets/{assetId}/relate-device
        if http_method == "POST" and "/relate-device" in path and path_parameters.get("assetId"):
            return relate_device_to_asset_handler(event, context)
        
        logger.warning(f"Unhandled route: {http_method} {path}")
        return ErrorResponse.build(f"Route not found: {http_method} {path}", 404)
        
    except Exception as e:
        logger.error(f"Unhandled error in lambda_handler: {str(e)}", exc_info=True)
        return ErrorResponse.build(f"Internal server error: {str(e)}", 500)
