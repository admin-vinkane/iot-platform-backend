# Enable CORS in API Gateway

The CORS error occurs because API Gateway needs to be configured to allow cross-origin requests from your frontend application.

## Problem
```
Access to XMLHttpRequest at 'https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices' 
from origin 'https://...webcontainer-api.io' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

## Solution

### Option 1: Enable CORS via AWS Console (Quick Fix)

1. **Open API Gateway Console**
   - Go to AWS Console → API Gateway
   - Select your API: `v_devices_api` or the API with ID `103wz10k37`

2. **Enable CORS for each resource**
   - Select the `/devices` resource
   - Click "Actions" → "Enable CORS"
   - Configure:
     - **Access-Control-Allow-Origin**: `*` (or specific domain for production)
     - **Access-Control-Allow-Headers**: `Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token`
     - **Access-Control-Allow-Methods**: `GET,POST,PUT,DELETE,OPTIONS`
   - Click "Enable CORS and replace existing CORS headers"

3. **Repeat for all resources**
   - `/devices/{deviceId}`
   - `/installs`
   - `/installs/{installId}`
   - Any other resources used by frontend

4. **Deploy the API**
   - Click "Actions" → "Deploy API
   - Select stage: `dev`
   - Click "Deploy"

### Option 2: Enable CORS via Terraform (Recommended for Production)

If your API Gateway is managed by Terraform, add CORS configuration:

```hcl
resource "aws_api_gateway_method" "options_devices" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.devices.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_devices" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.devices.id
  http_method = aws_api_gateway_method.options_devices.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_devices_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.devices.id
  http_method = aws_api_gateway_method.options_devices.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_devices_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.devices.id
  http_method = aws_api_gateway_method.options_devices.http_method
  status_code = aws_api_gateway_method_response.options_devices_200.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}
```

### Option 3: Use AWS CLI

```bash
# Enable CORS for /devices resource
aws apigateway put-method \
  --rest-api-id 103wz10k37 \
  --resource-id <RESOURCE_ID> \
  --http-method OPTIONS \
  --authorization-type NONE \
  --region ap-south-2

aws apigateway put-integration \
  --rest-api-id 103wz10k37 \
  --resource-id <RESOURCE_ID> \
  --http-method OPTIONS \
  --type MOCK \
  --request-templates '{"application/json": "{\"statusCode\": 200}"}' \
  --region ap-south-2

aws apigateway put-method-response \
  --rest-api-id 103wz10k37 \
  --resource-id <RESOURCE_ID> \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters \
    method.response.header.Access-Control-Allow-Headers=true,\
    method.response.header.Access-Control-Allow-Methods=true,\
    method.response.header.Access-Control-Allow-Origin=true \
  --region ap-south-2

aws apigateway put-integration-response \
  --rest-api-id 103wz10k37 \
  --resource-id <RESOURCE_ID> \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters \
    method.response.header.Access-Control-Allow-Headers="'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",\
    method.response.header.Access-Control-Allow-Methods="'GET,POST,PUT,DELETE,OPTIONS'",\
    method.response.header.Access-Control-Allow-Origin="'*'" \
  --region ap-south-2

# Deploy the API
aws apigateway create-deployment \
  --rest-api-id 103wz10k37 \
  --stage-name dev \
  --region ap-south-2
```

## What I've Already Done

✅ Updated Lambda response utility (`shared/response_utils.py`) to include CORS headers in all responses:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Headers: Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token`
- `Access-Control-Allow-Methods: GET,POST,PUT,DELETE,OPTIONS`

✅ Lambda already handles OPTIONS requests for CORS preflight

✅ Deployed Lambda version 20260210150109

## What Still Needs to Be Done

⚠️ **API Gateway Configuration** - CORS must be enabled at the API Gateway level for the headers to be passed through to the browser.

## Testing After Configuration

```bash
# Test OPTIONS preflight request
curl -i -X OPTIONS "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/devices" \
  -H "Origin: https://your-frontend-domain.com"

# Should return headers like:
# Access-Control-Allow-Origin: *
# Access-Control-Allow-Methods: GET,POST,PUT,DELETE,OPTIONS
# Access-Control-Allow-Headers: Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token
```

## For Production

Replace `*` with your specific frontend domain:
```
Access-Control-Allow-Origin: https://your-production-domain.com
```
