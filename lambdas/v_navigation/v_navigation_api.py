import json
import os
import boto3
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from shared.response_utils import SuccessResponse, ErrorResponse
from pydantic import BaseModel, ValidationError, Field, field_validator

# DynamoDB setup
TABLE_NAME = os.environ.get("TABLE_NAME", "v_navigation_dev")
DEV_MODE = os.environ.get("DEV_MODE", "true").lower() == "true"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

if DEV_MODE:
    logger.warning("⚠️  DEV_MODE is ENABLED - Authentication is BYPASSED! Set DEV_MODE=false in production.")

# Constants
ENTITY_TYPE_GROUP = "NAVIGATION_GROUP"
ENTITY_TYPE_ITEM = "NAVIGATION_ITEM"
ENTITY_TYPE_HISTORY = "NAVIGATION_HISTORY"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NavigationItem(BaseModel):
    """Navigation item model"""
    id: str
    PK: str
    SK: str
    entityType: str = Field(default=ENTITY_TYPE_ITEM)
    label: str = Field(min_length=2, max_length=50)
    icon: str
    path: str = Field(pattern=r'^/[^\s]*$')  # Must start with '/' and no spaces
    permission: Optional[str] = ""
    isActive: bool = True
    order: int = Field(ge=1, le=100)
    parentId: str  # Reference to the group ID
    children: List[Dict[str, Any]] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None

    class Config:
        extra = "forbid"


class NavigationItemCreate(BaseModel):
    """Model for creating navigation items"""
    label: str = Field(min_length=2, max_length=50)
    icon: str
    path: str = Field(pattern=r'^/[^\s]*$')
    permission: Optional[str] = ""
    isActive: bool = True
    order: int = Field(ge=1, le=100)
    createdBy: Optional[str] = "Admin"
    updatedBy: Optional[str] = "Admin"

    class Config:
        extra = "forbid"


class NavigationItemUpdate(BaseModel):
    """Model for updating navigation items (partial)"""
    label: Optional[str] = Field(default=None, min_length=2, max_length=50)
    icon: Optional[str] = None
    path: Optional[str] = Field(default=None, pattern=r'^/[^\s]*$')
    permission: Optional[str] = None
    isActive: Optional[bool] = None
    order: Optional[int] = Field(default=None, ge=1, le=100)
    updatedBy: Optional[str] = "Admin"

    class Config:
        extra = "forbid"


class NavigationGroup(BaseModel):
    """Navigation group model"""
    id: str
    PK: str
    SK: str
    entityType: str = Field(default=ENTITY_TYPE_GROUP)
    label: str = Field(min_length=2, max_length=50)
    icon: str
    isActive: bool = True
    order: int = Field(ge=1, le=100)
    isCollapsible: bool = True
    defaultExpanded: bool = False
    items: List[NavigationItem] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None

    class Config:
        extra = "forbid"


class NavigationGroupCreate(BaseModel):
    """Model for creating navigation groups"""
    label: str = Field(min_length=2, max_length=50)
    icon: str
    isActive: bool = True
    order: int = Field(ge=1, le=100)
    isCollapsible: bool = True
    defaultExpanded: bool = False
    createdBy: Optional[str] = "Admin"
    updatedBy: Optional[str] = "Admin"

    class Config:
        extra = "forbid"


class NavigationGroupUpdate(BaseModel):
    """Model for updating navigation groups (partial)"""
    label: Optional[str] = Field(default=None, min_length=2, max_length=50)
    icon: Optional[str] = None
    isActive: Optional[bool] = None
    order: Optional[int] = Field(default=None, ge=1, le=100)
    isCollapsible: Optional[bool] = None
    defaultExpanded: Optional[bool] = None
    updatedBy: Optional[str] = "Admin"

    class Config:
        extra = "forbid"


class NavigationChangeHistory(BaseModel):
    """Audit trail model for navigation changes"""
    id: str
    PK: str
    SK: str
    entityType: str = Field(default=ENTITY_TYPE_HISTORY)
    changeEntityType: str  # "group" or "item"
    entityId: str
    changeType: str  # "created", "updated", "deleted", "reordered", "moved", "status_changed"
    fieldName: Optional[str] = None
    oldValue: Optional[str] = None
    newValue: Optional[str] = None
    description: str
    changedBy: str
    changedAt: str
    ipAddress: Optional[str] = None

    class Config:
        extra = "forbid"


class ReorderRequest(BaseModel):
    """Model for reordering groups"""
    groupIds: List[str] = Field(min_length=1)

    class Config:
        extra = "forbid"


class ReorderItemsRequest(BaseModel):
    """Model for reordering items within a group"""
    itemIds: List[str] = Field(min_length=1)

    class Config:
        extra = "forbid"


