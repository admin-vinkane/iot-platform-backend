

# iot-platform-backend

## Overview
This project provides backend Lambda functions for IoT device management, region management, user management, and navigation/menu management, using AWS Lambda and DynamoDB. Each Lambda is versioned by git commit and deployed via a build script.

## Structure
- `lambdas/` — Contains Lambda source code for:
  - `v_devices` — Device management API
  - `v_regions` — Region management API
  - `v_users` — User management and RBAC/Permissions API
  - `v_navigation` — Navigation/Menu management API
  - `v_customers` — Customer management API
  - `v_simcards` — SIM card management API
  - Other domain-specific lambdas
- `shared/` — Shared Python utilities (e.g., response formatting, encryption).
- `iam/` — Example IAM policies for Lambdas.
- `scripts/` — Build and deployment scripts.
- `tests/` — Test events and unit tests.
- `docs/` — API documentation and implementation guides.

## Setup
1. Clone the repo and install dependencies for each Lambda:
  ```sh
  pip3 install -r lambdas/v_devices/requirements.txt
  pip3 install -r lambdas/v_regions/requirements.txt
  pip3 install -r lambdas/v_users/requirements.txt
  pip3 install -r lambdas/v_navigation/requirements.txt
  # ... and other lambdas as needed
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
11. Python Local Environment and Virtual Env(venv) setup
- To avoid conflicts with other python versions and packages
- Pyenv helps switching between different python versions globally or locally at specific project level
1. Install pyenv
brew update
brew install pyenv
pyenv --version
2. Configure your shell to use pyenv
Add these lines to ~/.zshrc: (or whichever shell you have)

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"

Reload the shell
3. Install a python version using pyenv.
pyenv install --list : check what is installed
pyenv install 3.9.6 : install specific version you want

pyenv global 3.9.6 : set globally

cd /path/to/project : set locally for a project
pyenv local 3.9.6

4. Verify python version
python --version
which python

5. create a venv using pyenv python version which is currently set
python -m venv .venv
source .venv/bin/activate

Tip: Always use pyenv + venv together: pyenv manages Python versions, venv manages project dependencies.

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
./scripts/package_and_upload_lambda.sh <lambda_dir> --env dev|prod [--upload]
```

**Usage:**
- `<lambda_dir>` - Lambda directory (e.g., `lambdas/v_devices`)
- `--env dev|prod` - Environment (mandatory)
- `--upload` - Upload to S3 (optional, without this flag it only packages locally)

**Examples:**
```sh
# Just package v_devices locally (no upload)
./scripts/package_and_upload_lambda.sh lambdas/v_devices --env dev

# Package and upload v_devices to dev environment
./scripts/package_and_upload_lambda.sh lambdas/v_devices --env dev --upload

# Package and upload v_regions to prod environment  
./scripts/package_and_upload_lambda.sh lambdas/v_regions --env prod --upload

# Package and upload v_navigation to dev environment
./scripts/package_and_upload_lambda.sh lambdas/v_navigation --env dev --upload
```

**Behavior:**
- Always creates zip in `dist/<lambda_name>.zip`
- With `--upload`: Uploads to S3
- Without `--upload`: Only packages locally
- S3 bucket is automatically selected based on environment:
  - `dev` → `my-lambda-bucket-vinkane-dev`
  - `prod` → `my-lambda-bucket-vinkane-prod`
- Version is automatically set to fixed version (20250816204228)
- Uploads to S3 key: `<lambda_name>/<version>/<lambda_name>.zip`

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
pip install -r lambdas/v_users/requirements.txt
pip install -r lambdas/v_navigation/requirements.txt
# ... and other lambdas as needed
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
- Run unit tests using pytest
```pytest```

## API Documentation

📚 **[Complete API Overview](docs/API_OVERVIEW.md)** - All endpoints across all services

### Available APIs

| Lambda | Purpose | Documentation |
|--------|---------|---------------|
| `v_navigation` 🆕 | Navigation/Menu management | [NAVIGATION_API_IMPLEMENTATION.md](docs/NAVIGATION_API_IMPLEMENTATION.md) |
| `v_users` | User management, RBAC, Permissions | [USERS_API_IMPROVEMENTS.md](docs/USERS_API_IMPROVEMENTS.md) |
| `v_devices` | Device management | [DEVICES_API_ROUTES.md](docs/DEVICES_API_ROUTES.md) |
| `v_regions` | Region management | [REGIONS_API_GUIDE.md](docs/REGIONS_API_GUIDE.md) |
| `v_customers` | Customer management | [CUSTOMER_ENDPOINTS_REVIEW.md](docs/CUSTOMER_ENDPOINTS_REVIEW.md) |

### Navigation API (NEW)

The Navigation API provides complete menu/navigation management with:
- **11 endpoints** for CRUD operations on groups and items
- **Audit trail** tracking all changes with before/after values
- **Validation** for uniqueness, ordering, and path formats
- **Hierarchical structure** with groups containing items

**Quick Start:**
```bash
# List all navigation groups with items
GET /navigation/groups

# Create a navigation group
POST /navigation/groups
{
  "label": "Administration",
  "icon": "Shield",
  "order": 1
}

# Create a navigation item
POST /navigation/groups/{groupId}/items
{
  "label": "Menu Management",
  "icon": "Grid",
  "path": "/menu-management",
  "permission": "can_manage_navigation",
  "order": 1
}
```

See [NAVIGATION_API_IMPLEMENTATION.md](docs/NAVIGATION_API_IMPLEMENTATION.md) for complete documentation.

### Infrastructure

For Terraform infrastructure setup:
- [NAVIGATION_TERRAFORM_INFRA.md](docs/NAVIGATION_TERRAFORM_INFRA.md) - Complete DynamoDB and API Gateway configuration
- [NAVIGATION_INFRA_QUICK_REFERENCE.md](NAVIGATION_INFRA_QUICK_REFERENCE.md) - Quick reference for table and routes

## API Usage
Each Lambda expects HTTP events with the following:
- `POST`/`PUT`: JSON body with required fields (varies by endpoint)
- `GET`/`DELETE`: Query/path params with resource identifiers
- All responses follow standardized format using `shared.response_utils`


## Security
- IAM policies grant only DynamoDB and CloudWatch Logs access for each Lambda.
- Do not store secrets in environment variables; use AWS Secrets Manager if needed.

## CI/CD
- Recommended: Add GitHub Actions for linting, testing, and deployment automation.

## Deployment Status

| Lambda | Deployment Status | Last Updated |
|--------|------------------|--------------|
| v_navigation | ✅ Deployed | 2026-02-10 |
| v_users | ✅ Deployed | - |
| v_devices | ✅ Deployed | - |
| v_regions | ✅ Deployed | - |
| v_customers | ✅ Deployed | - |

## Authors
- Your Name

## License
- Add your license here.
