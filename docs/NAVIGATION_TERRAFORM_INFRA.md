# Navigation API - Infrastructure Requirements

## DynamoDB Table Specification

### Table Name
- **Dev**: `v_navigation_dev`
- **Staging**: `v_navigation_staging`
- **Prod**: `v_navigation_prod`

### Table Configuration

```hcl
# Terraform Configuration

resource "aws_dynamodb_table" "v_navigation" {
  name           = "v_navigation_${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "PK"
  range_key      = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "entityType"
    type = "S"
  }

  attribute {
    name = "parentId"
    type = "S"
  }

  # GSI for querying by entity type
  global_secondary_index {
    name            = "GSI1-EntityType"
    hash_key        = "entityType"
    range_key       = "SK"
    projection_type = "ALL"
  }

  # GSI for querying items by parent group
  global_secondary_index {
    name            = "GSI2-ParentId"
    hash_key        = "parentId"
    range_key       = "order"
    projection_type = "ALL"
  }

  tags = {
    Name        = "v_navigation_${var.environment}"
    Environment = var.environment
    Service     = "navigation-management"
    ManagedBy   = "terraform"
  }

  point_in_time_recovery {
    enabled = var.environment == "prod" ? true : false
  }

  server_side_encryption {
    enabled = true
  }
}
```

### Key Schema

| Attribute | Type | Description |
|-----------|------|-------------|
| **PK** | String (HASH) | Partition Key - Format: `GROUP#{id}`, `ITEM#{id}`, `HISTORY#{id}` |
| **SK** | String (RANGE) | Sort Key - Format: `METADATA#{id}`, `TIMESTAMP#{iso8601}` |
| entityType | String | Entity discriminator: `NAVIGATION_GROUP`, `NAVIGATION_ITEM`, `NAVIGATION_HISTORY` |
| parentId | String | For items: references parent group ID |

### Sample Data Patterns

#### Navigation Group
```json
{
  "PK": "GROUP#GROUP_20260210120000_abc12345",
  "SK": "METADATA#GROUP_20260210120000_abc12345",
  "id": "GROUP_20260210120000_abc12345",
  "entityType": "NAVIGATION_GROUP",
  "label": "Administration",
  "icon": "Shield",
  "isActive": true,
  "order": 1,
  "isCollapsible": true,
  "defaultExpanded": false,
  "createdAt": "2026-02-10T12:00:00.000Z",
  "updatedAt": "2026-02-10T12:00:00.000Z",
  "createdBy": "admin@example.com",
  "updatedBy": "admin@example.com"
}
```

#### Navigation Item
```json
{
  "PK": "ITEM#ITEM_20260210120100_xyz67890",
  "SK": "METADATA#ITEM_20260210120100_xyz67890",
  "id": "ITEM_20260210120100_xyz67890",
  "entityType": "NAVIGATION_ITEM",
  "parentId": "GROUP_20260210120000_abc12345",
  "label": "Menu Management",
  "icon": "Grid",
  "path": "/menu-management",
  "permission": "can_manage_navigation",
  "isActive": true,
  "order": 1,
  "children": [],
  "createdAt": "2026-02-10T12:01:00.000Z",
  "updatedAt": "2026-02-10T12:01:00.000Z",
  "createdBy": "admin@example.com",
  "updatedBy": "admin@example.com"
}
```

#### History Record
```json
{
  "PK": "HISTORY#HIST_20260210120200_def45678",
  "SK": "TIMESTAMP#2026-02-10T12:02:00.000Z",
  "id": "HIST_20260210120200_def45678",
  "entityType": "NAVIGATION_HISTORY",
  "changeEntityType": "group",
  "entityId": "GROUP_20260210120000_abc12345",
  "changeType": "created",
  "fieldName": "label",
  "oldValue": "",
  "newValue": "Administration",
  "description": "Created navigation group 'Administration'",
  "changedBy": "admin@example.com",
  "changedAt": "2026-02-10T12:02:00.000Z",
  "ipAddress": "192.168.1.100"
}
```

---

## API Gateway Routes Configuration

