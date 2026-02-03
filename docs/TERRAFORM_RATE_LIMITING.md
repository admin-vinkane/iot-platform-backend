# Terraform Configuration for API Gateway Rate Limiting

**Location**: `iot-platform-infra` repository  
**Priority**: CRITICAL ⚠️  
**Estimated Time**: 30 minutes

---

## Overview

Add rate limiting to API Gateway to prevent DDoS attacks and control costs. Configuration should be added to your Terraform infrastructure repository.

---

## Option 1: Account-Level Throttling (Simplest)

Add this to your API Gateway stage configuration:

```hcl
# In your api_gateway.tf or similar file

resource "aws_api_gateway_stage" "dev" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "dev"

  # Account-level throttling settings
  throttle_settings {
    burst_limit = 2000  # Maximum concurrent requests
    rate_limit  = 1000  # Steady-state requests per second
  }

  tags = {
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

**Applies to**: All endpoints in the stage  
**Cost**: Free  
**Behavior**: 
- Allows burst of 2000 requests
- Steady rate of 1000 requests/second
- Returns 429 "Too Many Requests" when exceeded

---

## Option 2: Method-Level Throttling (Recommended)

For finer control, set limits per endpoint:

```hcl
# In your api_gateway.tf

resource "aws_api_gateway_stage" "dev" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "dev"

  # Default throttling for all methods
  throttle_settings {
    burst_limit = 2000
    rate_limit  = 1000
  }

  tags = {
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}

# Method-specific throttling
resource "aws_api_gateway_method_settings" "devices" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.dev.stage_name
  method_path = "*/*"  # Applies to all methods

  settings {
    # Logging
    logging_level          = "INFO"
    data_trace_enabled     = true
    metrics_enabled        = true
    
    # Throttling
    throttling_burst_limit = 2000
    throttling_rate_limit  = 1000
    
    # Caching (optional)
    caching_enabled        = false
  }
}

# Stricter limits for write operations
resource "aws_api_gateway_method_settings" "installs_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.dev.stage_name
  method_path = "installs/POST"  # Specific endpoint

  settings {
    throttling_burst_limit = 100   # Lower limit for create operations
    throttling_rate_limit  = 50    # 50 installations per second max
    logging_level          = "INFO"
    metrics_enabled        = true
  }
}

# Stricter limits for expensive operations
resource "aws_api_gateway_method_settings" "installs_get" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.dev.stage_name
  method_path = "installs/GET"  # List endpoint

  settings {
    throttling_burst_limit = 200   # Moderate limit for reads
    throttling_rate_limit  = 100   # 100 list requests per second
    logging_level          = "INFO"
    metrics_enabled        = true
  }
}
```

---

## Option 3: Usage Plans & API Keys (Enterprise)

For per-client rate limiting:

```hcl
# Create usage plan
resource "aws_api_gateway_usage_plan" "standard" {
  name        = "standard-plan"
  description = "Standard usage plan for API consumers"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.dev.stage_name
  }

  quota_settings {
    limit  = 100000   # 100K requests per period
    period = "MONTH"  # Monthly quota
  }

  throttle_settings {
    burst_limit = 500   # Per-client burst
    rate_limit  = 200   # Per-client rate
  }
}

# Create usage plan for premium clients
resource "aws_api_gateway_usage_plan" "premium" {
  name        = "premium-plan"
  description = "Premium usage plan with higher limits"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.dev.stage_name
  }

  quota_settings {
    limit  = 1000000  # 1M requests per month
    period = "MONTH"
  }

  throttle_settings {
    burst_limit = 2000
    rate_limit  = 1000
  }
}

# Create API key for a client
resource "aws_api_gateway_api_key" "client_abc" {
  name    = "client-abc-key"
  enabled = true
  
  tags = {
    Client = "ABC Corp"
  }
}

# Associate API key with usage plan
resource "aws_api_gateway_usage_plan_key" "client_abc" {
  key_id        = aws_api_gateway_api_key.client_abc.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.standard.id
}
```

---

## Recommended Configuration

Based on your current API requirements:

```hcl
# api_gateway_throttling.tf

# Stage-level default throttling
resource "aws_api_gateway_stage" "dev" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "dev"

  throttle_settings {
    burst_limit = 2000  # Handle traffic spikes
    rate_limit  = 1000  # Steady-state limit
  }

  # Enable detailed CloudWatch metrics
  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "iot-platform-backend"
  }
}

