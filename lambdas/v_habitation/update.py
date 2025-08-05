import json
from datetime import datetime
from shared.dynamodb_utils import update_item

def lambda_handler(event, context):
    item_id = event["pathParameters"]["id"]
    body = json.loads(event['body'])
    body["updated_date"] = datetime.utcnow().isoformat()
    result = update_item("v_habitation", "id", item_id, body)
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'v_habitation updated'})
    }
