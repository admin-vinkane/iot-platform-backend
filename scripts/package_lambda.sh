#!/bin/bash
# Usage: ./scripts/package_lambda.sh <lambda_dir> <output_zip>
# Example: ./scripts/package_lambda.sh lambdas/v_devices dist/v_devices.zip

set -e

# Check for required CLI tools
if ! command -v pip3 >/dev/null 2>&1; then
  echo "Error: pip3 is not installed. Please install pip3 (Python 3) to build Lambda packages." >&2
  exit 1
fi

LAMBDA_DIR="$1"
OUTPUT_ZIP="$2"
SHARED_DIR="shared"

if [ -z "$LAMBDA_DIR" ] || [ -z "$OUTPUT_ZIP" ]; then
  echo "Usage: $0 <lambda_dir> <output_zip>"
  exit 1
fi

TMP_DIR=$(mktemp -d)

# Copy Lambda code
cp -r "$LAMBDA_DIR"/* "$TMP_DIR"/
# Copy shared utils
cp -r "$SHARED_DIR" "$TMP_DIR/"




# Clean old build artifacts before installing dependencies (Python-only for Lambda Docker compatibility)
python3 -c '
import os, shutil
for root, dirs, files in os.walk("."):
  for d in dirs:
    if d == "__pycache__" or d == "build":
      shutil.rmtree(os.path.join(root, d), ignore_errors=True)
  for f in files:
    if f.endswith(".pyc") or f.endswith(".so"):
      try:
        os.remove(os.path.join(root, f))
      except Exception:
        pass
'

# Print Python and pip version for debug
echo "[DEBUG] Python version: $(python3 --version)"
echo "[DEBUG] Pip version: $(pip3 --version)"

# Install Python dependencies if requirements.txt exists
if [ -f "$LAMBDA_DIR/requirements.txt" ]; then
  echo "[DEBUG] Installing dependencies from $LAMBDA_DIR/requirements.txt"
  pip3 install --force-reinstall --no-cache-dir -r "$LAMBDA_DIR/requirements.txt" -t "$TMP_DIR" --upgrade | tee "$TMP_DIR/pip_install.log"
  if [ "${PIPESTATUS[0]}" -ne 0 ]; then
    echo "Error: pip3 failed to install dependencies for $LAMBDA_DIR. Check requirements.txt and your Python environment." >&2
    rm -rf "$TMP_DIR"
    exit 1
  fi
  echo "[DEBUG] Listing pydantic_core directory after pip install:"
  ls -lR "$TMP_DIR/pydantic_core" || echo "[DEBUG] pydantic_core directory not found in build."
fi




# Create zip using Python's zipfile module for cross-platform compatibility
cd "$TMP_DIR"
if ! python3 -c '
import os, sys, zipfile
def zipdir(path, ziph):
  for root, dirs, files in os.walk(path):
    for file in files:
      full_path = os.path.join(root, file)
      arcname = os.path.relpath(full_path, path)
      ziph.write(full_path, arcname)
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED) as zipf:
  zipdir(".", zipf)
' "$OLDPWD/$OUTPUT_ZIP"; then
  echo "Error: Failed to create zip archive $OUTPUT_ZIP." >&2
  cd "$OLDPWD"
  rm -rf "$TMP_DIR"
  exit 1
fi
cd "$OLDPWD"

# Clean up
echo "Packaged $OUTPUT_ZIP with Lambda and shared code."
rm -rf "$TMP_DIR"