# CloudWatch Log Group for API Gateway logs
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.environment}-iot-platform"
  retention_in_days = 30

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Method settings with specific limits
resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.dev.stage_name
  method_path = "*/*"

  settings {
    # Logging
    logging_level          = "INFO"
    data_trace_enabled     = false  # Set to true for debugging
    metrics_enabled        = true
    
    # Default throttling (inherits from stage if not specified)
    throttling_burst_limit = 2000
    throttling_rate_limit  = 1000
    
    # Caching
    caching_enabled        = false
  }
}

# Stricter limits for write operations
resource "aws_api_gateway_method_settings" "installs_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.dev.stage_name
  method_path = "installs/POST"

  settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
    logging_level          = "INFO"
    metrics_enabled        = true
  }
}

resource "aws_api_gateway_method_settings" "devices_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.dev.stage_name
  method_path = "devices/POST"

  settings {
    throttling_burst_limit = 200
    throttling_rate_limit  = 100
    logging_level          = "INFO"
    metrics_enabled        = true
  }
}

# Moderate limits for list operations (expensive due to scans)
resource "aws_api_gateway_method_settings" "installs_get" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.dev.stage_name
  method_path = "installs/GET"

  settings {
    throttling_burst_limit = 200
    throttling_rate_limit  = 100
    logging_level          = "INFO"
    metrics_enabled        = true
  }
}

resource "aws_api_gateway_method_settings" "devices_get" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.dev.stage_name
  method_path = "devices/GET"

  settings {
    throttling_burst_limit = 200
    throttling_rate_limit  = 100
    logging_level          = "INFO"
    metrics_enabled        = true
  }
}
```

---

## Variables Configuration

Add these to your `variables.tf`:

```hcl
variable "api_throttle_burst_limit" {
  description = "Maximum concurrent requests API Gateway can handle"
  type        = number
  default     = 2000
}

variable "api_throttle_rate_limit" {
  description = "Steady-state requests per second"
  type        = number
  default     = 1000
}

variable "api_throttle_installs_post_burst" {
  description = "Burst limit for POST /installs"
  type        = number
  default     = 100
}

variable "api_throttle_installs_post_rate" {
  description = "Rate limit for POST /installs"
  type        = number
  default     = 50
}
```

Add these to your `dev.tfvars`:

```hcl
# API Gateway Throttling
api_throttle_burst_limit             = 2000
api_throttle_rate_limit              = 1000
api_throttle_installs_post_burst     = 100
api_throttle_installs_post_rate      = 50
```

---

## CloudWatch Alarms

Add alarms to monitor throttling:

```hcl
# cloudwatch_alarms.tf