### Lambda Function

```hcl
resource "aws_lambda_function" "v_navigation" {
  function_name = "v_navigation_${var.environment}"
  handler       = "v_navigation_api.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.v_navigation_lambda_role.arn
  timeout       = 30
  memory_size   = 512

  filename         = "lambda_packages/v_navigation.zip"
  source_code_hash = filebase64sha256("lambda_packages/v_navigation.zip")

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.v_navigation.name
      DEV_MODE   = var.environment == "dev" ? "true" : "false"
    }
  }

  layers = [
    aws_lambda_layer_version.shared_utils.arn
  ]

  tags = {
    Name        = "v_navigation_${var.environment}"
    Environment = var.environment
    Service     = "navigation-management"
  }
}
```

### API Gateway HTTP API Routes

```hcl
# Integration
resource "aws_apigatewayv2_integration" "v_navigation" {
  api_id             = aws_apigatewayv2_api.main.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.v_navigation.invoke_arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

# Route 1: GET /navigation/groups
resource "aws_apigatewayv2_route" "navigation_groups_get" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /navigation/groups"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 2: POST /navigation/groups
resource "aws_apigatewayv2_route" "navigation_groups_post" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /navigation/groups"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 3: PATCH /navigation/groups/{groupId}
resource "aws_apigatewayv2_route" "navigation_groups_patch" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "PATCH /navigation/groups/{groupId}"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 4: DELETE /navigation/groups/{groupId}
resource "aws_apigatewayv2_route" "navigation_groups_delete" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "DELETE /navigation/groups/{groupId}"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 5: POST /navigation/groups/reorder
resource "aws_apigatewayv2_route" "navigation_groups_reorder" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /navigation/groups/reorder"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 6: POST /navigation/groups/{groupId}/items
resource "aws_apigatewayv2_route" "navigation_items_post" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /navigation/groups/{groupId}/items"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 7: PATCH /navigation/groups/{groupId}/items/{itemId}
resource "aws_apigatewayv2_route" "navigation_items_patch" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "PATCH /navigation/groups/{groupId}/items/{itemId}"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 8: DELETE /navigation/groups/{groupId}/items/{itemId}
resource "aws_apigatewayv2_route" "navigation_items_delete" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "DELETE /navigation/groups/{groupId}/items/{itemId}"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 9: POST /navigation/groups/{groupId}/items/reorder
resource "aws_apigatewayv2_route" "navigation_items_reorder" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /navigation/groups/{groupId}/items/reorder"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 10: POST /navigation/items/move
resource "aws_apigatewayv2_route" "navigation_items_move" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /navigation/items/move"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Route 11: GET /navigation/history
resource "aws_apigatewayv2_route" "navigation_history_get" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /navigation/history"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# OPTIONS routes for CORS (if not using automatic CORS)
resource "aws_apigatewayv2_route" "navigation_groups_options" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "OPTIONS /navigation/groups"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

resource "aws_apigatewayv2_route" "navigation_groups_id_options" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "OPTIONS /navigation/groups/{groupId}"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

resource "aws_apigatewayv2_route" "navigation_items_options" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "OPTIONS /navigation/groups/{groupId}/items"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

resource "aws_apigatewayv2_route" "navigation_items_id_options" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "OPTIONS /navigation/groups/{groupId}/items/{itemId}"
  target    = "integrations/${aws_apigatewayv2_integration.v_navigation.id}"
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "v_navigation_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.v_navigation.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
```

---

## IAM Role and Policies

```hcl
# Lambda Execution Role
resource "aws_iam_role" "v_navigation_lambda_role" {
  name = "v_navigation_lambda_role_${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "v_navigation_lambda_role_${var.environment}"
    Environment = var.environment
  }
}

# CloudWatch Logs Policy
resource "aws_iam_role_policy_attachment" "v_navigation_lambda_logs" {
  role       = aws_iam_role.v_navigation_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB Access Policy
resource "aws_iam_role_policy" "v_navigation_dynamodb_policy" {
  name = "v_navigation_dynamodb_policy_${var.environment}"
  role = aws_iam_role.v_navigation_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.v_navigation.arn,
          "${aws_dynamodb_table.v_navigation.arn}/index/*"
        ]
      }
    ]
  })
}
```

