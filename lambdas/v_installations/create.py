import boto3, uuid, json
from datetime import datetime
from shared.dynamodb_utils import create_item

def lambda_handler(event, context):
    body = json.loads(event['body'])
    item = {
        'v_installation_id': str(uuid.uuid4()),
        'createdbyuser': body.get('createdbyuser', 'system'),
        'created_date': datetime.utcnow().isoformat(),
        'modifiedbyuser': body.get('createdbyuser', 'system'),
        'updated_date': datetime.utcnow().isoformat()
    }
    item.update(body)
    result = create_item("v_installations", item)
    return {
        'statusCode': 201,
        'body': json.dumps({'message': 'v_installations created', 'id': result['v_installation_id']})
    }
