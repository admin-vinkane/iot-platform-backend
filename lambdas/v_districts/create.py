import boto3, uuid, json
from datetime import datetime
from shared.dynamodb_utils import create_item

def lambda_handler(event, context):
    body = json.loads(event['body'])
    item = {
        'v_district_id': str(uuid.uuid4()),
        'createdbyuser': body.get('createdbyuser', 'system'),
        'created_date': datetime.utcnow().isoformat(),
        'modifiedbyuser': body.get('createdbyuser', 'system'),
        'updated_date': datetime.utcnow().isoformat()
    }
    item.update(body)
    result = create_item("v_districts", item)
    return {
        'statusCode': 201,
        'body': json.dumps({'message': 'v_districts created', 'id': result['v_district_id']})
    }
