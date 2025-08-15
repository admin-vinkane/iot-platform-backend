#!/bin/bash
set -e
ROOT_DIR=$(pwd)
mkdir -p dist
for L in v_devices v_regions; do
  ZIP=dist/${L}.zip
  (cd lambdas/${L} && zip -r9 $ROOT_DIR/$ZIP .)
  echo "Created $ZIP"
done
echo "All Lambda zips created in dist/"
