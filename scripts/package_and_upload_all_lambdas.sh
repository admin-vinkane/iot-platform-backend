#!/bin/bash
# Usage: ./scripts/package_and_upload_all_lambdas.sh [--upload]
# Packages all lambdas in lambdas/ to dist/<lambda>.zip
# If --upload is provided, uploads to S3 as well

# Usage
# 1. Package All Lambdas - ./scripts/package_and_upload_all_lambdas.sh
# Packages all Lambda functions into .zip files in the dist directory.
# 2. Package and Upload to S3 - ./scripts/package_and_upload_all_lambdas.sh --upload
# Packages all Lambda functions and uploads them to the my-lambda-bucket-vinkane-dev S3 bucket.
# 3. Specify a Custom Bucket - ./scripts/package_and_upload_all_lambdas.sh --upload --bucket my-custom-bucket
# Packages and uploads Lambda functions to the specified S3 bucket.
# Conclusion
# The package_and_upload_all_lambdas.sh script automates the process of packaging, uploading, and managing Lambda functions.
# It ensures compatibility with AWS Lambda's environment, dynamically determines the S3 bucket based on the environment,
# and updates Terraform .tfvars files for seamless deployment. This script is a critical part of the CI/CD pipeline for
# managing Lambda functions in the project.

set -e

# Set VERSION to current timestamp (YYYYmmddHHMMSS)
VERSION=$(date +%Y%m%d%H%M%S)



# If not running inside Docker, re-invoke this script inside the official AWS Lambda Python 3.12 Docker image for Linux compatibility,
# and ensure AWS CLI and credentials are available inside the container.
if [ -z "$IN_LAMBDA_DOCKER" ]; then
  echo "[INFO] Re-invoking inside Docker for Linux compatibility with AWS CLI and credentials..."
  SCRIPT_DIR="$(dirname "$0")"
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  AWS_DIR="$HOME/.aws"
  docker run --platform linux/amd64 --rm \
    -v "$PROJECT_ROOT":/var/task \
    -v "$AWS_DIR":/root/.aws \
    -w /var/task \
    --entrypoint /bin/bash \
    -e IN_LAMBDA_DOCKER=1 \
    public.ecr.aws/lambda/python:3.12 \
  -c "pip install awscli && ./scripts/package_and_upload_all_lambdas.sh $@"
  exit $?
fi

# Check for required CLI tools (inside Docker)
if ! command -v aws >/dev/null 2>&1; then
  echo "Error: aws CLI is not installed. Please install AWS CLI and configure credentials (or mount ~/.aws into Docker)." >&2
  exit 1
fi


LAMBDA_ROOT="lambdas"
DIST_DIR="dist"
SCRIPT_DIR="$(dirname "$0")"
UPLOAD=false
BUCKET="my-lambda-bucket"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --upload)
      UPLOAD=true
      shift
      ;;
    --bucket)
      BUCKET="$2"
      shift 2
      ;;
    --env)
      ENV="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done



# Default bucket based on environment if not set
if [ "$BUCKET" = "my-lambda-bucket" ]; then
  if [ "$ENV" == "prod" ]; then
    BUCKET="my-lambda-bucket-vinkane-prod"
  else
    BUCKET="my-lambda-bucket-vinkane-dev"
  fi
fi

mkdir -p "$DIST_DIR"


# Track S3 keys for tfvars output
TFVARS_SNIPPET=""

for LAMBDA in "$LAMBDA_ROOT"/*; do
  if [ -d "$LAMBDA" ]; then
    NAME=$(basename "$LAMBDA")
    "$SCRIPT_DIR/package_lambda.sh" "$LAMBDA" "$DIST_DIR/${NAME}.zip"
    S3_KEY="${NAME}/$VERSION/${NAME}.zip"
    if [ "$UPLOAD" = true ]; then
      echo "Uploading $DIST_DIR/${NAME}.zip to s3://$BUCKET/$S3_KEY"
      aws s3 cp "$DIST_DIR/${NAME}.zip" "s3://$BUCKET/$S3_KEY"
      echo "[INFO] S3 key for $NAME: $S3_KEY"
      # Append tfvars snippet
      TFVARS_SNIPPET+="${NAME}_lambda_s3_key = \"$S3_KEY\"\n"
    fi
  fi
done


# Write tfvars snippet and update dev.tfvars
if [ "$UPLOAD" = true ] && [ -n "$TFVARS_SNIPPET" ]; then
  echo -e "\n[INFO] Terraform .tfvars snippet for Lambda S3 keys:"
  echo -e "$TFVARS_SNIPPET"


  # Path to tfvars files
  DEV_TFVARS="../../iot-platform-infra/dev.tfvars"
  PROD_TFVARS="../../iot-platform-infra/prod.tfvars"
  # Choose which tfvars to update based on --env
  if [ "$ENV" == "prod" ]; then
    TARGET_TFVARS="$PROD_TFVARS"
  else
    TARGET_TFVARS="$DEV_TFVARS"
  fi
  if [ -f "$TARGET_TFVARS" ]; then
    grep -v '_lambda_s3_key[ ]*=' "$TARGET_TFVARS" > "$TARGET_TFVARS.tmp" || true
    echo -e "$TFVARS_SNIPPET" >> "$TARGET_TFVARS.tmp"
    mv "$TARGET_TFVARS.tmp" "$TARGET_TFVARS"
    echo "[INFO] Updated $TARGET_TFVARS with latest Lambda S3 keys."
  else
    echo "[WARN] $TARGET_TFVARS not found. Please update your tfvars file manually."
  fi
fi

if [ "$UPLOAD" = true ]; then
  echo "All Lambdas packaged and uploaded to S3. Version: $VERSION"
else
  echo "All Lambdas packaged in $DIST_DIR/"
fi
