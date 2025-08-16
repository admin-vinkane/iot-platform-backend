

# iot-platform-backend

## Overview
This project provides backend Lambda functions for IoT device and region management, using AWS Lambda and DynamoDB. Each Lambda is versioned by git commit and deployed via a build script.

## Structure
- `lambdas/` — Contains Lambda source code for `v_devices` and `v_regions`.
- `shared/` — Shared Python utilities (e.g., response formatting).
- `iam/` — Example IAM policies for Lambdas.
- `scripts/` — Build and deployment scripts.
- `tests/` — Test events and unit tests.

## Setup
1. Clone the repo and install dependencies for each Lambda:
  ```sh
  pip3 install -r lambdas/v_devices/requirements.txt
  pip3 install -r lambdas/v_regions/requirements.txt
  ```
2. Configure AWS CLI and credentials.
3. Use AWS Secrets Manager or SSM Parameter Store for secrets, not plain environment variables.
4. All Lambda code uses structured logging and robust error handling.
5. IAM policies follow least privilege principle.
6. Automated CI runs linting (`flake8`), formatting (`black`), type checking (`mypy`), and tests (`pytest`).
7. Add new dependencies to `requirements.txt` and `requirements-dev.txt`.
8. Use `requirements-dev.txt` for development dependencies.
9. All code should be formatted with `black` and pass `flake8` and `mypy`.
10. Add/expand tests in `tests/` for new features or bugfixes.
## API Documentation
- Document all API endpoints and payloads in an OpenAPI/Swagger spec (recommended: `openapi.yaml`).
- Add example event payloads and error responses for each Lambda in the docs.

## Integration Testing
- Add integration tests in `tests/` using DynamoDB Local or mocks for database calls.

## Deployment
- Use the provided scripts for packaging and uploading Lambda code.
- For production, use a CI/CD pipeline to automate build, test, and deploy steps.

## Monitoring
- Ensure CloudWatch metrics and alarms are set for Lambda errors and throttles.

## Build & Deploy
## Lambda Packaging & S3 Upload

You can package and upload Lambda functions using the provided scripts. All packaging is done in a Linux-compatible environment using Docker for AWS Lambda compatibility.

### Batch: Package & Upload All Lambdas

**Package all Lambdas (no upload):**
```sh
chmod +x scripts/package_and_upload_all_lambdas.sh
./scripts/package_and_upload_all_lambdas.sh
```
Zips are created in the `dist/` directory.

**Package and upload all Lambdas to S3:**
```sh
# For development
./scripts/package_and_upload_all_lambdas.sh --upload --env dev
# For production
./scripts/package_and_upload_all_lambdas.sh --upload --env prod
```
Zips are uploaded to:
```
s3://<your-lambda-bucket>/<lambda>/<commit-hash>/<lambda>.zip
```

### Single Lambda: Package & Upload

**Package and upload a single Lambda:**
```sh
chmod +x scripts/package_and_upload_lambda.sh
./scripts/package_and_upload_lambda.sh lambdas/<lambda_name> dist/<lambda_name>.zip <your-lambda-bucket> <version>
```
Example:
```sh
./scripts/package_and_upload_lambda.sh lambdas/v_devices dist/v_devices.zip my-lambda-bucket-vinkane-dev 123abc
```
This creates and uploads the zip to:
```
s3://my-lambda-bucket-vinkane-dev/v_devices/123abc/v_devices.zip
```

**Note:**
- All scripts run in Docker for Linux compatibility.
- The `--env` flag sets the S3 bucket for dev/prod.
- The `<version>` is typically the git commit hash.

See script headers for more options and usage details.

### Prerequisites
- Python 3.8+ and pip
- AWS CLI configured with credentials and region
- S3 bucket for Lambda deployment packages

### 1. Install dependencies
```sh
pip install -r lambdas/v_devices/requirements.txt
pip install -r lambdas/v_regions/requirements.txt
```

s3://<your-lambda-bucket>/<lambda>/<commit-hash>/<lambda>.zip
### 2. Package all Lambda functions
```sh
chmod +x scripts/package_and_upload_all_lambdas.sh
./scripts/package_and_upload_all_lambdas.sh
```
This creates zip files for each Lambda in the `dist/` directory.

### 3. Upload Lambda packages to S3 (dev/prod)
For development:
```sh
./scripts/package_and_upload_all_lambdas.sh --upload --env dev
```
For production:
```sh
./scripts/package_and_upload_all_lambdas.sh --upload --env prod
```
This uploads each Lambda zip to:
```
s3://<your-lambda-bucket>/<lambda>/<commit-hash>/<lambda>.zip
```

### 4. Deploy/Update Lambda functions
- Update your infrastructure (e.g., with Terraform) to point to the new S3 object/version for each Lambda.
- Example (Terraform):
  - Set the Lambda source code S3 key and version in your module/variable.
  - Run:
    ```sh
    terraform init
    terraform apply
    ```

### 5. Environment Variables
- Set required environment variables for each Lambda (e.g., TABLE_NAME, ENABLE_AUDIT_LOG) in your deployment config or AWS Console.

### 6. Testing
- Run unit tests:
  ```sh
  python3 -m unittest discover tests
  ```


## API Usage
Each Lambda expects HTTP events with the following:
- `POST`/`PUT`: JSON body with `PK` and `SK` (string IDs)
- `GET`/`DELETE`: Query/path params with `PK` and `SK`


## Security
- IAM policies grant only DynamoDB and CloudWatch Logs access for each Lambda.
- Do not store secrets in environment variables; use AWS Secrets Manager if needed.

## CI/CD
- Recommended: Add GitHub Actions for linting, testing, and deployment automation.

## Authors
- Your Name

## License
- Add your license here.