class MoveItemRequest(BaseModel):
    """Model for moving items between groups"""
    itemId: str
    fromGroupId: str
    toGroupId: str

    class Config:
        extra = "forbid"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_user_from_event(event: Dict[str, Any]) -> Optional[str]:
    """Extract authenticated user from event (simplified for dev)"""
    if DEV_MODE:
        return "dev-user"
    
    # In production, extract from JWT token
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    return authorizer.get("claims", {}).get("sub") or authorizer.get("principalId")


def generate_id(prefix: str) -> str:
    """Generate a unique ID with timestamp"""
    from datetime import datetime
    import uuid
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"{prefix}_{timestamp}_{short_uuid}"


def get_iso_timestamp() -> str:
    """Get current timestamp in ISO-8601 format"""
    return datetime.utcnow().isoformat() + "Z"


def convert_decimals(obj):
    """Convert DynamoDB Decimal types to native Python types"""
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def record_history(
    entity_type: str,
    entity_id: str,
    change_type: str,
    description: str,
    changed_by: str,
    field_name: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """Record a change in navigation history"""
    try:
        history_id = generate_id("HIST")
        timestamp = get_iso_timestamp()
        
        history_item = {
            "id": history_id,
            "PK": f"HISTORY#{history_id}",
            "SK": f"TIMESTAMP#{timestamp}",
            "entityType": ENTITY_TYPE_HISTORY,
            "changeEntityType": entity_type,
            "entityId": entity_id,
            "changeType": change_type,
            "description": description,
            "changedBy": changed_by,
            "changedAt": timestamp,
        }
        
        if field_name:
            history_item["fieldName"] = field_name
        if old_value is not None:
            history_item["oldValue"] = str(old_value)
        if new_value is not None:
            history_item["newValue"] = str(new_value)
        if ip_address:
            history_item["ipAddress"] = ip_address
        
        table.put_item(Item=history_item)
        logger.info(f"Recorded history: {change_type} for {entity_type} {entity_id}")
    except Exception as e:
        logger.error(f"Failed to record history: {str(e)}")


def get_all_groups_with_items() -> List[Dict[str, Any]]:
    """Fetch all groups with their nested items, sorted by order"""
    try:
        # Fetch all groups
        response = table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_GROUP}
        ) if "GSI1" in [idx["IndexName"] for idx in table.global_secondary_indexes or []] else table.scan(
            FilterExpression="entityType = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_GROUP}
        )
        
        groups = response.get("Items", [])
        
        # Fetch all items
        response = table.scan(
            FilterExpression="entityType = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_ITEM}
        )
        
        items = response.get("Items", [])
        
        # Group items by parentId
        items_by_group = {}
        for item in items:
            parent_id = item.get("parentId")
            if parent_id not in items_by_group:
                items_by_group[parent_id] = []
            items_by_group[parent_id].append(convert_decimals(item))
        
        # Attach items to groups and sort
        result = []
        for group in groups:
            group_dict = convert_decimals(group)
            group_id = group_dict["id"]
            group_items = items_by_group.get(group_id, [])
            # Sort items by order
            group_dict["items"] = sorted(group_items, key=lambda x: x.get("order", 999))
            result.append(group_dict)
        
        # Sort groups by order
        result.sort(key=lambda x: x.get("order", 999))
        
        return result
    except Exception as e:
        logger.error(f"Error fetching groups with items: {str(e)}")
        raise


def check_unique_group_label(label: str, exclude_id: Optional[str] = None) -> bool:
    """Check if group label is unique (case-insensitive)"""
    try:
        response = table.scan(
            FilterExpression="entityType = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_GROUP}
        )
        
        for item in response.get("Items", []):
            if item.get("label", "").lower() == label.lower():
                if exclude_id and item.get("id") == exclude_id:
                    continue
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking unique label: {str(e)}")
        return False


def check_unique_item_path(path: str, exclude_id: Optional[str] = None) -> bool:
    """Check if item path is unique across all items"""
    try:
        response = table.scan(
            FilterExpression="entityType = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_ITEM}
        )
        
        for item in response.get("Items", []):
            if item.get("path") == path:
                if exclude_id and item.get("id") == exclude_id:
                    continue
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking unique path: {str(e)}")
        return False


def check_unique_item_label_in_group(label: str, group_id: str, exclude_id: Optional[str] = None) -> bool:
    """Check if item label is unique within a group (case-insensitive)"""
    try:
        response = table.scan(
            FilterExpression="entityType = :entity_type AND parentId = :parent_id",
            ExpressionAttributeValues={
                ":entity_type": ENTITY_TYPE_ITEM,
                ":parent_id": group_id
            }
        )
        
        for item in response.get("Items", []):
            if item.get("label", "").lower() == label.lower():
                if exclude_id and item.get("id") == exclude_id:
                    continue
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking unique item label: {str(e)}")
        return False


