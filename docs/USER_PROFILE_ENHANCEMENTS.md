# User Profile Enhancements - Implementation Guide

## Overview

This document covers the optional enhancements implemented for the User Profile API, including Firebase integration, S3 profile picture uploads, migration tools, and database optimizations.

---

## 1. Enhanced Firebase Sync

### **What's New**

The `/users/sync` endpoint now automatically:
- Extracts `displayName` from Firebase token and splits into `firstName`/`lastName`
- Syncs `photoURL` from Firebase to profile's `profilePictureUrl`
- Creates or updates user profile during login
- Non-blocking: Profile sync failures don't prevent login

### **How It Works**

When a user logs in via Firebase:
1. Firebase token is verified
2. User is found/updated in DynamoDB
3. **NEW**: Profile is automatically created/updated with:
   - `firstName` & `lastName` from Firebase `displayName`
   - `profilePictureUrl` from Firebase `photoURL`
4. Login count increments

### **Code Example**

```python
# Firebase token claims include:
{
  "uid": "firebase-user-id",
  "email": "user@example.com",
  "name": "John Doe",  # NEW: Used for firstName/lastName
  "picture": "https://...photo.jpg",  # NEW: Synced to profile
  "email_verified": true
}
```

### **Benefits**

- **Automatic Profile Creation**: Users get profiles on first login
- **Data Consistency**: Firebase profile data stays in sync
- **Better UX**: Profile pictures appear immediately after Google/social login

---

## 2. S3 Profile Picture Upload

### **Two Upload Methods**

#### **Method 1: Base64 Upload (Simpler)**

**Endpoint:** `POST /users/{userId}/profile/picture`

Upload a base64-encoded image directly through the API.

**Request:**
```json
{
  "imageData": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "contentType": "image/jpeg",
  "fileExtension": "jpg"
}
```

**Response:**
```json
{
  "message": "Profile picture uploaded successfully",
  "profilePictureUrl": "https://bucket.s3.amazonaws.com/profile-pictures/user1/20260204160000.jpg",
  "s3Key": "profile-pictures/user1/20260204160000.jpg"
}
```

**Limits:**
- Max file size: 5MB
- Allowed types: `image/jpeg`, `image/jpg`, `image/png`, `image/webp`

**React Example:**
```typescript
async function uploadProfilePicture(userId: string, file: File) {
  const reader = new FileReader();
  
  return new Promise((resolve, reject) => {
    reader.onload = async () => {
      const base64 = reader.result as string;
      const token = await firebaseAuth.currentUser?.getIdToken();
      
      const response = await fetch(
        `${API_BASE_URL}/users/${userId}/profile/picture`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            imageData: base64,
            contentType: file.type,
            fileExtension: file.name.split('.').pop()
          })
        }
      );
      
      const result = await response.json();
      resolve(result.profilePictureUrl);
    };
    
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
```

---

#### **Method 2: Presigned URL Upload (Better for Large Files)**

**Endpoint:** `GET /users/{userId}/profile/picture/upload-url`

Get a presigned S3 URL for direct client-to-S3 upload (no Lambda size limits).

**Query Parameters:**
- `contentType`: MIME type (default: `image/jpeg`)
- `fileExtension`: File extension (default: `jpg`)

**Response:**
```json
{
  "uploadUrl": "https://bucket.s3.amazonaws.com/",
  "fields": {
    "key": "profile-pictures/user1/20260204160000.jpg",
    "Content-Type": "image/jpeg",
    "x-amz-meta-userId": "user1",
    "policy": "...",
    "x-amz-signature": "..."
  },
  "profilePictureUrl": "https://bucket.s3.amazonaws.com/profile-pictures/user1/20260204160000.jpg",
  "s3Key": "profile-pictures/user1/20260204160000.jpg",
  "expiresIn": 3600
}
```

**React Example:**
```typescript
async function uploadProfilePicturePresigned(userId: string, file: File) {
  const token = await firebaseAuth.currentUser?.getIdToken();
  
  // Step 1: Get presigned URL
  const urlResponse = await fetch(
    `${API_BASE_URL}/users/${userId}/profile/picture/upload-url?contentType=${file.type}&fileExtension=${file.name.split('.').pop()}`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );
  
  const { uploadUrl, fields, profilePictureUrl } = await urlResponse.json();
  
  // Step 2: Upload directly to S3
  const formData = new FormData();
  Object.entries(fields).forEach(([key, value]) => {
    formData.append(key, value as string);
  });
  formData.append('file', file);
  
  await fetch(uploadUrl, {
    method: 'POST',
    body: formData
  });
  
  // Step 3: Update profile with new URL
  await fetch(
    `${API_BASE_URL}/users/${userId}/profile`,
    {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ profilePictureUrl })
    }
  );
  
  return profilePictureUrl;
}
```

---

### **S3 Bucket Configuration**

#### **Required Environment Variable**
```bash
S3_BUCKET_NAME=iot-platform-profile-pictures
```

#### **S3 Bucket Setup**
```bash
# Create bucket
aws s3 mb s3://iot-platform-profile-pictures --region ap-south-2

# Enable public read access (adjust based on security needs)
aws s3api put-bucket-policy --bucket iot-platform-profile-pictures --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::iot-platform-profile-pictures/profile-pictures/*"
  }]
}'

# Enable CORS
aws s3api put-bucket-cors --bucket iot-platform-profile-pictures --cors-configuration '{
  "CORSRules": [{
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "POST", "PUT"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }]
}'
```

