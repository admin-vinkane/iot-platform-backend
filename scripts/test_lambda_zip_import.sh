#!/bin/bash
# Test if pydantic_core._pydantic_core can be imported in the same environment as AWS Lambda
# Usage: ./test_lambda_zip_import.sh dist/v_regions.zip

set -e

ZIPFILE="$1"
if [ -z "$ZIPFILE" ]; then
  echo "Usage: $0 <lambda_zip_file>"
  exit 1
fi

docker run --platform linux/amd64 --rm --entrypoint /bin/bash -v "$PWD/$ZIPFILE":/tmp/lambda.zip public.ecr.aws/lambda/python:3.12 -c '
  cd /tmp
  rm -rf test_lambda && mkdir test_lambda
  python3 -c "import zipfile; zipfile.ZipFile('lambda.zip').extractall('test_lambda')"
  cd test_lambda
  echo "[INFO] Files in test_lambda:"
  ls -l
  echo "[INFO] Attempting import..."
  python3 -c "import pydantic_core._pydantic_core; print(\"Import OK\")"
'
