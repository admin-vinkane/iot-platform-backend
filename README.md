

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

- Use AWS Secrets Manager or SSM Parameter Store for secrets, not plain environment variables.
- All Lambda code uses structured logging and robust error handling.
- IAM policies follow least privilege principle.
  pip install -r lambdas/v_devices/requirements.txt
  pip install -r lambdas/v_regions/requirements.txt
- Automated CI runs linting (`flake8`), formatting (`black`), type checking (`mypy`), and tests (`pytest`).
- Add new dependencies to `requirements.txt` and `requirements-dev.txt`.
- Use `requirements-dev.txt` for development dependencies.
- All code should be formatted with `black` and pass `flake8` and `mypy`.
- Add/expand tests in `tests/` for new features or bugfixes.
2. Configure AWS CLI and credentials.
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

### Prerequisites
- Python 3.8+ and pip
- AWS CLI configured with credentials and region
- S3 bucket for Lambda deployment packages

### 1. Install dependencies
```sh
pip install -r lambdas/v_devices/requirements.txt
pip install -r lambdas/v_regions/requirements.txt
```

### 2. Package all Lambda functions
```sh
chmod +x scripts/package_and_upload_all_lambdas.sh
./scripts/package_and_upload_all_lambdas.sh
```
This creates zip files for each Lambda in the `dist/` directory.

### 3. Upload Lambda packages to S3
```sh
./scripts/package_and_upload_all_lambdas.sh --upload
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
  python -m unittest discover tests
  ```

---

## API Usage
Each Lambda expects HTTP events with the following:
- `POST`/`PUT`: JSON body with `PK` and `SK` (string IDs)
- `GET`/`DELETE`: Query/path params with `PK` and `SK`

## Testing
Run unit tests:
```sh
python -m unittest discover tests
```

## Security
- IAM policies grant only DynamoDB and CloudWatch Logs access for each Lambda.
- Do not store secrets in environment variables; use AWS Secrets Manager if needed.

## CI/CD
- Recommended: Add GitHub Actions for linting, testing, and deployment automation.

## Authors
- Your Name

## License
- Add your license here.
