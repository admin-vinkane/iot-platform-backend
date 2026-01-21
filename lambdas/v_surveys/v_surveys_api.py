import json
import os
import boto3
import logging
import re
import uuid
from datetime import datetime
from decimal import Decimal
import decimal
from pydantic import BaseModel, ValidationError, Field
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any, List
from shared.response_utils import SuccessResponse, ErrorResponse

TABLE_NAME = os.environ.get("TABLE_NAME", "v_surveys_dev")
REGIONS_TABLE_NAME = os.environ.get("REGIONS_TABLE_NAME", "v_regions_dev")
S3_BUCKET = os.environ.get("S3_BUCKET", "my-lambda-bucket-vinkane-dev")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)
regions_table = dynamodb.Table(REGIONS_TABLE_NAME)
s3_client = boto3.client("s3")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Pydantic Models

class MeasurementValue(BaseModel):
    value: float
    unit: str

class PersonnelContact(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None

class Survey(BaseModel):
    PK: str
    SK: str = "META"
    EntityType: str = "SURVEY"
    SurveyId: str
    Status: str = "draft"  # draft | submitted
    
    # Surveyor Info
    SurveyorName: str
    SurveyorPhone: str
    SurveyorEmail: Optional[str] = None
    SurveyDate: str
    
    # Location (Required)
    State: str
    District: str
    Mandal: str
    Village: str
    Habitation: Optional[str] = None
    Latitude: Optional[float] = None
    Longitude: Optional[float] = None
    
    # Tank Details
    TankCapacity: Optional[MeasurementValue] = None
    TankHeight: Optional[MeasurementValue] = None
    TankToMotorDistance: Optional[MeasurementValue] = None
    TankMaterial: Optional[str] = None
    TankCondition: Optional[str] = None
    
    # Motor Details
    MotorCapacity: Optional[MeasurementValue] = None
    MotorPhaseType: Optional[str] = None
    MotorAge: Optional[MeasurementValue] = None
    MotorManufacturer: Optional[str] = None
    MotorModel: Optional[str] = None
    MotorSerialNumber: Optional[str] = None
    MotorWorkingCondition: Optional[str] = None
    MotorConditionNotes: Optional[str] = None
    
    # Starter Details
    StarterType: Optional[str] = None
    StarterAge: Optional[MeasurementValue] = None
    StarterManufacturer: Optional[str] = None
    StarterWorkingCondition: Optional[str] = None
    StarterConditionNotes: Optional[str] = None
    
    # Power Supply
    PowerSupplyAtTank: Optional[str] = None
    PowerSupplySource: Optional[str] = None
    ConnectionType: Optional[str] = None
    Voltage: Optional[float] = None
    FuseRatings: Optional[str] = None
    PowerQuality: Optional[str] = None
    
    # Chlorine Setup
    ChlorineSystemAvailable: Optional[bool] = None
    ChlorineTankSetupNotes: Optional[str] = None
    
    # Site Personnel
    HabitationEngineeringAssistant: Optional[str] = None
    HabitationPumpOperator: Optional[PersonnelContact] = None
    TechnicianEngineer: Optional[PersonnelContact] = None
    ViklatSalesTeam: Optional[str] = None
    AssistantEngineer: Optional[PersonnelContact] = None
    SarpanchContact: Optional[PersonnelContact] = None
    
    # Additional Notes
    SiteStatus: Optional[str] = None
    GeneralNotes: Optional[str] = None
    Recommendations: Optional[str] = None
    
    # Metadata
    CreatedDate: Optional[str] = None
    UpdatedDate: Optional[str] = None
    SubmittedDate: Optional[str] = None
    CreatedBy: Optional[str] = None
    UpdatedBy: Optional[str] = None
    
    class Config:
        extra = "allow"

class SurveyImage(BaseModel):
    PK: str
    SK: str
    EntityType: str = "SURVEY_IMAGE"
    ImageId: str
    ImageUrl: str
    Description: Optional[str] = None
    UploadedDate: str
    FileSize: Optional[int] = None
    MimeType: Optional[str] = None
    
    class Config:
        extra = "forbid"

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    # Extract HTTP method
    method = (
        event.get("httpMethod") or 
        event.get("requestContext", {}).get("http", {}).get("method") or
        event.get("requestContext", {}).get("httpMethod")
    )
    
    logger.info(f"Extracted method: {method}")
    
    if not method:
        logger.error("Could not extract HTTP method from event")
        return ErrorResponse.build("Could not determine HTTP method from request", 400)

    # Handle OPTIONS preflight request for CORS
    if method == "OPTIONS":
        return SuccessResponse.build({"message": "CORS preflight successful"}, 200)

    # Extract path and path parameters
    path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path") or ""
    path_parameters = event.get("pathParameters") or {}
    params = event.get("queryStringParameters") or {}
    
    if method == "POST":
        # POST /surveys/{surveyId}/submit
        if path_parameters.get("surveyId") and "/submit" in path:
            return handle_submit_survey(path_parameters.get("surveyId"), event)
        
        # POST /surveys/{surveyId}/images
        if path_parameters.get("surveyId") and "/images" in path:
            return handle_upload_image(path_parameters.get("surveyId"), event)
        
        # POST /surveys - Create new survey
        return handle_create_survey(event)
    
    elif method == "GET":
        # GET /surveys/{surveyId}
        if path_parameters.get("surveyId"):
            return handle_get_survey(path_parameters.get("surveyId"))
        
        # GET /surveys - List surveys
        return handle_list_surveys(params)
    
    elif method == "PUT":
        # PUT /surveys/{surveyId}
        if path_parameters.get("surveyId"):
            return handle_update_survey(path_parameters.get("surveyId"), event)
        
        return ErrorResponse.build("Survey ID required for update", 400)
    
    elif method == "DELETE":
        # DELETE /surveys/{surveyId}/images/{imageId}
        if path_parameters.get("surveyId") and path_parameters.get("imageId"):
            return handle_delete_image(path_parameters.get("surveyId"), path_parameters.get("imageId"))
        
        # DELETE /surveys/{surveyId}
        if path_parameters.get("surveyId"):
            return handle_delete_survey(path_parameters.get("surveyId"))
        
        return ErrorResponse.build("Survey ID required for delete", 400)

    return ErrorResponse.build("Method not allowed", 405)

def handle_create_survey(event):
    """Create a new survey (draft status)"""
    try:
        body = json.loads(event.get("body", "{}"))
        body = convert_floats_to_decimal(body)
    except Exception as e:
        logger.error(f"Failed to parse body: {e}")
        return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
    
    # Generate survey ID
    survey_id = body.get("SurveyId") or f"SRV{str(uuid.uuid4())[:8].upper()}"
    
    # Set required fields
    body["SurveyId"] = survey_id
    body["PK"] = f"SURVEY#{survey_id}"
    body["SK"] = "META"
    body["EntityType"] = "SURVEY"
    body["Status"] = "draft"
    
    # Set timestamps
    timestamp = datetime.utcnow().isoformat() + "Z"
    body["CreatedDate"] = timestamp
    body["UpdatedDate"] = timestamp
    body["CreatedBy"] = body.get("CreatedBy", "system")
    
    # Validate required fields for draft
    if not body.get("SurveyorName"):
        return ErrorResponse.build("SurveyorName is required", 400)
    if not body.get("SurveyorPhone"):
        return ErrorResponse.build("SurveyorPhone is required", 400)
    if not body.get("SurveyDate"):
        return ErrorResponse.build("SurveyDate is required", 400)
    if not body.get("State"):
        return ErrorResponse.build("State is required", 400)
    if not body.get("District"):
        return ErrorResponse.build("District is required", 400)
    if not body.get("Mandal"):
        return ErrorResponse.build("Mandal is required", 400)
    if not body.get("Village"):
        return ErrorResponse.build("Village is required", 400)
    
    try:
        # Validate with Pydantic
        validated_survey = Survey(**body)
        
        # Store in DynamoDB
        table.put_item(Item=body)
        
        logger.info(f"Created survey {survey_id}")
        return SuccessResponse.build({"created": simplify(body)}, 201)
    
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return ErrorResponse.build(f"Validation error: {str(e)}", 400)
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    except Exception as e:
        logger.error(f"Create error: {str(e)}")
        return ErrorResponse.build(f"Create error: {str(e)}", 500)

def handle_get_survey(survey_id):
    """Get a single survey with all images"""
    try:
        # Get survey metadata
        response = table.get_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": "META"
            }
        )
        
        if "Item" not in response:
            return ErrorResponse.build(f"Survey {survey_id} not found", 404)
        
        survey = simplify(response["Item"])
        
        # Get all images for this survey
        images_response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": f"SURVEY#{survey_id}",
                ":sk": "IMAGE#"
            }
        )
        
        images = [simplify(img) for img in images_response.get("Items", [])]
        survey["images"] = images
        survey["imageCount"] = len(images)
        
        return SuccessResponse.build(survey)
    
    except ClientError as e:
        logger.error(f"Database error: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    except Exception as e:
        logger.error(f"Get error: {str(e)}")
        return ErrorResponse.build(f"Get error: {str(e)}", 500)

def handle_list_surveys(params):
    """List all surveys with optional filters"""
    try:
        state = params.get("state")
        district = params.get("district")
        status = params.get("status")
        surveyor = params.get("surveyor")
        from_date = params.get("fromDate")
        to_date = params.get("toDate")
        
        # Build filter expression
        from boto3.dynamodb.conditions import Attr
        filter_expr = Attr("EntityType").eq("SURVEY") & Attr("SK").eq("META")
        
        if state:
            filter_expr = filter_expr & Attr("State").eq(state)
        if district:
            filter_expr = filter_expr & Attr("District").eq(district)
        if status:
            filter_expr = filter_expr & Attr("Status").eq(status)
        if surveyor:
            filter_expr = filter_expr & Attr("SurveyorName").contains(surveyor)
        if from_date:
            filter_expr = filter_expr & Attr("SurveyDate").gte(from_date)
        if to_date:
            filter_expr = filter_expr & Attr("SurveyDate").lte(to_date)
        
        response = table.scan(FilterExpression=filter_expr)
        items = response.get("Items", [])
        
        # Add image count for each survey
        for item in items:
            survey_id = item.get("SurveyId")
            if survey_id:
                try:
                    images_response = table.query(
                        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                        ExpressionAttributeValues={
                            ":pk": f"SURVEY#{survey_id}",
                            ":sk": "IMAGE#"
                        },
                        Select="COUNT"
                    )
                    item["imageCount"] = images_response.get("Count", 0)
                except Exception as e:
                    logger.warning(f"Failed to get image count for {survey_id}: {str(e)}")
                    item["imageCount"] = 0
        
        surveys = [simplify(item) for item in items]
        
        return SuccessResponse.build({
            "surveys": surveys,
            "count": len(surveys)
        })
    
    except Exception as e:
        logger.error(f"List error: {str(e)}")
        return ErrorResponse.build(f"List error: {str(e)}", 500)

def handle_update_survey(survey_id, event):
    """Update an existing survey (draft only)"""
    try:
        body = json.loads(event.get("body", "{}"))
        body = convert_floats_to_decimal(body)
    except Exception as e:
        logger.error(f"Failed to parse body: {e}")
        return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
    
    # Check if survey exists and is draft
    try:
        response = table.get_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": "META"
            }
        )
        
        if "Item" not in response:
            return ErrorResponse.build(f"Survey {survey_id} not found", 404)
        
        existing_survey = response["Item"]
        
        if existing_survey.get("Status") == "submitted":
            return ErrorResponse.build("Cannot update submitted survey", 400)
    
    except ClientError as e:
        logger.error(f"Database error checking survey: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    
    # Remove fields that should not be updated
    body.pop("PK", None)
    body.pop("SK", None)
    body.pop("SurveyId", None)
    body.pop("EntityType", None)
    body.pop("Status", None)
    body.pop("CreatedDate", None)
    body.pop("SubmittedDate", None)
    
    # Update timestamp and updatedBy
    body["UpdatedDate"] = datetime.utcnow().isoformat() + "Z"
    if "CreatedBy" in body and "UpdatedBy" not in body:
        body["UpdatedBy"] = body.pop("CreatedBy")
    
    # Build update expression
    reserved_keywords = {"Status", "State", "Condition"}
    update_expr_parts = []
    expr_attr_names = {}
    expr_attr_vals = {}
    
    for k, v in body.items():
        if k in reserved_keywords:
            update_expr_parts.append(f"#attr_{k} = :{k}")
            expr_attr_names[f"#attr_{k}"] = k
        else:
            update_expr_parts.append(f"{k} = :{k}")
        expr_attr_vals[f":{k}"] = v
    
    update_expr = "SET " + ", ".join(update_expr_parts)
    
    try:
        response = table.update_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": "META"
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names if expr_attr_names else None,
            ReturnValues="ALL_NEW"
        )
        
        updated_survey = simplify(response["Attributes"])
        
        logger.info(f"Updated survey {survey_id}")
        return SuccessResponse.build({"updated": updated_survey})
    
    except ClientError as e:
        logger.error(f"Update error: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    except Exception as e:
        logger.error(f"Update error: {str(e)}")
        return ErrorResponse.build(f"Update error: {str(e)}", 500)

def handle_delete_survey(survey_id):
    """Delete a survey (draft only)"""
    try:
        # Check if survey exists and is draft
        response = table.get_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": "META"
            }
        )
        
        if "Item" not in response:
            return ErrorResponse.build(f"Survey {survey_id} not found", 404)
        
        survey = response["Item"]
        
        if survey.get("Status") == "submitted":
            return ErrorResponse.build("Cannot delete submitted survey", 400)
        
        # Delete all images first
        images_response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": f"SURVEY#{survey_id}",
                ":sk": "IMAGE#"
            }
        )
        
        for image in images_response.get("Items", []):
            # Delete from S3
            try:
                image_url = image.get("ImageUrl")
                if image_url and "s3://" in image_url:
                    s3_key = image_url.split(f"s3://{S3_BUCKET}/")[1]
                    s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
            except Exception as e:
                logger.warning(f"Failed to delete S3 image: {str(e)}")
            
            # Delete from DynamoDB
            table.delete_item(
                Key={
                    "PK": image["PK"],
                    "SK": image["SK"]
                }
            )
        
        # Delete survey
        table.delete_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": "META"
            }
        )
        
        logger.info(f"Deleted survey {survey_id}")
        return SuccessResponse.build({"message": "Survey deleted successfully", "surveyId": survey_id})
    
    except ClientError as e:
        logger.error(f"Delete error: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return ErrorResponse.build(f"Delete error: {str(e)}", 500)

def handle_submit_survey(survey_id, event):
    """Submit a draft survey (makes it immutable)"""
    try:
        # Check if survey exists and is draft
        response = table.get_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": "META"
            }
        )
        
        if "Item" not in response:
            return ErrorResponse.build(f"Survey {survey_id} not found", 404)
        
        survey = response["Item"]
        
        if survey.get("Status") == "submitted":
            return ErrorResponse.build("Survey already submitted", 400)
        
        # Validate required fields for submission
        required_fields = [
            "SurveyorName", "SurveyorPhone", "SurveyDate",
            "State", "District", "Mandal", "Village"
        ]
        
        missing_fields = []
        for field in required_fields:
            if not survey.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            return ErrorResponse.build(f"Missing required fields for submission: {', '.join(missing_fields)}", 400)
        
        # Update status to submitted
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        table.update_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": "META"
            },
            UpdateExpression="SET #status = :status, SubmittedDate = :submitted, UpdatedDate = :updated",
            ExpressionAttributeNames={
                "#status": "Status"
            },
            ExpressionAttributeValues={
                ":status": "submitted",
                ":submitted": timestamp,
                ":updated": timestamp
            }
        )
        
        logger.info(f"Submitted survey {survey_id}")
        return SuccessResponse.build({
            "message": "Survey submitted successfully",
            "surveyId": survey_id,
            "submittedDate": timestamp
        })
    
    except ClientError as e:
        logger.error(f"Submit error: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    except Exception as e:
        logger.error(f"Submit error: {str(e)}")
        return ErrorResponse.build(f"Submit error: {str(e)}", 500)

def handle_upload_image(survey_id, event):
    """Generate pre-signed URL for image upload"""
    try:
        body = json.loads(event.get("body", "{}"))
    except Exception as e:
        logger.error(f"Failed to parse body: {e}")
        return ErrorResponse.build(f"Malformed JSON body: {e}", 400)
    
    # Check if survey exists
    try:
        response = table.get_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": "META"
            }
        )
        
        if "Item" not in response:
            return ErrorResponse.build(f"Survey {survey_id} not found", 404)
    
    except ClientError as e:
        logger.error(f"Database error: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    
    # Generate image ID and S3 key
    image_id = f"IMG{str(uuid.uuid4())[:8].upper()}"
    filename = body.get("filename", "image.jpg")
    content_type = body.get("contentType", "image/jpeg")
    description = body.get("description", "")
    
    # Validate file size (max 5MB)
    file_size = body.get("fileSize", 0)
    if file_size > 5 * 1024 * 1024:
        return ErrorResponse.build("File size exceeds 5MB limit", 400)
    
    # Check image count (max 10 per survey)
    try:
        images_response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": f"SURVEY#{survey_id}",
                ":sk": "IMAGE#"
            },
            Select="COUNT"
        )
        
        if images_response.get("Count", 0) >= 10:
            return ErrorResponse.build("Maximum 10 images per survey", 400)
    
    except ClientError as e:
        logger.error(f"Database error: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    
    # Generate S3 key
    s3_key = f"surveys/{survey_id}/{image_id}_{filename}"
    
    # Generate pre-signed POST URL
    try:
        presigned_post = s3_client.generate_presigned_post(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 0, 5242880]  # 5MB
            ],
            ExpiresIn=3600  # 1 hour
        )
        
        # Create image record in DynamoDB
        timestamp = datetime.utcnow().isoformat() + "Z"
        image_record = {
            "PK": f"SURVEY#{survey_id}",
            "SK": f"IMAGE#{image_id}",
            "EntityType": "SURVEY_IMAGE",
            "ImageId": image_id,
            "ImageUrl": f"s3://{S3_BUCKET}/{s3_key}",
            "Description": description,
            "UploadedDate": timestamp,
            "FileSize": file_size,
            "MimeType": content_type
        }
        
        table.put_item(Item=image_record)
        
        logger.info(f"Generated upload URL for image {image_id} in survey {survey_id}")
        
        return SuccessResponse.build({
            "imageId": image_id,
            "uploadUrl": presigned_post["url"],
            "uploadFields": presigned_post["fields"],
            "imageRecord": simplify(image_record)
        })
    
    except ClientError as e:
        logger.error(f"S3 error: {str(e)}")
        return ErrorResponse.build(f"S3 error: {e.response['Error']['Message']}", 500)
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return ErrorResponse.build(f"Upload error: {str(e)}", 500)

