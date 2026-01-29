import json
import os
import boto3
import logging
from datetime import datetime
from decimal import Decimal
import re
from shared.response_utils import SuccessResponse, ErrorResponse
from pydantic import BaseModel, ValidationError, Field

# Initialize DynamoDB and logging
TABLE_NAME = os.environ.get("TABLE_NAME", "regions")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Validate regionType and regionCode and parentCode
def validate_delete_keys(params):
    if not isinstance(params, dict):
        return False
    regiontype = params.get("regionType")
    regioncode = params.get("regionCode")
    parentcode = params.get("parentCode")

    if regiontype != 'STATE' and not (isinstance(parentcode, str) and parentcode):
        return False

    if not (isinstance(regiontype, str) and regiontype and isinstance(regioncode, str) and regioncode):
        return False

    return True

def simplify(item):
    """
    Simplify DynamoDB item format by extracting values from 'S', 'N', 'BOOL', 'M', or 'L' types,
    and handle Decimal objects for JSON serialization.

    Args:
        item: Dictionary in DynamoDB format (e.g., {'PK': {'S': 'STATE#TS'}}) or simplified format

    Returns:
        Simplified Python dictionary with native types (e.g., {'PK': 'STATE#TS', 'isActive': True})
    """
    out = {}

    """Review this function for correctness and efficiency."""
    def simplify_value(v):
        """Recursively simplify DynamoDB value types and handle Decimal."""
        if isinstance(v, Decimal):
            # Convert Decimal to int if it's a whole number, else float
            return int(v) if v == int(v) else float(v)
        if isinstance(v, dict):
            logger.info(f"Simplifying dict value: {v}")
            if 'S' in v:
                return v['S']
            elif 'N' in v:
                # Convert numeric strings to int or float
                return int(v['N']) if v['N'].isdigit() else float(v['N'])
            elif 'BOOL' in v:
                return v['BOOL']
            elif 'M' in v:
                # Simplify nested map
                return {k: simplify_value(nv) for k, nv in v['M'].items()}
            elif 'L' in v:
                # Simplify list of values
                return [simplify_value(x) for x in v['L']]
        elif isinstance(v, list):
            return [simplify_value(x) for x in v]
        elif isinstance(v, dict):
            return {k: simplify_value(nv) for k, nv in v.items()}
        return v

    logger.debug(f"Simplifying item: {item}")
    for k, v in item.items():
        if k == 'metadata':
            # Special handling for metadata to ensure population is int
            metadata = simplify_value(v)
            logger.info(f"Simplified metadata: {metadata}")
            if isinstance(metadata, dict) and 'population' in metadata:
                try:
                    metadata['population'] = int(metadata['population'])
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid population in metadata: {metadata['population']} must be convertible to integer")
                    raise ValueError(f"Invalid population in metadata: {metadata['population']} must be convertible to integer")
            out[k] = metadata
        else:
            out[k] = simplify_value(v)
    
    logger.debug(f"Simplified item: {out}")
    return out

def transform_items_to_json(items):
    """Transform a list of DynamoDB items to a list of JSON objects."""
    if not items:
        return []
    
    results = []
    for item in items:
        item = simplify(item)
        if not item or not isinstance(item, dict):
            logger.info(f"Skipping invalid item: {item}")
            continue
            
        region_type = item.get("RegionType")
        if not region_type:
            logger.info(f"Skipping item with missing RegionType: {item}")
            continue

        result = {
            "id": item.get("PK").split("#")[-1] if "#" in item.get("PK", "") else item.get("PK"),
            "type": region_type,
            "code": item.get("RegionCode"),
            "name": item.get("RegionName"),
            "isActive": item.get("isActive", True),
            "createdAt": item.get("created_date"),
            "updatedAt": item.get("updated_date"),
            "createdBy": item.get("created_by"),
            "updatedBy": item.get("updated_by")
        }
        logger.info(f"Transforming item: {item} to result: {result}")
        # Explicitly add population and pincode for VILLAGE and HABITATION
        if region_type in ["VILLAGE", "HABITATION"]:
            metadata = item.get("metadata", {})
            if isinstance(metadata, dict):
                result["population"] = metadata.get("population")
                result["pincode"] = metadata.get("pincode")
        else:
            result["metadata"] = item.get("metadata", {})
        if region_type != "STATE":
            result["stateCode"] = item.get("StateCode")
        if region_type in ["MANDAL", "VILLAGE", "HABITATION"]:
            result["districtCode"] = item.get("DistrictCode")
        if region_type in ["VILLAGE", "HABITATION"]:
            result["mandalCode"] = item.get("MandalCode")
        if region_type == "HABITATION":
            result["villageCode"] = item.get("VillageCode")
            result["path"] = item.get("Path")
        
        results.append(result)
    
    return results

