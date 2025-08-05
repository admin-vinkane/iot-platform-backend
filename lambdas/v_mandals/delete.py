import json
from shared.dynamodb_utils import delete_item

def lambda_handler(event, context):
    item_id = event["pathParameters"]["id"]
    delete_item("v_mandals", "id", item_id)
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'v_mandals deleted'})
    }
