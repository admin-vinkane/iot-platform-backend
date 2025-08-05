import json
from shared.dynamodb_utils import read_item

def lambda_handler(event, context):
    item_id = event["pathParameters"]["id"]
    item = read_item("v_states", "id", item_id)
    return {
        'statusCode': 200,
        'body': json.dumps(item)
    }
