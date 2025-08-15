#!/bin/bash
set -e
BUCKET="my-lambda-bucket"
ROOT_DIR=$(pwd)
if [ -d .git ]; then
  VERSION=$(git rev-parse --short HEAD)
else
  VERSION=$(date +%Y%m%d%H%M%S)
fi
echo $VERSION > .version
mkdir -p dist
for L in v_devices v_regions; do
  ZIP=dist/${L}.zip
  (cd lambdas/${L} && zip -r9 $ROOT_DIR/$ZIP .)
  echo "Uploading $ZIP to s3://$BUCKET/${L}/$VERSION/${L}.zip"
  aws s3 cp "$ZIP" "s3://$BUCKET/${L}/$VERSION/${L}.zip"
done
echo "Uploaded. Version: $VERSION"
