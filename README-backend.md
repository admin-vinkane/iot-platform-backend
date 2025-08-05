
# IoT Platform Backend

This repository contains all Python AWS Lambda functions for performing CRUD operations on each DynamoDB table used in the IoT Device Management Platform.

## 📁 Project Structure

```
iot-platform-backend/
├── lambdas/
│   ├── v_users/
│   │   ├── create.py
│   │   ├── read.py
│   │   ├── update.py
│   │   └── delete.py
│   ├── v_states/
│   ├── v_districts/
│   ├── v_mandals/
│   ├── v_villages/
│   ├── v_habitation/
│   ├── v_devices/
│   ├── v_device_registrations/
│   ├── v_installations/
│   └── v_installed_device_registration_usage/
├── shared/
│   └── dynamodb_utils.py
├── requirements.txt
└── README.md
```

## ✅ Features

- Serverless backend using Python 3.12
- One Lambda function per operation per table
- Uses Boto3 to interact with DynamoDB
- Includes timestamp and user tracking
- Modular and scalable

## 🔧 Prerequisites

- Python 3.12+
- AWS CLI configured
- Terraform (for infra)
- Zip CLI (or use `make`/build scripts)

## 📦 Deployment

Each function should be zipped and referenced in Terraform for deployment.

```bash
cd lambdas/v_users
zip create.zip create.py
zip read.zip read.py
...
```

Then deploy using Terraform from the infra repo.

## 🔁 Shared Utilities

The `shared/dynamodb_utils.py` contains reusable code for:
- Input validation
- Timestamp generation
- Error handling
- DynamoDB resource access

## 📩 API Gateway Endpoints

Each Lambda is automatically exposed through API Gateway with endpoints like:

```
POST   /v_users        → create.py
GET    /v_users/{id}   → read.py
PUT    /v_users/{id}   → update.py
DELETE /v_users/{id}   → delete.py
```

## 🧪 Postman Usage

Import the Postman collection from the `iot-platform-api-specs` repo or generate a basic one using the following sample:

### POST /v_users

```json
POST https://<your-api-url>/v_users
Content-Type: application/json

{
  "user_id": "user123",
  "name": "John Doe",
  "email": "john@example.com",
  "created_by": "admin"
}
```

### GET /v_users/{id}

```http
GET https://<your-api-url>/v_users/user123
```

### PUT /v_users/{id}

```json
PUT https://<your-api-url>/v_users/user123
Content-Type: application/json

{
  "name": "Jane Doe",
  "updated_by": "admin"
}
```

### DELETE /v_users/{id}

```http
DELETE https://<your-api-url>/v_users/user123
```

More collections can be auto-generated for each table similarly.

---
