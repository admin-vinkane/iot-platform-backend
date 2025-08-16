#!/bin/bash
# Usage: ./scripts/package_and_upload_all_lambdas.sh [--upload]
# Packages all lambdas in lambdas/ to dist/<lambda>.zip
# If --upload is provided, uploads to S3 as well


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

for LAMBDA in "$LAMBDA_ROOT"/*; do
  if [ -d "$LAMBDA" ]; then
    NAME=$(basename "$LAMBDA")
    "$SCRIPT_DIR/package_lambda.sh" "$LAMBDA" "$DIST_DIR/${NAME}.zip"
    if [ "$UPLOAD" = true ]; then
  echo "Uploading $DIST_DIR/${NAME}.zip to s3://$BUCKET/${NAME}/$VERSION/${NAME}.zip"
  aws s3 cp "$DIST_DIR/${NAME}.zip" "s3://$BUCKET/${NAME}/$VERSION/${NAME}.zip"
    fi
  fi
done

if [ "$UPLOAD" = true ]; then
  echo "All Lambdas packaged and uploaded to S3. Version: $VERSION"
else
  echo "All Lambdas packaged in $DIST_DIR/"
fi