# ============================================================================
# ENDPOINT HANDLERS - GROUPS
# ============================================================================

def handle_list_groups(authenticated_user: Optional[str]) -> Dict[str, Any]:
    """GET /navigation/groups - List all groups with items"""
    try:
        groups = get_all_groups_with_items()
        return SuccessResponse.build(groups, 200)
    except Exception as e:
        logger.error(f"Error listing groups: {str(e)}")
        return ErrorResponse.build(f"Failed to list navigation groups: {str(e)}", 500)


def handle_create_group(event: Dict[str, Any], authenticated_user: Optional[str]) -> Dict[str, Any]:
    """POST /navigation/groups - Create a new navigation group"""
    try:
        body = json.loads(event.get("body", "{}"))
        group_data = NavigationGroupCreate(**body)
        
        # Check unique label
        if not check_unique_group_label(group_data.label):
            return ErrorResponse.build(f"Group label '{group_data.label}' already exists (case-insensitive)", 400)
        
        # Generate ID and timestamps
        group_id = generate_id("GROUP")
        timestamp = get_iso_timestamp()
        
        # Create group item
        group_item = {
            "id": group_id,
            "PK": f"GROUP#{group_id}",
            "SK": f"METADATA#{group_id}",
            "entityType": ENTITY_TYPE_GROUP,
            "label": group_data.label,
            "icon": group_data.icon,
            "isActive": group_data.isActive,
            "order": group_data.order,
            "isCollapsible": group_data.isCollapsible,
            "defaultExpanded": group_data.defaultExpanded,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "createdBy": group_data.createdBy,
            "updatedBy": group_data.updatedBy,
        }
        
        # Save to DynamoDB
        table.put_item(Item=group_item)
        
        # Record history
        record_history(
            entity_type="group",
            entity_id=group_id,
            change_type="created",
            description=f"Created navigation group '{group_data.label}'",
            changed_by=group_data.createdBy or authenticated_user or "system"
        )
        
        # Return with empty items array
        result = convert_decimals(group_item)
        result["items"] = []
        
        logger.info(f"Created navigation group: {group_id}")
        return SuccessResponse.build(result, 201)
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return ErrorResponse.build(f"Validation error: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error creating group: {str(e)}")
        return ErrorResponse.build(f"Failed to create navigation group: {str(e)}", 500)


def handle_update_group(group_id: str, event: Dict[str, Any], authenticated_user: Optional[str]) -> Dict[str, Any]:
    """PATCH /navigation/groups/{groupId} - Update a navigation group"""
    try:
        # Fetch existing group
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": f"METADATA#{group_id}"})
        
        if "Item" not in response:
            return ErrorResponse.build(f"Navigation group '{group_id}' not found", 404)
        
        existing_group = response["Item"]
        
        # Parse update data
        body = json.loads(event.get("body", "{}"))
        update_data = NavigationGroupUpdate(**body)
        
        # Check unique label if being updated
        if update_data.label and update_data.label != existing_group.get("label"):
            if not check_unique_group_label(update_data.label, exclude_id=group_id):
                return ErrorResponse.build(f"Group label '{update_data.label}' already exists", 400)
        
        # Build update expression
        update_expr_parts = []
        expr_attr_values = {}
        expr_attr_names = {}
        
        if update_data.label is not None:
            update_expr_parts.append("#label = :label")
            expr_attr_names["#label"] = "label"
            expr_attr_values[":label"] = update_data.label
        
        if update_data.icon is not None:
            update_expr_parts.append("icon = :icon")
            expr_attr_values[":icon"] = update_data.icon
        
        if update_data.isActive is not None:
            update_expr_parts.append("isActive = :isActive")
            expr_attr_values[":isActive"] = update_data.isActive
        
        if update_data.order is not None:
            update_expr_parts.append("#order = :order")
            expr_attr_names["#order"] = "order"
            expr_attr_values[":order"] = update_data.order
        
        if update_data.isCollapsible is not None:
            update_expr_parts.append("isCollapsible = :isCollapsible")
            expr_attr_values[":isCollapsible"] = update_data.isCollapsible
        
        if update_data.defaultExpanded is not None:
            update_expr_parts.append("defaultExpanded = :defaultExpanded")
            expr_attr_values[":defaultExpanded"] = update_data.defaultExpanded
        
        # Always update timestamp and updatedBy
        update_expr_parts.append("updatedAt = :updatedAt")
        update_expr_parts.append("updatedBy = :updatedBy")
        expr_attr_values[":updatedAt"] = get_iso_timestamp()
        expr_attr_values[":updatedBy"] = update_data.updatedBy or authenticated_user or "system"
        
        update_expression = "SET " + ", ".join(update_expr_parts)
        
        # Update in DynamoDB
        update_kwargs = {
            "Key": {"PK": f"GROUP#{group_id}", "SK": f"METADATA#{group_id}"},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expr_attr_values,
            "ReturnValues": "ALL_NEW"
        }
        
        if expr_attr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_attr_names
        
        response = table.update_item(**update_kwargs)
        
        updated_group = convert_decimals(response["Attributes"])
        
        # Record history for each changed field
        for field, new_value in update_data.dict(exclude_unset=True, exclude={"updatedBy"}).items():
            old_value = existing_group.get(field)
            if old_value != new_value:
                record_history(
                    entity_type="group",
                    entity_id=group_id,
                    change_type="updated",
                    description=f"Updated group '{existing_group.get('label')}' - {field}",
                    changed_by=update_data.updatedBy or authenticated_user or "system",
                    field_name=field,
                    old_value=str(old_value),
                    new_value=str(new_value)
                )
        
        # Fetch items for this group
        items_response = table.scan(
            FilterExpression="entityType = :entity_type AND parentId = :parent_id",
            ExpressionAttributeValues={
                ":entity_type": ENTITY_TYPE_ITEM,
                ":parent_id": group_id
            }
        )
        
        items = [convert_decimals(item) for item in items_response.get("Items", [])]
        items.sort(key=lambda x: x.get("order", 999))
        updated_group["items"] = items
        
        logger.info(f"Updated navigation group: {group_id}")
        return SuccessResponse.build(updated_group, 200)
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return ErrorResponse.build(f"Validation error: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error updating group: {str(e)}")
        return ErrorResponse.build(f"Failed to update navigation group: {str(e)}", 500)