resource "aws_cloudwatch_metric_alarm" "api_gateway_4xx_errors" {
  alarm_name          = "${var.environment}-api-gateway-4xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"  # 5 minutes
  statistic           = "Sum"
  threshold           = "100"
  alarm_description   = "This metric monitors API Gateway 4xx errors (includes 429 throttling)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.main.name
    Stage   = aws_api_gateway_stage.dev.stage_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_throttled_requests" {
  alarm_name          = "${var.environment}-api-gateway-throttled"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Count"
  namespace           = "AWS/ApiGateway"
  period              = "60"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Alert when requests are being throttled"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.main.name
    Stage   = aws_api_gateway_stage.dev.stage_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_latency" {
  alarm_name          = "${var.environment}-api-gateway-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Average"
  threshold           = "1000"  # 1 second
  alarm_description   = "Alert when API latency exceeds 1 second"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.main.name
    Stage   = aws_api_gateway_stage.dev.stage_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# SNS topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.environment}-iot-platform-alerts"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
```

---

## Deployment Steps

### 1. Update Terraform Configuration

In your `iot-platform-infra` repository:

```bash
cd iot-platform-infra

# Create new branch
git checkout -b feature/api-gateway-rate-limiting

# Add the throttling configuration to your API Gateway Terraform files
# (Use the recommended configuration above)

# Commit changes
git add .
git commit -m "Add API Gateway rate limiting and monitoring"
git push origin feature/api-gateway-rate-limiting
```

### 2. Review Changes

```bash
# Initialize Terraform (if needed)
terraform init

# Review what will change
terraform plan -var-file=dev.tfvars

# Expected output:
# + aws_api_gateway_stage.dev (throttle_settings added)
# + aws_api_gateway_method_settings.all
# + aws_api_gateway_method_settings.installs_post
# + aws_cloudwatch_metric_alarm.api_gateway_4xx_errors
# etc.
```

### 3. Apply Changes

```bash
# Apply to dev environment
terraform apply -var-file=dev.tfvars

# Review output and confirm with "yes"
```

### 4. Test Rate Limiting

```bash
# Test normal operation
curl -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs?limit=10"

# Test rate limiting with load test
for i in {1..2500}; do
  curl -s -X GET "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs" &
done

# Should see 429 responses after burst limit exceeded
```

### 5. Monitor in CloudWatch

```bash
# View metrics in AWS Console
# CloudWatch > Metrics > AWS/ApiGateway
# Look for:
# - Count (total requests)
# - 4XXError (includes 429 throttling)
# - Latency
# - CacheHitCount / CacheMissCount
```

---

## Testing Configuration

### Test Script

Save as `test_rate_limiting.sh`:

```bash
#!/bin/bash

API_URL="https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/installs"
REQUESTS_PER_SECOND=100
TOTAL_SECONDS=15

echo "Testing rate limiting: $REQUESTS_PER_SECOND req/sec for $TOTAL_SECONDS seconds"
echo "Total requests: $((REQUESTS_PER_SECOND * TOTAL_SECONDS))"

success_count=0
throttled_count=0
error_count=0

for ((i=1; i<=$TOTAL_SECONDS; i++)); do
  echo "Second $i..."
  for ((j=1; j<=$REQUESTS_PER_SECOND; j++)); do
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL?limit=1")
    
    if [ "$response" = "200" ]; then
      ((success_count++))
    elif [ "$response" = "429" ]; then
      ((throttled_count++))
    else
      ((error_count++))
    fi
  done
  sleep 1
done

echo ""
echo "Results:"
echo "  Success (200): $success_count"
echo "  Throttled (429): $throttled_count"
echo "  Errors (other): $error_count"
echo ""
echo "Throttle rate: $(echo "scale=2; $throttled_count * 100 / ($success_count + $throttled_count + $error_count)" | bc)%"
```

---

## Cost Considerations

**API Gateway Throttling**: FREE ✅
- No additional cost for throttling
- Built-in feature of API Gateway

**CloudWatch Logs**: ~$0.50/GB ingested
- Estimate: 1GB/month with INFO logging
- Cost: ~$0.50/month

**CloudWatch Alarms**: $0.10/alarm/month
- 3 alarms = $0.30/month

**Total Additional Cost**: ~$0.80/month

---

## Troubleshooting

### Issue: All Requests Getting Throttled

**Cause**: Limits set too low

**Solution**: Increase limits in `dev.tfvars`:
```hcl
api_throttle_rate_limit = 2000  # Increase from 1000
```

### Issue: No Throttling Happening

**Cause**: Configuration not applied to correct stage

**Solution**: Verify stage name matches:
```bash
terraform state show aws_api_gateway_stage.dev
```

### Issue: 429 Errors But No Alarms

**Cause**: Alarm threshold too high

**Solution**: Lower threshold in alarm:
```hcl
threshold = "10"  # Alert on 10+ throttled requests
```

---

## Environment-Specific Configuration

### Dev Environment
```hcl
# dev.tfvars
api_throttle_burst_limit = 500
api_throttle_rate_limit  = 200
```

### Staging Environment
```hcl
# staging.tfvars
api_throttle_burst_limit = 1000
api_throttle_rate_limit  = 500
```

### Production Environment
```hcl
# prod.tfvars
api_throttle_burst_limit = 5000
api_throttle_rate_limit  = 2000
```

---

## Monitoring Dashboard

Create CloudWatch dashboard to visualize throttling:

```hcl
resource "aws_cloudwatch_dashboard" "api_gateway" {
  dashboard_name = "${var.environment}-iot-platform-api"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", { stat = "Sum", label = "Total Requests" }],
            [".", "4XXError", { stat = "Sum", label = "4XX Errors" }],
            [".", "5XXError", { stat = "Sum", label = "5XX Errors" }]
          ]
          period = 300
          region = var.aws_region
          title  = "API Gateway Requests"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Latency", { stat = "Average", label = "Avg Latency" }],
            ["...", { stat = "p99", label = "P99 Latency" }]
          ]
          period = 300
          region = var.aws_region
          title  = "API Gateway Latency"
        }
      }
    ]
  })
}
```

---

## Next Steps After Rate Limiting

1. **Monitor for 1 week**: Check CloudWatch metrics
2. **Adjust limits**: Based on actual traffic patterns
3. **Add API keys**: For per-client throttling (Phase 3)
4. **Implement caching**: Add CloudFront or API Gateway cache
5. **Create DynamoDB GSI**: To improve list endpoint performance

---

## Summary

✅ **DO**: Configure rate limiting via Terraform  
❌ **DON'T**: Configure manually via AWS Console  

**Recommended Limits**:
- Default: 1000 req/sec, burst 2000
- POST /installs: 50 req/sec, burst 100
- GET /installs: 100 req/sec, burst 200

**Estimated Time**: 30 minutes  
**Cost**: ~$0.80/month  
**Priority**: CRITICAL ⚠️

---

**Next Review**: After 1 week of monitoring