# Pydantic model for validation
class RegionDetails(BaseModel):
    # PK: str = None
    # SK: str = None
    RegionType: str = None
    RegionCode: str = None
    RegionName: str = None
    StateCode: str = None
    DistrictCode: str = None
    MandalCode: str = None
    VillageCode: str = None
    # Path: str = None
    # created_date: str = None
    # updated_date: str = None
    created_by: str = None
    updated_by: str = None
    isActive: bool = True
    metadata: dict = {}

    class Config:
        extra = "forbid"

    @classmethod
    def validate_for_type(cls, data):
        region_type = data.get("RegionType")
        required = []
        if region_type == "STATE":
            required = [ "RegionType", "RegionCode", "RegionName", "isActive"]
        elif region_type == "DISTRICT":
            required = ["RegionType", "RegionCode", "RegionName", "StateCode", "isActive"]
        elif region_type == "MANDAL":
            required = ["RegionType", "RegionCode", "RegionName", "StateCode", "DistrictCode", "isActive"]
        elif region_type == "VILLAGE":
            required = ["RegionType", "RegionCode", "RegionName", "StateCode", "DistrictCode", "MandalCode", "isActive", "metadata"]
        elif region_type == "HABITATION":
            required = ["RegionType", "RegionCode", "RegionName", "StateCode", "DistrictCode", "MandalCode", "VillageCode", "isActive", "metadata"]
        else:
            raise ValueError(f"Invalid RegionType: {region_type}")

        missing = [f for f in required if f not in data or data[f] is None]
        if missing:
            raise ValueError(f"Missing required fields for {region_type}: {', '.join(missing)}")

        # Validate metadata based on RegionType
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError(f"metadata must be a dictionary for {region_type}, got {type(metadata)}")

        if region_type in {"STATE", "DISTRICT", "MANDAL"}:
            if metadata != {}:
                raise ValueError(f"metadata for {region_type} must be empty, got {metadata}")
        elif region_type == "VILLAGE":
            # if "population" not in metadata:
            #     raise ValueError(f"VILLAGE metadata must contain 'population', got {metadata}")
            if "population" in metadata and (not isinstance(metadata["population"], int) or metadata["population"] < 0):
                raise ValueError(f"VILLAGE population must be a non-negative integer, got {metadata['population']}")
            # if "pincode" not in metadata:
            #     raise ValueError(f"VILLAGE metadata must contain 'pincode', got {metadata}")
            if "pincode" in metadata and (not isinstance(metadata["pincode"], str) or not re.match(r"^\d{6}$", metadata["pincode"])):
                raise ValueError(f"VILLAGE pincode must be a 6-digit string, got {metadata['pincode']}")
            allowed_keys = {"population", "pincode"}
            if set(metadata.keys()) - allowed_keys:
                raise ValueError(f"VILLAGE metadata contains unexpected keys: {set(metadata.keys()) - allowed_keys}")
        elif region_type == "HABITATION":
            # if "population" not in metadata:
            #     raise ValueError(f"HABITATION metadata must contain 'population', got {metadata}")
            if "population" in metadata and (not isinstance(metadata["population"], int) or metadata["population"] < 0):
                raise ValueError(f"HABITATION population must be a non-negative integer, got {metadata['population']}")
            # if "pincode" in metadata:
            #     raise ValueError(f"HABITATION metadata must not contain 'pincode', got {metadata}")
            allowed_keys = {"population"}
            if set(metadata.keys()) - allowed_keys:
                raise ValueError(f"HABITATION metadata contains unexpected keys: {set(metadata.keys()) - allowed_keys}")

    @classmethod
    def validate_pk_sk(cls, pk: str, sk: str) -> bool:
        return pk.startswith(("STATE#", "DISTRICT#", "MANDAL#", "VILLAGE#")) and sk.startswith(("STATE#", "DISTRICT#", "MANDAL#", "VILLAGE#", "HABITATION#"))