def handle_delete_group(group_id: str, authenticated_user: Optional[str]) -> Dict[str, Any]:
    """DELETE /navigation/groups/{groupId} - Delete a navigation group and all its items"""
    try:
        # Fetch existing group
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": f"METADATA#{group_id}"})
        
        if "Item" not in response:
            return ErrorResponse.build(f"Navigation group '{group_id}' not found", 404)
        
        group = response["Item"]
        group_label = group.get("label", "Unknown")
        
        # Delete all items in this group
        items_response = table.scan(
            FilterExpression="entityType = :entity_type AND parentId = :parent_id",
            ExpressionAttributeValues={
                ":entity_type": ENTITY_TYPE_ITEM,
                ":parent_id": group_id
            }
        )
        
        items = items_response.get("Items", [])
        for item in items:
            item_pk = item["PK"]
            item_sk = item["SK"]
            table.delete_item(Key={"PK": item_pk, "SK": item_sk})
            logger.info(f"Deleted navigation item: {item['id']}")
        
        # Delete the group
        table.delete_item(Key={"PK": f"GROUP#{group_id}", "SK": f"METADATA#{group_id}"})
        
        # Record history
        record_history(
            entity_type="group",
            entity_id=group_id,
            change_type="deleted",
            description=f"Deleted navigation group '{group_label}' and {len(items)} items",
            changed_by=authenticated_user or "system"
        )
        
        logger.info(f"Deleted navigation group: {group_id} with {len(items)} items")
        return SuccessResponse.build(None, 204)
        
    except Exception as e:
        logger.error(f"Error deleting group: {str(e)}")
        return ErrorResponse.build(f"Failed to delete navigation group: {str(e)}", 500)


# ============================================================================
# ENDPOINT HANDLERS - ITEMS
# ============================================================================

def handle_create_item(group_id: str, event: Dict[str, Any], authenticated_user: Optional[str]) -> Dict[str, Any]:
    """POST /navigation/groups/{groupId}/items - Create a new navigation item"""
    try:
        # Verify group exists
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": f"METADATA#{group_id}"})
        
        if "Item" not in response:
            return ErrorResponse.build(f"Navigation group '{group_id}' not found", 404)
        
        group = response["Item"]
        
        # Parse item data
        body = json.loads(event.get("body", "{}"))
        item_data = NavigationItemCreate(**body)
        
        # Check unique path
        if not check_unique_item_path(item_data.path):
            return ErrorResponse.build(f"Item path '{item_data.path}' already exists", 400)
        
        # Check unique label within group
        if not check_unique_item_label_in_group(item_data.label, group_id):
            return ErrorResponse.build(f"Item label '{item_data.label}' already exists in this group", 400)
        
        # Generate ID and timestamps
        item_id = generate_id("ITEM")
        timestamp = get_iso_timestamp()
        
        # Create item
        item = {
            "id": item_id,
            "PK": f"ITEM#{item_id}",
            "SK": f"METADATA#{item_id}",
            "entityType": ENTITY_TYPE_ITEM,
            "label": item_data.label,
            "icon": item_data.icon,
            "path": item_data.path,
            "permission": item_data.permission or "",
            "isActive": item_data.isActive,
            "order": item_data.order,
            "parentId": group_id,
            "children": [],
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "createdBy": item_data.createdBy,
            "updatedBy": item_data.updatedBy,
        }
        
        # Save to DynamoDB
        table.put_item(Item=item)
        
        # Record history
        record_history(
            entity_type="item",
            entity_id=item_id,
            change_type="created",
            description=f"Created navigation item '{item_data.label}' in group '{group.get('label')}'",
            changed_by=item_data.createdBy or authenticated_user or "system"
        )
        
        result = convert_decimals(item)
        
        logger.info(f"Created navigation item: {item_id}")
        return SuccessResponse.build(result, 201)
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return ErrorResponse.build(f"Validation error: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error creating item: {str(e)}")
        return ErrorResponse.build(f"Failed to create navigation item: {str(e)}", 500)


