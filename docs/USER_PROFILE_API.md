# User Profile API Documentation

## Overview

The User Profile API provides endpoints to manage user profile information separately from core user authentication data. Profiles are stored in the same DynamoDB table as users but with a separate partition key pattern.

## DynamoDB Schema

### Profile Entity
```
PK: USER#{userId}
SK: PROFILE#MAIN
entityType: USER_PROFILE

Fields:
- userId: string
- firstName: string
- lastName: string
- phoneNumber: string (encrypted)
- language: string (ISO 639-1 code, e.g., "en", "es")
- organization: string (optional)
- department: string (optional)
- timezone: string (default: "UTC")
- profilePictureUrl: string (optional)
- address: {
    street: string
    city: string
    state: string
    country: string
    postalCode: string
  }
- preferences: {
    notifications: boolean
    emailAlerts: boolean
    smsAlerts: boolean
  }
- createdAt: ISO 8601 timestamp
- updatedAt: ISO 8601 timestamp
```

## API Endpoints

### 1. Get User Profile

**Endpoint:** `GET /users/{userId}/profile`

**Description:** Retrieves the profile for a specific user. If the profile doesn't exist, a default profile is automatically created.

**Authorization:** 
- Users can only access their own profile
- Admins can access any profile

**Path Parameters:**
- `userId` (required): The user ID

**Query Parameters:**
- `decrypt` (optional): Whether to decrypt sensitive fields (default: true)