def handle_delete_image(survey_id, image_id):
    """Delete an image from a survey"""
    try:
        # Get image record
        response = table.get_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": f"IMAGE#{image_id}"
            }
        )
        
        if "Item" not in response:
            return ErrorResponse.build(f"Image {image_id} not found", 404)
        
        image = response["Item"]
        
        # Delete from S3
        try:
            image_url = image.get("ImageUrl")
            if image_url and "s3://" in image_url:
                s3_key = image_url.split(f"s3://{S3_BUCKET}/")[1]
                s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        except Exception as e:
            logger.warning(f"Failed to delete S3 image: {str(e)}")
        
        # Delete from DynamoDB
        table.delete_item(
            Key={
                "PK": f"SURVEY#{survey_id}",
                "SK": f"IMAGE#{image_id}"
            }
        )
        
        logger.info(f"Deleted image {image_id} from survey {survey_id}")
        return SuccessResponse.build({"message": "Image deleted successfully", "imageId": image_id})
    
    except ClientError as e:
        logger.error(f"Delete error: {str(e)}")
        return ErrorResponse.build(f"Database error: {e.response['Error']['Message']}", 500)
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return ErrorResponse.build(f"Delete error: {str(e)}", 500)

# Helper functions

def convert_floats_to_decimal(obj):
    """Recursively convert all float values to Decimal for DynamoDB"""
    if isinstance(obj, float):
        return decimal.Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(v) for v in obj]
    else:
        return obj

def simplify(item):
    """Convert DynamoDB item to JSON-serializable format"""
    def simplify_value(v):
        if isinstance(v, Decimal):
            return int(v) if v == int(v) else float(v)
        if isinstance(v, dict):
            return {k: simplify_value(nv) for k, nv in v.items()}
        if isinstance(v, list):
            return [simplify_value(x) for x in v]
        return v
    
    return {k: simplify_value(v) for k, v in item.items()}