#### **Lambda IAM Permissions**
Add to Lambda execution role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::iot-platform-profile-pictures/profile-pictures/*"
    }
  ]
}
```

---

## 3. User Profile Migration Script

### **Purpose**

Create default profiles for all existing users who don't have one yet.

### **Usage**

```bash
# Dry run (preview only)
python scripts/migrate_user_profiles.py --dry-run

# Production run
python scripts/migrate_user_profiles.py

# Custom table
python scripts/migrate_user_profiles.py --table-name v_users_prod
```

### **What It Does**

1. Scans the users table for all user records
2. Checks if each user has a profile (PK=USER#{userId}, SK=PROFILE#MAIN)
3. Creates default profile if missing:
   - Copies `firstName`, `lastName`, `phoneNumber` from user record
   - Sets default language to `en`
   - Creates empty address and default preferences

### **Output Example**

```
============================================================
Starting User Profile Migration
Table: v_users_dev
Dry Run: False
============================================================
Scanning table: v_users_dev
Found 50 user records
Profile already exists for user: user1
Created profile for user: user2 (user2@example.com)
Created profile for user: user3 (user3@example.com)
...
============================================================
Migration Summary
============================================================
Total users processed:    50
Profiles already existed: 20
Profiles created:         30
Profiles failed:          0
============================================================
Migration complete!
```

### **Prerequisites**

```bash
pip install boto3
```

### **AWS Credentials**

Ensure AWS credentials are configured:
```bash
aws configure
# OR set environment variables:
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=ap-south-2
```

---

## 4. Email GSI (Global Secondary Index)

### **Problem**

Currently, user lookup by email uses `table.scan()` which is:
- ❌ Slow for large tables
- ❌ Expensive (reads all items)
- ❌ Not scalable

### **Solution: Add Email GSI**

#### **GSI Configuration**

```
Index Name: email-index
Partition Key: email (String)
Projection: ALL (or KEYS_ONLY + required fields)
```

#### **Create GSI via AWS CLI**

```bash
aws dynamodb update-table \
  --table-name v_users_dev \
  --attribute-definitions AttributeName=email,AttributeType=S \
  --global-secondary-index-updates '[
    {
      "Create": {
        "IndexName": "email-index",
        "KeySchema": [
          {"AttributeName": "email", "KeyType": "HASH"}
        ],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {
          "ReadCapacityUnits": 5,
          "WriteCapacityUnits": 5
        }
      }
    }
  ]'
```

#### **Code Update (After GSI is Active)**

Replace email scan with query:

```python
# OLD (Slow):
response = table.scan(
    FilterExpression="email = :email",
    ExpressionAttributeValues={":email": email}
)

# NEW (Fast):
response = table.query(
    IndexName="email-index",
    KeyConditionExpression="email = :email",
    ExpressionAttributeValues={":email": email}
)
```

#### **Benefits**

- ✅ **Fast**: O(1) lookup instead of O(n) scan
- ✅ **Cost-efficient**: Only reads matching items
- ✅ **Scalable**: Performance doesn't degrade with table size

---

## Summary of Enhancements

| Enhancement | Status | Benefit |
|-------------|--------|---------|
| Firebase Photo Sync | ✅ Implemented | Auto-sync profile pictures from Google/social login |
| Base64 Picture Upload | ✅ Implemented | Simple browser-to-Lambda upload |
| Presigned URL Upload | ✅ Implemented | Direct client-to-S3, no size limits |
| Migration Script | ✅ Implemented | Backfill profiles for existing users |
| Email GSI | 📋 Documented | 100x faster email lookups |

---

## Testing Checklist

### Firebase Sync
- [ ] Login creates profile automatically
- [ ] Firebase displayName splits into firstName/lastName
- [ ] Firebase photoURL syncs to profilePictureUrl
- [ ] Existing profiles update on login

### Profile Picture Upload
- [ ] Base64 upload works (< 5MB)
- [ ] Presigned URL upload works (any size)
- [ ] Invalid file types rejected
- [ ] Profile updates with new URL
- [ ] Old pictures remain accessible (no deletion)

### Migration
- [ ] Dry run shows preview
- [ ] Production run creates profiles
- [ ] Existing profiles not duplicated
- [ ] firstName/lastName copied from users

### Email GSI
- [ ] GSI creation complete (check DynamoDB console)
- [ ] Query replaces scan in code
- [ ] Email lookups are fast (< 100ms)

---

## Next Steps

1. **Deploy Lambda** with new code
2. **Create S3 bucket** for profile pictures
3. **Run migration** to create profiles for existing users
4. **Add Email GSI** to DynamoDB table
5. **Update code** to use email GSI after it's active
6. **Test** all upload methods in production

---

## Troubleshooting

### "S3 bucket not found"
- Ensure `S3_BUCKET_NAME` environment variable is set in Lambda
- Create the bucket: `aws s3 mb s3://iot-platform-profile-pictures`

### "Access Denied" on S3
- Check Lambda IAM role has `s3:PutObject` permission
- Verify bucket name in code matches actual bucket

### Migration script fails
- Check AWS credentials: `aws sts get-caller-identity`
- Verify table name: `aws dynamodb describe-table --table-name v_users_dev`

### Email lookup still slow
- Check GSI status: `aws dynamodb describe-table --table-name v_users_dev | jq '.Table.GlobalSecondaryIndexes'`
- Ensure code uses `table.query()` with `IndexName="email-index"`