**Response (200 OK):**
```json
{
  "PK": "USER#user1",
  "SK": "PROFILE#MAIN",
  "userId": "user1",
  "entityType": "USER_PROFILE",
  "firstName": "John",
  "lastName": "Doe",
  "phoneNumber": "+1234567890",
  "language": "en",
  "organization": "ACME Corp",
  "department": "Engineering",
  "timezone": "America/New_York",
  "profilePictureUrl": "https://example.com/photo.jpg",
  "address": {
    "street": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "country": "USA",
    "postalCode": "94105"
  },
  "preferences": {
    "notifications": true,
    "emailAlerts": true,
    "smsAlerts": false
  },
  "createdAt": "2026-02-04T16:00:00Z",
  "updatedAt": "2026-02-04T16:30:00Z"
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User attempting to access another user's profile
- `404 Not Found`: User not found
- `500 Internal Server Error`: Server error

---

### 2. Update User Profile (Full Update)

**Endpoint:** `PUT /users/{userId}/profile`

**Description:** Replaces the entire profile with new data. All fields should be provided.

**Authorization:**
- Users can only update their own profile
- Admins can update any profile

**Path Parameters:**
- `userId` (required): The user ID

**Request Body:**
```json
{
  "firstName": "John",
  "lastName": "Doe",
  "phoneNumber": "+1234567890",
  "language": "en",
  "organization": "ACME Corp",
  "department": "Engineering",
  "timezone": "America/New_York",
  "profilePictureUrl": "https://example.com/photo.jpg",
  "address": {
    "street": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "country": "USA",
    "postalCode": "94105"
  },
  "preferences": {
    "notifications": true,
    "emailAlerts": true,
    "smsAlerts": false
  }
}
```

**Response (200 OK):**
```json
{
  "message": "Profile updated successfully",
  "profile": {
    "PK": "USER#user1",
    "SK": "PROFILE#MAIN",
    "userId": "user1",
    "firstName": "John",
    "lastName": "Doe",
    "phoneNumber": "+1234567890",
    "language": "en",
    "organization": "ACME Corp",
    "department": "Engineering",
    "timezone": "America/New_York",
    "profilePictureUrl": "https://example.com/photo.jpg",
    "address": {
      "street": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "country": "USA",
      "postalCode": "94105"
    },
    "preferences": {
      "notifications": true,
      "emailAlerts": true,
      "smsAlerts": false
    },
    "createdAt": "2026-02-04T16:00:00Z",
    "updatedAt": "2026-02-04T16:45:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request body or validation error
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User attempting to update another user's profile
- `500 Internal Server Error`: Server error

---

### 3. Update User Profile (Partial Update)

**Endpoint:** `PATCH /users/{userId}/profile`

**Description:** Updates only the specified fields in the profile. Unspecified fields remain unchanged.

**Authorization:**
- Users can only update their own profile
- Admins can update any profile

**Path Parameters:**
- `userId` (required): The user ID

**Request Body (all fields optional):**
```json
{
  "language": "es",
  "preferences": {
    "notifications": false
  }
}
```

**Response (200 OK):**
```json
{
  "message": "Profile updated successfully",
  "profile": {
    "PK": "USER#user1",
    "SK": "PROFILE#MAIN",
    "userId": "user1",
    "firstName": "John",
    "lastName": "Doe",
    "phoneNumber": "+1234567890",
    "language": "es",
    "organization": "ACME Corp",
    "department": "Engineering",
    "timezone": "America/New_York",
    "profilePictureUrl": "https://example.com/photo.jpg",
    "address": {
      "street": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "country": "USA",
      "postalCode": "94105"
    },
    "preferences": {
      "notifications": false,
      "emailAlerts": true,
      "smsAlerts": false
    },
    "createdAt": "2026-02-04T16:00:00Z",
    "updatedAt": "2026-02-04T17:00:00Z"
  },
  "updatedFields": ["language", "preferences"]
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request body, no fields to update, or validation error
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User attempting to update another user's profile
- `500 Internal Server Error`: Server error

---

## Field Validation

### Required Fields
- `firstName`: 1-100 characters
- `lastName`: 1-100 characters

### Optional Fields
- `phoneNumber`: E.164 format (e.g., +1234567890)
- `language`: ISO 639-1 code (2 lowercase letters, e.g., "en", "es", "fr")
- `organization`: Max 200 characters
- `department`: Max 100 characters
- `timezone`: Max 50 characters (e.g., "America/New_York", "UTC")
- `profilePictureUrl`: Valid URL

### Address Fields (all optional)
- `street`: Max 200 characters
- `city`: Max 100 characters
- `state`: Max 100 characters
- `country`: Max 100 characters
- `postalCode`: Max 20 characters

### Preferences (all boolean)
- `notifications`: Enable/disable all notifications
- `emailAlerts`: Enable/disable email alerts
- `smsAlerts`: Enable/disable SMS alerts

---

## Security

### Encryption
- `phoneNumber` field is encrypted at rest using the shared encryption utilities
- `address` fields are encrypted for privacy

### Authorization
- All profile endpoints require authentication via Firebase token in `Authorization: Bearer <token>` header
- Users can only access/modify their own profile unless they have admin role
- Admins have full access to all profiles

### Rate Limiting
- Consider implementing rate limiting for profile updates to prevent abuse
- Recommended: 10 updates per minute per user

---

## React Integration Example

```typescript
import { firebaseAuth } from './firebase';

export const profileApi = {
  async getUserProfile(userId: string): Promise<UserProfile> {
    const token = await firebaseAuth.currentUser?.getIdToken();
    
    const response = await fetch(
      `${API_BASE_URL}/users/${userId}/profile`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    if (!response.ok) {
      throw new Error(`Failed to get profile: ${response.statusText}`);
    }
    
    return await response.json();
  },
  
  async updateProfile(
    userId: string, 
    data: UpdateProfileRequest
  ): Promise<UserProfile> {
    const token = await firebaseAuth.currentUser?.getIdToken();
    
    const response = await fetch(
      `${API_BASE_URL}/users/${userId}/profile`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      }
    );
    
    if (!response.ok) {
      throw new Error(`Failed to update profile: ${response.statusText}`);
    }
    
    const result = await response.json();
    return result.profile;
  }
};
```

---

## Notes

1. **Auto-Creation**: If a profile doesn't exist when `GET` is called, a default profile is automatically created using data from the user entity
2. **Sync with User**: Changes to `firstName` and `lastName` in the profile should also update the user entity for consistency
3. **Language Preference**: The `language` field should be used to set the UI locale in the React application
4. **Profile Picture**: The `profilePictureUrl` can be synced from Firebase photoURL during user sync
5. **Timezone**: Use for displaying dates/times in user's local timezone

---

## Migration Script

To create profiles for existing users, run:

```bash
# Coming soon: migration script
node scripts/migrate-user-profiles.js
```
