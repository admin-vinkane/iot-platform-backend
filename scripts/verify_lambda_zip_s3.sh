#!/bin/bash
# Usage: ./scripts/verify_lambda_zip_s3.sh <local_zip> <s3_bucket> <s3_key>
# Compares a local Lambda zip with the one deployed to S3 (structure and content)

set -e

LOCAL_ZIP="$1"
S3_BUCKET="$2"
S3_KEY="$3"

if [ -z "$LOCAL_ZIP" ] || [ -z "$S3_BUCKET" ] || [ -z "$S3_KEY" ]; then
  echo "Usage: $0 <local_zip> <s3_bucket> <s3_key>"
  exit 1
fi

TMP_DIR=$(mktemp -d)
S3_ZIP="$TMP_DIR/s3_lambda.zip"

# Download the S3 zip
aws s3 cp "s3://$S3_BUCKET/$S3_KEY" "$S3_ZIP"

# Compare file lists
echo "[INFO] Comparing file lists in local and S3 zips..."
diff <(unzip -l "$LOCAL_ZIP" | awk '{print $4}' | sort) <(unzip -l "$S3_ZIP" | awk '{print $4}' | sort) || {
  echo "[ERROR] File lists differ!" >&2
  exit 2
}

# Compare file contents (optional, can be slow for large zips)
echo "[INFO] Comparing file contents in local and S3 zips..."
diff <(unzip -p "$LOCAL_ZIP" | sha256sum) <(unzip -p "$S3_ZIP" | sha256sum) || {
  echo "[ERROR] File contents differ!" >&2
  exit 3
}

echo "[SUCCESS] Local and S3 Lambda zips are identical."
rm -rf "$TMP_DIR"