# Lambda handler
def lambda_handler(event, context):
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
    
    # Handle both v1.0 (REST API) and v2.0 (HTTP API) formats
    path = event.get("path") or event.get("rawPath", "")
    query_params = event.get("queryStringParameters") or {}
    
    logger.info(f"Path received: '{path}'")
    logger.info(f"Query params: {query_params}")

    try:
        # Special route for hierarchy endpoint - must be checked first
        if "/hierarchy" in path:
            logger.info("Hierarchy endpoint matched")
            if method == "GET":
                return handle_get_hierarchy()
            else:
                return ErrorResponse.build("Method not allowed for hierarchy endpoint", 405)
        
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

            # Validate isActive
            if not isinstance(item.get("isActive"), bool):
                logger.error(f"Invalid isActive value: {item.get('isActive')} (must be boolean)")
                return ErrorResponse.build(f"Invalid isActive value: {item.get('isActive')} (must be boolean)", 400)

            # Validate metadata # possible duplicate validations
            # metadata = item.get("metadata", {})
            # if not isinstance(metadata, dict):
            #     logger.error(f"Invalid metadata: must be a dictionary, got {type(metadata)}")
            #     return ErrorResponse.build(f"Invalid metadata: must be a dictionary, got {type(metadata)}", 400)

            # region_type = item.get("RegionType")
            # if region_type in {"STATE", "DISTRICT", "MANDAL"}:
            #     if metadata != {}:
            #         logger.error(f"Metadata for {region_type} must be empty, got {metadata}")
            #         return ErrorResponse.build(f"Metadata for {region_type} must be empty, got {metadata}", 400)

            # elif region_type == "VILLAGE":
            #     if not isinstance(metadata.get("population"), int) or metadata.get("population") < 0:
            #         logger.error(f"Invalid population for VILLAGE: {metadata.get('population')} (must be non-negative integer)")
            #         return ErrorResponse.build(f"Invalid population for VILLAGE: {metadata.get('population')} (must be non-negative integer)", 400)

            #     if not isinstance(metadata.get("pincode"), str) or not re.match(r"^\d{6}$", metadata.get("pincode", "")):
            #         logger.error(f"Invalid pincode for VILLAGE: {metadata.get('pincode')} (must be 6-digit string)")
            #         return ErrorResponse.build(f"Invalid pincode for VILLAGE: {metadata.get('pincode')} (must be 6-digit string)", 400)

            #     # Check for unexpected keys
            #     allowed_keys = {"population", "pincode"}
            #     if set(metadata.keys()) - allowed_keys:
            #         logger.error(f"Unexpected keys in VILLAGE metadata: {set(metadata.keys()) - allowed_keys}")
            #         return ErrorResponse.build(f"Unexpected keys in VILLAGE metadata: {set(metadata.keys()) - allowed_keys}", 400)

            # elif region_type == "HABITATION":
            #     if not isinstance(metadata.get("population"), int) or metadata.get("population") < 0:
            #         logger.error(f"Invalid population for HABITATION: {metadata.get('population')} (must be non-negative integer)")
            #         return ErrorResponse.build(f"Invalid population for HABITATION: {metadata.get('population')} (must be non-negative integer)", 400)

            #     if "pincode" in metadata:
            #         logger.error(f"HABITATION metadata must not contain pincode, got {metadata}")
            #         return ErrorResponse.build(f"HABITATION metadata must not contain pincode, got {metadata}", 400)
            #     # Check for unexpected keys
            #     allowed_keys = {"population"}
            #     if set(metadata.keys()) - allowed_keys:
            #         return ErrorResponse.build(f"Unexpected keys in HABITATION metadata: {set(metadata.keys()) - allowed_keys}", 400)

            if not item.get("created_by"):
                item["created_by"] = "admin"
            if not item.get("updated_by"):
                item["updated_by"] = "admin"

            # parent check
            region_type = item.get("RegionType")
            region_code = item.get("RegionCode")
            region_name = item.get("RegionName")
            state_code = item.get("StateCode")
            district_code = item.get("DistrictCode")
            mandal_code = item.get("MandalCode")
            village_code = item.get("VillageCode")
            # path = item.get("Path")
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
                # if not path:
                #     return {
                #         'statusCode': 400,
                #         'body': json.dumps({'error': 'Path is required for HABITATION'})
                #     }
                path = f"{state_code}#{district_code}#{mandal_code}#{village_code}#{region_code}"
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid RegionType. Must be STATE, DISTRICT, MANDAL, VILLAGE, or HABITATION'})
                }

            logger.info(f"Determined PK: {pk}, SK: {sk}, Parent Check: {parent_check}")

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

            # Finalize item with PK and SK
            item["PK"] = pk
            item["SK"] = sk
            if region_type == "HABITATION":
                item["Path"] = path

            logger.info(f"Finalized item for insertion: {item}")

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

            return SuccessResponse.build({"message": "created", "item": transform_items_to_json([item])})

        if method == "GET":
            try:
                # Extract query parameters
                query_params = event.get("queryStringParameters") or event.get("pathParameters") or {}
                region_type = query_params.get('regionType')
                region_code = query_params.get('regionCode')

                logger.info(f"Received request: regiontype={region_type}, regioncode={region_code}")

                # Validate region_type
                valid_region_types = ['STATE', 'DISTRICT', 'MANDAL', 'VILLAGE', 'HABITATION']
                if not region_type:
                    return ErrorResponse.build('Missing regiontype parameter', 400)
                if region_type.upper() not in valid_region_types:
                    return ErrorResponse.build(
                        f'Invalid regiontype. Must be one of: {", ".join(valid_region_types)}',
                        400
                    )

                region_type = region_type.upper()

                # Initialize response items
                items = []

                if region_code:
                    # Case: Filter by RegionCode (e.g., districts under a state)
                    if region_type == 'STATE':
                        return ErrorResponse.build(
                            'RegionCode not applicable for STATE queries',
                            400
                        )

                    # Define parent region for hierarchical queries
                    parent_region = {
                        'DISTRICT': 'STATE',
                        'MANDAL': 'DISTRICT',
                        'VILLAGE': 'MANDAL',
                        'HABITATION': 'VILLAGE'
                    }.get(region_type)

                    if not parent_region:
                        return ErrorResponse.build(
                            f'No parent region defined for {region_type}',
                            400
                        )

                    # Query DynamoDB with PK as parent region and SK starting with region_type
                    logger.info(f"Querying PK={parent_region}#{region_code}, SK begins_with {region_type}#")
                    response = table.query(
                        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                        ExpressionAttributeValues={
                            ':pk': f'{parent_region}#{region_code}',
                            ':sk': f'{region_type}#'
                        }
                    )
                    items = response.get('Items', [])

                    # Check if region_code exists (optional validation)
                    if not items and region_type != 'STATE':
                        logger.warning(f"No items found for {parent_region}#{region_code}")
                        return ErrorResponse.build(
                            f'No {region_type} found for {parent_region} with code {region_code}',
                            404
                        )

                else:
                    # Case: No RegionCode, return all items of the given RegionType
                    logger.info(f"Scanning for RegionType={region_type}")
                    response = table.scan(
                        FilterExpression='RegionType = :rt',
                        ExpressionAttributeValues={':rt': region_type}
                    )
                    items = response.get('Items', [])

                    # Handle pagination
                    while 'LastEvaluatedKey' in response:
                        logger.info(f"Paginating scan with LastEvaluatedKey={response['LastEvaluatedKey']}")
                        response = table.scan(
                            FilterExpression='RegionType = :rt',
                            ExpressionAttributeValues={':rt': region_type},
                            ExclusiveStartKey=response['LastEvaluatedKey']
                        )
                        items.extend(response.get('Items', []))

                # Prepare success response
                # response_data = {
                #     'count': len(items),
                #     'items': items
                # }
                logger.info(f"Returning {len(items)} items for regiontype={region_type}")
                return SuccessResponse.build(transform_items_to_json(items))

            # except ClientError as e:
            #     error_code = e.response['Error']['Code']
            #     error_message = e.response['Error']['Message']
            #     logger.error(f"DynamoDB ClientError: {error_code} - {error_message}")
            #     if error_code == 'ResourceNotFoundException':
            #         return create_error_response('DynamoDB table not found', 500)
            #     elif error_code == 'ProvisionedThroughputExceededException':
            #         return create_error_response('DynamoDB throughput exceeded, try again later', 429)
            #     else:
            #         return create_error_response(f'DynamoDB error: {error_message}', 500)

            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return ErrorResponse.build(f'Server error: {str(e)}', 500)


            # params = event.get("queryStringParameters") or event.get("pathParameters") or {}
            # if validate_keys(params):
            #     pk = params.get("PK")
            #     sk = params.get("SK")
            #     try:
            #         r = table.get_item(Key={"PK": pk, "SK": sk})
            #         item = r.get("Item")
            #         if not item:
            #             return ErrorResponse.build("Item not found", 404)
            #         return SuccessResponse.build(transform_item_to_json(item))
            #     except Exception as e:
            #         logger.error(f"DynamoDB get_item failed: {e}")
            #         return ErrorResponse.build("Database error", 500)
            # else:
            #     try:
            #         # Default list: query items under a sample PK, using SK prefix for types
            #         response = table.query(
            #             KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            #             ExpressionAttributeValues={":pk": "STATE#TS", ":sk": "STATE#"}
            #         )
            #         items = response.get("Items", [])
            #         return SuccessResponse.build([transform_item_to_json(item) for item in items])
            #     except Exception as e:
            #         logger.error(f"DynamoDB query failed: {e}")
            #         return ErrorResponse.build("Database error", 500)

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

            # Validate isActive
            if not isinstance(item.get("isActive"), bool):
                logger.error(f"Invalid isActive value: {item.get('isActive')} (must be boolean)")
                return ErrorResponse.build(f"Invalid isActive value: {item.get('isActive')} (must be boolean)", 400)
            

            sysdate = datetime.utcnow().isoformat() + "Z"
            item["updated_date"] = sysdate
            if not item.get("created_by"):
                item["created_by"] = "admin"
            if not item.get("updated_by"):
                item["updated_by"] = "admin"

            user = event.get("requestContext", {}).get("authorizer", {}).get("principalId", "admin")
            enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"

            # parent check
            region_type = item.get("RegionType")
            region_code = item.get("RegionCode")
            region_name = item.get("RegionName")
            state_code = item.get("StateCode")
            district_code = item.get("DistrictCode")
            mandal_code = item.get("MandalCode")
            village_code = item.get("VillageCode")
            # path = item.get("Path")
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

            elif region_type == 'DISTRICT':
                if not state_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode is required for DISTRICT'})
                    }
                pk = f"STATE#{state_code}"
                sk = f"DISTRICT#{region_code}"

            elif region_type == 'MANDAL':
                if not state_code or not district_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode and DistrictCode are required for MANDAL'})
                    }
                pk = f"DISTRICT#{district_code}"
                sk = f"MANDAL#{region_code}"

            elif region_type == 'VILLAGE':
                if not state_code or not district_code or not mandal_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode, DistrictCode, and MandalCode are required for VILLAGE'})
                    }
                pk = f"MANDAL#{mandal_code}"
                sk = f"VILLAGE#{region_code}"

            elif region_type == 'HABITATION':
                if not state_code or not district_code or not mandal_code or not village_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode, DistrictCode, MandalCode, and VillageCode are required for HABITATION'})
                    }
                pk = f"VILLAGE#{village_code}"
                sk = f"HABITATION#{region_code}"

            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid RegionType. Must be STATE, DISTRICT, MANDAL, VILLAGE, or HABITATION'})
                }

            logger.info(f"Determined PK: {pk}, SK: {sk}")

            # Finalize item with PK and SK
            item["PK"] = pk
            item["SK"] = sk

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
                return SuccessResponse.build({"message": "updated", "item": transform_items_to_json([item])})
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
            params = event.get("queryStringParameters") or event.get("pathParameters") or {}
            if not validate_delete_keys(params):
                logger.warning("Missing ParentCode(excluding STATE) or invalid RegionType and RegionCode in DELETE params")
                return ErrorResponse.build("Missing ParentCode(excluding STATE) or invalid RegionType and RegionCode for DELETE", 400)

            region_type = params.get("regionType")
            region_code = params.get("regionCode")
            parent_code = params.get("parentCode")
            

            # Define PK, SK, and parent check based on RegionType
            if region_type == 'STATE':
                pk = f"STATE#{region_code}"
                sk = f"STATE#{region_code}"

            elif region_type == 'DISTRICT':
                state_code = parent_code
                if not state_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'StateCode is required for DISTRICT'})
                    }
                pk = f"STATE#{state_code}"
                sk = f"DISTRICT#{region_code}"

            elif region_type == 'MANDAL':
                district_code = parent_code
                if not district_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'DistrictCode is required for MANDAL'})
                    }
                pk = f"DISTRICT#{district_code}"
                sk = f"MANDAL#{region_code}"

            elif region_type == 'VILLAGE':
                mandal_code = parent_code
                if not mandal_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'MandalCode is required for VILLAGE'})
                    }
                pk = f"MANDAL#{mandal_code}"
                sk = f"VILLAGE#{region_code}"

            elif region_type == 'HABITATION':
                village_code = parent_code
                if not village_code:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'VillageCode is required for HABITATION'})
                    }
                pk = f"VILLAGE#{village_code}"
                sk = f"HABITATION#{region_code}"

            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid RegionType. Must be STATE, DISTRICT, MANDAL, VILLAGE, or HABITATION'})
                }


            user = event.get("requestContext", {}).get("authorizer", {}).get("principalId", "admin")
            enable_audit = os.environ.get("ENABLE_AUDIT_LOG", "false").lower() == "true"

            logger.info(f"Determined PK: {pk}, SK: {sk} for deletion")

            # Check for child items before deleting
            child_type_map = {
                "STATE": "DISTRICT",
                "DISTRICT": "MANDAL",
                "MANDAL": "VILLAGE",
                "VILLAGE": "HABITATION"
            }
            child_type = child_type_map.get(region_type)
            logger.info(f"Checking for child items of type: {child_type}")
            if child_type:
                try:
                    response = table.query(
                        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                        ExpressionAttributeValues={
                            ':pk': sk, # looking for child items under this sk
                            ':sk': f'{child_type}#'
                        }
                    )
                    children = response.get('Items', [])
                    logger.info(f"Found {children} child items")
                    if children:
                        logger.warning(f"Cannot delete {region_type} {pk}/{sk}: child {child_type} exists.")
                        return ErrorResponse.build(f"Cannot delete: child {child_type} exists for this region.", 409)
                except Exception as e:
                    logger.error(f"Error checking for child items: {e}")
                    return ErrorResponse.build("Database error while checking for child items", 500)

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


