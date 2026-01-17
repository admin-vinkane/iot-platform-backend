#!/bin/bash
# Usage: ./scripts/rollback_lambda.sh <lambda_name> <previous_version> --env dev|prod
# Example: ./scripts/rollback_lambda.sh v_devices 20250816204228 --env dev
# Rolls back a Lambda function to a previous version from S3

set -e

# Parse arguments
LAMBDA_NAME=""
PREVIOUS_VERSION=""
ENV=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --env)
      ENV="$2"
      shift 2
      ;;
    *)
      if [ -z "$LAMBDA_NAME" ]; then
        LAMBDA_NAME="$1"
      elif [ -z "$PREVIOUS_VERSION" ]; then
        PREVIOUS_VERSION="$1"
      fi
      shift
      ;;
  esac
done

if [ -z "$LAMBDA_NAME" ] || [ -z "$PREVIOUS_VERSION" ] || [ -z "$ENV" ]; then
  echo "Usage: $0 <lambda_name> <previous_version> --env dev|prod"
  echo "Example: $0 v_devices 20250816204228 --env dev"
  exit 1
fi

# Set bucket and function name based on environment
if [ "$ENV" == "prod" ]; then
  BUCKET="my-lambda-bucket-vinkane-prod"
  FUNCTION_NAME="${LAMBDA_NAME}_prod"
else
  BUCKET="my-lambda-bucket-vinkane-dev"
  FUNCTION_NAME="${LAMBDA_NAME}_dev"
fi

S3_KEY="${LAMBDA_NAME}/${PREVIOUS_VERSION}/${LAMBDA_NAME}.zip"

# Check if the previous version exists in S3
echo "[INFO] Checking if previous version exists in S3..."
if ! aws s3 ls "s3://$BUCKET/$S3_KEY" >/dev/null 2>&1; then
  echo "[ERROR] Previous version not found in S3: s3://$BUCKET/$S3_KEY"
  echo "[INFO] Available versions:"
  aws s3 ls "s3://$BUCKET/${LAMBDA_NAME}/" --recursive | grep ".zip$" || echo "No versions found"
  exit 1
fi

echo "[INFO] Found previous version in S3: s3://$BUCKET/$S3_KEY"

# Get current Lambda configuration for backup
echo "[INFO] Backing up current Lambda configuration..."
BACKUP_FILE="/tmp/${LAMBDA_NAME}_backup_$(date +%Y%m%d%H%M%S).json"
aws lambda get-function-configuration --function-name "$FUNCTION_NAME" > "$BACKUP_FILE"
echo "[INFO] Current configuration backed up to: $BACKUP_FILE"

# Update Lambda function to previous version
echo "[INFO] Rolling back Lambda function $FUNCTION_NAME to version $PREVIOUS_VERSION..."
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --s3-bucket "$BUCKET" \
  --s3-key "$S3_KEY" \
  --output json

if [ $? -eq 0 ]; then
  echo "[SUCCESS] Lambda function $FUNCTION_NAME rolled back to version $PREVIOUS_VERSION"
  echo "[INFO] S3 location: s3://$BUCKET/$S3_KEY"
  
  # Update tfvars if needed
  TFVARS_PATH="../../iot-platform-infra/${ENV}.tfvars"
  if [ -f "$TFVARS_PATH" ]; then
    echo "[INFO] Updating $TFVARS_PATH with rollback version..."
    sed -i '' "/^${LAMBDA_NAME}_lambda_s3_key[ ]*=/d" "$TFVARS_PATH"
    echo "${LAMBDA_NAME}_lambda_s3_key = \"$S3_KEY\"" >> "$TFVARS_PATH"
    echo "[INFO] Updated $TFVARS_PATH"
  fi
  
  echo ""
  echo "[INFO] Rollback complete. Monitor CloudWatch Logs for any issues:"
  echo "       aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
else
  echo "[ERROR] Rollback failed! Check AWS Lambda console for details."
  echo "[INFO] Configuration backup available at: $BACKUP_FILE"
  exit 1
fi