---

## CORS Configuration

```hcl
resource "aws_apigatewayv2_api" "main" {
  name          = "iot-platform-api-${var.environment}"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = var.environment == "prod" ? [
      "https://app.yourdomain.com"
    ] : ["*"]
    
    allow_methods = [
      "GET",
      "POST",
      "PUT",
      "PATCH",
      "DELETE",
      "OPTIONS"
    ]
    
    allow_headers = [
      "Content-Type",
      "Authorization",
      "X-Amz-Date",
      "X-Api-Key",
      "X-Amz-Security-Token"
    ]
    
    expose_headers = [
      "Content-Length",
      "Content-Type"
    ]
    
    max_age = 300
  }
}
```

---

## Environment Variables

### Lambda Configuration

| Variable | Dev | Staging | Prod | Description |
|----------|-----|---------|------|-------------|
| `TABLE_NAME` | `v_navigation_dev` | `v_navigation_staging` | `v_navigation_prod` | DynamoDB table name |
| `DEV_MODE` | `true` | `false` | `false` | Bypass authentication in dev |

---

## Route Summary Table

| # | Method | Path | Description | Path Parameters |
|---|--------|------|-------------|-----------------|
| 1 | GET | `/navigation/groups` | List all groups with items | - |
| 2 | POST | `/navigation/groups` | Create navigation group | - |
| 3 | PATCH | `/navigation/groups/{groupId}` | Update navigation group | `groupId` |
| 4 | DELETE | `/navigation/groups/{groupId}` | Delete group and items | `groupId` |
| 5 | POST | `/navigation/groups/reorder` | Reorder groups | - |
| 6 | POST | `/navigation/groups/{groupId}/items` | Create navigation item | `groupId` |
| 7 | PATCH | `/navigation/groups/{groupId}/items/{itemId}` | Update navigation item | `groupId`, `itemId` |
| 8 | DELETE | `/navigation/groups/{groupId}/items/{itemId}` | Delete navigation item | `groupId`, `itemId` |
| 9 | POST | `/navigation/groups/{groupId}/items/reorder` | Reorder items in group | `groupId` |
| 10 | POST | `/navigation/items/move` | Move item between groups | - |
| 11 | GET | `/navigation/history` | Fetch audit trail | - |

---

## CloudWatch Alarms (Optional)

```hcl
resource "aws_cloudwatch_metric_alarm" "v_navigation_errors" {
  alarm_name          = "v_navigation_errors_${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors navigation Lambda errors"
  
  dimensions = {
    FunctionName = aws_lambda_function.v_navigation.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "v_navigation_duration" {
  alarm_name          = "v_navigation_duration_${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Average"
  threshold           = "5000"
  alarm_description   = "This metric monitors navigation Lambda duration"
  
  dimensions = {
    FunctionName = aws_lambda_function.v_navigation.function_name
  }
}
```

---

## Deployment Checklist

- [ ] Create DynamoDB table with GSIs
- [ ] Deploy Lambda function
- [ ] Configure API Gateway routes (11 main + 4 OPTIONS)
- [ ] Set up IAM role and policies
- [ ] Configure CORS
- [ ] Set environment variables
- [ ] Add CloudWatch alarms
- [ ] Test all endpoints
- [ ] Enable API Gateway logging
- [ ] Configure rate limiting (if needed)

---

## Estimated Costs (AWS Pricing)

### DynamoDB (PAY_PER_REQUEST)
- Read: $0.25 per million requests
- Write: $1.25 per million requests
- Storage: $0.25 per GB/month

### Lambda
- Requests: $0.20 per million requests
- Duration: $0.0000166667 per GB-second (512MB = ~$0.0000083)

### API Gateway (HTTP API)
- $1.00 per million requests

**Estimated Monthly (Low Traffic):**
- 100K requests/month ≈ $0.20 - $0.50