def handle_update_item(group_id: str, item_id: str, event: Dict[str, Any], authenticated_user: Optional[str]) -> Dict[str, Any]:
    """PATCH /navigation/groups/{groupId}/items/{itemId} - Update a navigation item"""
    try:
        # Fetch existing item
        response = table.get_item(Key={"PK": f"ITEM#{item_id}", "SK": f"METADATA#{item_id}"})
        
        if "Item" not in response:
            return ErrorResponse.build(f"Navigation item '{item_id}' not found", 404)
        
        existing_item = response["Item"]
        
        # Verify item belongs to the group
        if existing_item.get("parentId") != group_id:
            return ErrorResponse.build(f"Item '{item_id}' does not belong to group '{group_id}'", 400)
        
        # Parse update data
        body = json.loads(event.get("body", "{}"))
        update_data = NavigationItemUpdate(**body)
        
        # Check unique path if being updated
        if update_data.path and update_data.path != existing_item.get("path"):
            if not check_unique_item_path(update_data.path, exclude_id=item_id):
                return ErrorResponse.build(f"Item path '{update_data.path}' already exists", 400)
        
        # Check unique label within group if being updated
        if update_data.label and update_data.label != existing_item.get("label"):
            if not check_unique_item_label_in_group(update_data.label, group_id, exclude_id=item_id):
                return ErrorResponse.build(f"Item label '{update_data.label}' already exists in this group", 400)
        
        # Build update expression
        update_expr_parts = []
        expr_attr_values = {}
        expr_attr_names = {}
        
        if update_data.label is not None:
            update_expr_parts.append("#label = :label")
            expr_attr_names["#label"] = "label"
            expr_attr_values[":label"] = update_data.label
        
        if update_data.icon is not None:
            update_expr_parts.append("icon = :icon")
            expr_attr_values[":icon"] = update_data.icon
        
        if update_data.path is not None:
            update_expr_parts.append("#path = :path")
            expr_attr_names["#path"] = "path"
            expr_attr_values[":path"] = update_data.path
        
        if update_data.permission is not None:
            update_expr_parts.append("permission = :permission")
            expr_attr_values[":permission"] = update_data.permission
        
        if update_data.isActive is not None:
            update_expr_parts.append("isActive = :isActive")
            expr_attr_values[":isActive"] = update_data.isActive
        
        if update_data.order is not None:
            update_expr_parts.append("#order = :order")
            expr_attr_names["#order"] = "order"
            expr_attr_values[":order"] = update_data.order
        
        # Always update timestamp and updatedBy
        update_expr_parts.append("updatedAt = :updatedAt")
        update_expr_parts.append("updatedBy = :updatedBy")
        expr_attr_values[":updatedAt"] = get_iso_timestamp()
        expr_attr_values[":updatedBy"] = update_data.updatedBy or authenticated_user or "system"
        
        update_expression = "SET " + ", ".join(update_expr_parts)
        
        # Update in DynamoDB
        update_kwargs = {
            "Key": {"PK": f"ITEM#{item_id}", "SK": f"METADATA#{item_id}"},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expr_attr_values,
            "ReturnValues": "ALL_NEW"
        }
        
        if expr_attr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_attr_names
        
        response = table.update_item(**update_kwargs)
        
        updated_item = convert_decimals(response["Attributes"])
        
        # Record history for each changed field
        for field, new_value in update_data.dict(exclude_unset=True, exclude={"updatedBy"}).items():
            old_value = existing_item.get(field)
            if old_value != new_value:
                record_history(
                    entity_type="item",
                    entity_id=item_id,
                    change_type="updated",
                    description=f"Updated item '{existing_item.get('label')}' - {field}",
                    changed_by=update_data.updatedBy or authenticated_user or "system",
                    field_name=field,
                    old_value=str(old_value),
                    new_value=str(new_value)
                )
        
        logger.info(f"Updated navigation item: {item_id}")
        return SuccessResponse.build(updated_item, 200)
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return ErrorResponse.build(f"Validation error: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error updating item: {str(e)}")
        return ErrorResponse.build(f"Failed to update navigation item: {str(e)}", 500)


