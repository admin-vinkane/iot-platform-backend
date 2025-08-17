#!/bin/bash
# Usage: ./update_tfvars.sh <v_devices_s3_key> <v_regions_s3_key>
# Example: ./update_tfvars.sh "v_devices/20250817124427/v_devices.zip" "v_regions/20250817124427/v_regions.zip"

TFVARS_PATH="../../iot-platform-infra/dev.tfvars"

if [ ! -f "$TFVARS_PATH" ]; then
  echo "[ERROR] $TFVARS_PATH not found!"
  exit 1
fi

# Remove old keys if present
sed -i '' "/^v_devices_lambda_s3_key[ ]*=/d" "$TFVARS_PATH"
sed -i '' "/^v_regions_lambda_s3_key[ ]*=/d" "$TFVARS_PATH"

# Append new keys
echo "v_devices_lambda_s3_key = \"$1\"" >> "$TFVARS_PATH"
echo "v_regions_lambda_s3_key = \"$2\"" >> "$TFVARS_PATH"

echo "[INFO] Updated $TFVARS_PATH with new Lambda S3 keys."