def handle_get_hierarchy():
    """
    Get complete hierarchical location structure for dropdowns.
    Returns nested structure: states -> districts -> mandals -> villages
    """
    try:
        logger.info("Fetching complete region hierarchy")
        
        # Scan all regions
        response = table.scan()
        items = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))
        
        logger.info(f"Scanned {len(items)} total region items")
        
        # Organize by type
        states = []
        districts_by_state = {}
        mandals_by_district = {}
        villages_by_mandal = {}
        
        for item in items:
            item = simplify(item)
            region_type = item.get('RegionType')
            
            if not region_type:
                continue
            
            if region_type == 'STATE':
                states.append({
                    'code': item.get('RegionCode'),
                    'name': item.get('RegionName')
                })
            elif region_type == 'DISTRICT':
                state_code = item.get('StateCode')
                if state_code:
                    if state_code not in districts_by_state:
                        districts_by_state[state_code] = []
                    districts_by_state[state_code].append({
                        'code': item.get('RegionCode'),
                        'name': item.get('RegionName')
                    })
            elif region_type == 'MANDAL':
                district_code = item.get('DistrictCode')
                if district_code:
                    if district_code not in mandals_by_district:
                        mandals_by_district[district_code] = []
                    mandals_by_district[district_code].append({
                        'code': item.get('RegionCode'),
                        'name': item.get('RegionName')
                    })
            elif region_type == 'VILLAGE':
                mandal_code = item.get('MandalCode')
                if mandal_code:
                    if mandal_code not in villages_by_mandal:
                        villages_by_mandal[mandal_code] = []
                    villages_by_mandal[mandal_code].append({
                        'code': item.get('RegionCode'),
                        'name': item.get('RegionName')
                    })
        
        # Sort all arrays alphabetically by name
        states.sort(key=lambda x: x['name'])
        for state_code in districts_by_state:
            districts_by_state[state_code].sort(key=lambda x: x['name'])
        for district_code in mandals_by_district:
            mandals_by_district[district_code].sort(key=lambda x: x['name'])
        for mandal_code in villages_by_mandal:
            villages_by_mandal[mandal_code].sort(key=lambda x: x['name'])
        
        hierarchy = {
            'states': states,
            'districts': districts_by_state,
            'mandals': mandals_by_district,
            'villages': villages_by_mandal
        }
        
        logger.info(f"Hierarchy built: {len(states)} states, {len(districts_by_state)} district groups, "
                   f"{len(mandals_by_district)} mandal groups, {len(villages_by_mandal)} village groups")
        
        return SuccessResponse.build(hierarchy)
        
    except Exception as e:
        logger.error(f"Hierarchy error: {str(e)}")
        return ErrorResponse.build(f"Error fetching hierarchy: {str(e)}", 500)