def handle_delete_item(group_id: str, item_id: str, authenticated_user: Optional[str]) -> Dict[str, Any]:
    """DELETE /navigation/groups/{groupId}/items/{itemId} - Delete a navigation item"""
    try:
        # Fetch existing item
        response = table.get_item(Key={"PK": f"ITEM#{item_id}", "SK": f"METADATA#{item_id}"})
        
        if "Item" not in response:
            return ErrorResponse.build(f"Navigation item '{item_id}' not found", 404)
        
        item = response["Item"]
        
        # Verify item belongs to the group
        if item.get("parentId") != group_id:
            return ErrorResponse.build(f"Item '{item_id}' does not belong to group '{group_id}'", 400)
        
        item_label = item.get("label", "Unknown")
        
        # Delete the item
        table.delete_item(Key={"PK": f"ITEM#{item_id}", "SK": f"METADATA#{item_id}"})
        
        # Record history
        record_history(
            entity_type="item",
            entity_id=item_id,
            change_type="deleted",
            description=f"Deleted navigation item '{item_label}'",
            changed_by=authenticated_user or "system"
        )
        
        logger.info(f"Deleted navigation item: {item_id}")
        return SuccessResponse.build(None, 204)
        
    except Exception as e:
        logger.error(f"Error deleting item: {str(e)}")
        return ErrorResponse.build(f"Failed to delete navigation item: {str(e)}", 500)


# ============================================================================
# ENDPOINT HANDLERS - REORDER & MOVE
# ============================================================================

def handle_reorder_groups(event: Dict[str, Any], authenticated_user: Optional[str]) -> Dict[str, Any]:
    """POST /navigation/groups/reorder - Reorder navigation groups"""
    try:
        body = json.loads(event.get("body", "{}"))
        reorder_data = ReorderRequest(**body)
        
        # Fetch all specified groups and update their order
        updated_groups = []
        for index, group_id in enumerate(reorder_data.groupIds):
            new_order = index + 1
            
            # Update group order
            response = table.update_item(
                Key={"PK": f"GROUP#{group_id}", "SK": f"METADATA#{group_id}"},
                UpdateExpression="SET #order = :order, updatedAt = :updatedAt, updatedBy = :updatedBy",
                ExpressionAttributeNames={"#order": "order"},
                ExpressionAttributeValues={
                    ":order": new_order,
                    ":updatedAt": get_iso_timestamp(),
                    ":updatedBy": authenticated_user or "system"
                },
                ReturnValues="ALL_NEW"
            )
            
            updated_groups.append(convert_decimals(response["Attributes"]))
        
        # Record history
        record_history(
            entity_type="group",
            entity_id="multiple",
            change_type="reordered",
            description=f"Reordered {len(reorder_data.groupIds)} navigation groups",
            changed_by=authenticated_user or "system"
        )
        
        # Return all groups with items
        all_groups = get_all_groups_with_items()
        
        logger.info(f"Reordered {len(reorder_data.groupIds)} navigation groups")
        return SuccessResponse.build(all_groups, 200)
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return ErrorResponse.build(f"Validation error: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error reordering groups: {str(e)}")
        return ErrorResponse.build(f"Failed to reorder navigation groups: {str(e)}", 500)


def handle_reorder_items(group_id: str, event: Dict[str, Any], authenticated_user: Optional[str]) -> Dict[str, Any]:
    """POST /navigation/groups/{groupId}/items/reorder - Reorder items within a group"""
    try:
        # Verify group exists
        response = table.get_item(Key={"PK": f"GROUP#{group_id}", "SK": f"METADATA#{group_id}"})
        
        if "Item" not in response:
            return ErrorResponse.build(f"Navigation group '{group_id}' not found", 404)
        
        group = response["Item"]
        
        body = json.loads(event.get("body", "{}"))
        reorder_data = ReorderItemsRequest(**body)
        
        # Update order for each item
        for index, item_id in enumerate(reorder_data.itemIds):
            new_order = index + 1
            
            table.update_item(
                Key={"PK": f"ITEM#{item_id}", "SK": f"METADATA#{item_id}"},
                UpdateExpression="SET #order = :order, updatedAt = :updatedAt, updatedBy = :updatedBy",
                ExpressionAttributeNames={"#order": "order"},
                ExpressionAttributeValues={
                    ":order": new_order,
                    ":updatedAt": get_iso_timestamp(),
                    ":updatedBy": authenticated_user or "system"
                }
            )
        
        # Record history
        record_history(
            entity_type="item",
            entity_id="multiple",
            change_type="reordered",
            description=f"Reordered {len(reorder_data.itemIds)} items in group '{group.get('label')}'",
            changed_by=authenticated_user or "system"
        )
        
        # Fetch updated group with items
        items_response = table.scan(
            FilterExpression="entityType = :entity_type AND parentId = :parent_id",
            ExpressionAttributeValues={
                ":entity_type": ENTITY_TYPE_ITEM,
                ":parent_id": group_id
            }
        )
        
        items = [convert_decimals(item) for item in items_response.get("Items", [])]
        items.sort(key=lambda x: x.get("order", 999))
        
        result = convert_decimals(group)
        result["items"] = items
        
        logger.info(f"Reordered {len(reorder_data.itemIds)} items in group {group_id}")
        return SuccessResponse.build(result, 200)
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return ErrorResponse.build(f"Validation error: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error reordering items: {str(e)}")
        return ErrorResponse.build(f"Failed to reorder navigation items: {str(e)}", 500)


