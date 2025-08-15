

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
## Deployment

To create zip files for each Lambda (for local use or manual upload):
```sh
./scripts/build_zip_only.sh
```
This will create `dist/v_devices.zip` and `dist/v_regions.zip`.

### 2. Build and Upload to S3 (With Versioning)
To build the Lambda zip files and upload them to your S3 bucket with versioning:
```sh
chmod +x scripts/build_and_upload.sh
./scripts/build_and_upload.sh
```
This will zip each Lambda, version by git commit, and upload to S3 at:
```
s3://my-lambda-bucket/<lambda>/<commit-hash>/<lambda>.zip
```

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