def handle_move_item(event: Dict[str, Any], authenticated_user: Optional[str]) -> Dict[str, Any]:
    """POST /navigation/items/move - Move item between groups"""
    try:
        body = json.loads(event.get("body", "{}"))
        move_data = MoveItemRequest(**body)
        
        # Verify item exists
        item_response = table.get_item(Key={"PK": f"ITEM#{move_data.itemId}", "SK": f"METADATA#{move_data.itemId}"})
        
        if "Item" not in item_response:
            return ErrorResponse.build(f"Navigation item '{move_data.itemId}' not found", 404)
        
        item = item_response["Item"]
        
        # Verify current parent matches
        if item.get("parentId") != move_data.fromGroupId:
            return ErrorResponse.build(f"Item does not belong to source group '{move_data.fromGroupId}'", 400)
        
        # Verify target group exists
        to_group_response = table.get_item(Key={"PK": f"GROUP#{move_data.toGroupId}", "SK": f"METADATA#{move_data.toGroupId}"})
        
        if "Item" not in to_group_response:
            return ErrorResponse.build(f"Target navigation group '{move_data.toGroupId}' not found", 404)
        
        to_group = to_group_response["Item"]
        
        # Check if label is unique in target group
        if not check_unique_item_label_in_group(item.get("label"), move_data.toGroupId, exclude_id=move_data.itemId):
            return ErrorResponse.build(f"Item label '{item.get('label')}' already exists in target group", 400)
        
        # Update item's parentId
        table.update_item(
            Key={"PK": f"ITEM#{move_data.itemId}", "SK": f"METADATA#{move_data.itemId}"},
            UpdateExpression="SET parentId = :parentId, updatedAt = :updatedAt, updatedBy = :updatedBy",
            ExpressionAttributeValues={
                ":parentId": move_data.toGroupId,
                ":updatedAt": get_iso_timestamp(),
                ":updatedBy": authenticated_user or "system"
            }
        )
        
        # Record history
        record_history(
            entity_type="item",
            entity_id=move_data.itemId,
            change_type="moved",
            description=f"Moved item '{item.get('label')}' from group '{move_data.fromGroupId}' to '{to_group.get('label')}'",
            changed_by=authenticated_user or "system",
            field_name="parentId",
            old_value=move_data.fromGroupId,
            new_value=move_data.toGroupId
        )
        
        # Fetch both groups with items
        from_group_response = table.get_item(Key={"PK": f"GROUP#{move_data.fromGroupId}", "SK": f"METADATA#{move_data.fromGroupId}"})
        from_group = convert_decimals(from_group_response["Item"]) if "Item" in from_group_response else None
        
        # Get items for from_group
        if from_group:
            from_items_response = table.scan(
                FilterExpression="entityType = :entity_type AND parentId = :parent_id",
                ExpressionAttributeValues={
                    ":entity_type": ENTITY_TYPE_ITEM,
                    ":parent_id": move_data.fromGroupId
                }
            )
            from_items = [convert_decimals(item) for item in from_items_response.get("Items", [])]
            from_items.sort(key=lambda x: x.get("order", 999))
            from_group["items"] = from_items
        
        # Get items for to_group
        to_group_dict = convert_decimals(to_group)
        to_items_response = table.scan(
            FilterExpression="entityType = :entity_type AND parentId = :parent_id",
            ExpressionAttributeValues={
                ":entity_type": ENTITY_TYPE_ITEM,
                ":parent_id": move_data.toGroupId
            }
        )
        to_items = [convert_decimals(item) for item in to_items_response.get("Items", [])]
        to_items.sort(key=lambda x: x.get("order", 999))
        to_group_dict["items"] = to_items
        
        result = {
            "fromGroup": from_group,
            "toGroup": to_group_dict
        }
        
        logger.info(f"Moved item {move_data.itemId} from group {move_data.fromGroupId} to {move_data.toGroupId}")
        return SuccessResponse.build(result, 200)
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return ErrorResponse.build(f"Validation error: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error moving item: {str(e)}")
        return ErrorResponse.build(f"Failed to move navigation item: {str(e)}", 500)


# ============================================================================
# ENDPOINT HANDLERS - HISTORY
# ============================================================================

def handle_get_history(authenticated_user: Optional[str]) -> Dict[str, Any]:
    """GET /navigation/history - Fetch navigation change history"""
    try:
        # Fetch all history records
        response = table.scan(
            FilterExpression="entityType = :entity_type",
            ExpressionAttributeValues={":entity_type": ENTITY_TYPE_HISTORY}
        )
        
        history_items = [convert_decimals(item) for item in response.get("Items", [])]
        
        # Sort by timestamp (newest first)
        history_items.sort(key=lambda x: x.get("changedAt", ""), reverse=True)
        
        logger.info(f"Fetched {len(history_items)} history records")
        return SuccessResponse.build(history_items, 200)
        
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        return ErrorResponse.build(f"Failed to fetch navigation history: {str(e)}", 500)


# ============================================================================
# LAMBDA HANDLER
# ============================================================================

def lambda_handler(event, context):
    """Main Lambda handler for navigation API"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract HTTP method and path
    http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    raw_path = event.get("path") or event.get("rawPath", "")
    path_parameters = event.get("pathParameters") or {}
    
    # Normalize path - remove stage prefix if present
    path = raw_path
    if path.startswith("/dev/") or path.startswith("/prod/") or path.startswith("/staging/"):
        path = "/" + "/".join(path.split("/")[2:])
    
    method = http_method.upper() if http_method else None
    
    logger.info(f"Processing request: {method} {path}")
    logger.info(f"Path parameters: {json.dumps(path_parameters)}")
    
    if not method:
        logger.error("Could not extract HTTP method from event")
        return ErrorResponse.build("Could not determine HTTP method from request", 400)
    
    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return SuccessResponse.build({"message": "CORS preflight successful"}, 200)
    
    # Extract authenticated user
    authenticated_user = extract_user_from_event(event)
    
    try:
        # ====== ROUTING LOGIC ======
        
        # History endpoint
        if method == "GET" and path == "/navigation/history":
            return handle_get_history(authenticated_user)
        
        # Reorder groups
        elif method == "POST" and path == "/navigation/groups/reorder":
            return handle_reorder_groups(event, authenticated_user)
        
        # Move item between groups
        elif method == "POST" and path == "/navigation/items/move":
            return handle_move_item(event, authenticated_user)
        
        # Reorder items within a group
        elif method == "POST" and "/navigation/groups/" in path and path.endswith("/items/reorder"):
            group_id = path_parameters.get("groupId")
            if not group_id:
                return ErrorResponse.build("Missing groupId parameter", 400)
            return handle_reorder_items(group_id, event, authenticated_user)
        
        # List groups
        elif method == "GET" and path == "/navigation/groups":
            return handle_list_groups(authenticated_user)
        
        # Create group
        elif method == "POST" and path == "/navigation/groups":
            return handle_create_group(event, authenticated_user)
        
        # Update group
        elif method == "PATCH" and "/navigation/groups/" in path and "/items" not in path:
            group_id = path_parameters.get("groupId")
            if not group_id:
                return ErrorResponse.build("Missing groupId parameter", 400)
            return handle_update_group(group_id, event, authenticated_user)
        
        # Delete group
        elif method == "DELETE" and "/navigation/groups/" in path and "/items" not in path:
            group_id = path_parameters.get("groupId")
            if not group_id:
                return ErrorResponse.build("Missing groupId parameter", 400)
            return handle_delete_group(group_id, authenticated_user)
        
        # Create item
        elif method == "POST" and "/navigation/groups/" in path and path.endswith("/items"):
            group_id = path_parameters.get("groupId")
            if not group_id:
                return ErrorResponse.build("Missing groupId parameter", 400)
            return handle_create_item(group_id, event, authenticated_user)
        
        # Update item
        elif method == "PATCH" and "/navigation/groups/" in path and "/items/" in path:
            group_id = path_parameters.get("groupId")
            item_id = path_parameters.get("itemId")
            if not group_id or not item_id:
                return ErrorResponse.build("Missing groupId or itemId parameter", 400)
            return handle_update_item(group_id, item_id, event, authenticated_user)
        
        # Delete item
        elif method == "DELETE" and "/navigation/groups/" in path and "/items/" in path:
            group_id = path_parameters.get("groupId")
            item_id = path_parameters.get("itemId")
            if not group_id or not item_id:
                return ErrorResponse.build("Missing groupId or itemId parameter", 400)
            return handle_delete_item(group_id, item_id, authenticated_user)
        
        else:
            return ErrorResponse.build(f"Endpoint not found: {method} {path}", 404)
    
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")
        return ErrorResponse.build(f"Internal server error: {str(e)}", 500)
