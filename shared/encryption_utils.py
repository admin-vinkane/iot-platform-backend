"""
Encryption utilities for encrypting/decrypting sensitive fields in DynamoDB
Uses AWS KMS for key management (with optional test mode for dummy encryption)
"""

import boto3
import logging
from base64 import b64encode, b64decode
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class FieldEncryption:
    """Handle encryption/decryption of individual fields"""
    
    def __init__(self, region='ap-south-2', key_alias='alias/iot-platform-data', use_test_mode=None):
        """
        Initialize encryption manager
        Args:
            region: AWS region
            key_alias: KMS key alias (or full ARN)
            use_test_mode: If True, use dummy encryption. If None, auto-detect based on KMS availability.
                          Useful for testing without real KMS key setup.
        """
        self.kms = boto3.client('kms', region_name=region)
        self.key_id = key_alias
        self.enabled = True
        self.test_mode = False
        self.test_key = "DUMMY_KEY_FOR_TESTING"  # Fixed key for test mode
        
        # Determine test mode
        if use_test_mode is not None:
            self.test_mode = use_test_mode
            if self.test_mode:
                logger.info(f"🧪 TEST MODE ENABLED: Using dummy encryption for testing")
                self.enabled = True
            return
        
        # Auto-detect: Try real KMS, fall back to test mode if not available
        try:
            self.kms.describe_key(KeyId=self.key_id)
            logger.info("✅ KMS encryption enabled and key accessible")
            self.test_mode = False
        except Exception as e:
            logger.warning(f"⚠️  KMS key not accessible ({e}). Falling back to TEST MODE with dummy encryption.")
            logger.warning(f"⚠️  For production, set up KMS key: alias/iot-platform-data")
            self.test_mode = True
            self.enabled = True
    
    def encrypt_field(self, value, field_name=""):
        """
        Encrypt a single field value
        
        Args:
            value: String or number to encrypt
            field_name: Name of field (for logging)
        
        Returns:
            Dict with encrypted_value, key_version, and encrypted_at timestamp
            Or original value if encryption is disabled
            
        Note: In test mode, uses base64 encoding instead of real KMS encryption
        """
        if not value or not self.enabled:
            return value
        
        try:
            plaintext = str(value).encode('utf-8')
            
            if self.test_mode:
                # Test mode: use base64 as dummy encryption
                encrypted_value = b64encode(plaintext).decode('utf-8')
                logger.debug(f"[TEST MODE] Encrypted field: {field_name}")
            else:
                # Real KMS encryption
                response = self.kms.encrypt(
                    KeyId=self.key_id,
                    Plaintext=plaintext
                )
                encrypted_value = b64encode(response['CiphertextBlob']).decode('utf-8')
                logger.debug(f"Encrypted field: {field_name}")
            
            return {
                'encrypted_value': encrypted_value,
                'key_version': '1',
                'encrypted_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            }
        except Exception as e:
            logger.error(f"Failed to encrypt {field_name}: {str(e)}")
            # Don't fail the request, just log and return original
            return value
    
    def decrypt_field(self, encrypted_data, field_name=""):
        """
        Decrypt a field that was encrypted
        
        Args:
            encrypted_data: Dict with 'encrypted_value' or direct encrypted string
            field_name: Name of field (for logging)
        
        Returns:
            Decrypted string value
            Or original value if it's not encrypted format
            
        Note: In test mode, uses base64 decoding instead of real KMS decryption
        """
        if not self.enabled:
            return encrypted_data
        
        try:
            # Handle both dict format and plain values
            if isinstance(encrypted_data, dict):
                if 'encrypted_value' not in encrypted_data:
                    return encrypted_data
                ciphertext = encrypted_data['encrypted_value']
            else:
                # If it's not a dict, assume it's not encrypted
                return encrypted_data
            
            if self.test_mode:
                # Test mode: use base64 decoding
                decrypted_value = b64decode(ciphertext.encode('utf-8')).decode('utf-8')
                logger.debug(f"[TEST MODE] Decrypted field: {field_name}")
            else:
                # Real KMS decryption
                ciphertext_bytes = b64decode(ciphertext.encode('utf-8'))
                response = self.kms.decrypt(CiphertextBlob=ciphertext_bytes)
                decrypted_value = response['Plaintext'].decode('utf-8')
                logger.debug(f"Decrypted field: {field_name}")
            
            return decrypted_value
        except Exception as e:
            logger.error(f"Failed to decrypt {field_name}: {str(e)}")
            # Return the encrypted data structure if decryption fails
            return encrypted_data
    
    def encrypt_fields(self, data, fields_to_encrypt):
        """
        Encrypt multiple fields in a data dict
        
        Args:
            data: Dictionary with data
            fields_to_encrypt: List of field names to encrypt
        
        Returns:
            Dictionary with specified fields encrypted
        """
        if not self.enabled:
            return data
        
        result = data.copy()
        for field in fields_to_encrypt:
            if field in result and result[field]:
                result[field] = self.encrypt_field(result[field], field)
        
        return result
    
    def decrypt_fields(self, data, fields_to_decrypt):
        """
        Decrypt multiple fields in a data dict
        
        Args:
            data: Dictionary with encrypted data
            fields_to_decrypt: List of field names to decrypt
        
        Returns:
            Dictionary with specified fields decrypted
        """
        if not self.enabled:
            return data
        
        result = data.copy()
        for field in fields_to_decrypt:
            if field in result and result[field]:
                result[field] = self.decrypt_field(result[field], field)
        
        return result


# Define which fields should be encrypted for each entity type
ENCRYPTION_CONFIG = {
    'SIM': {
        'encrypt': ['mobileNumber', 'MobileNumber', 'provider', 'Provider'],
        'decrypt': ['mobileNumber', 'MobileNumber', 'provider', 'Provider']
    },
    'SIM_ASSOC': {
        'encrypt': [],
        'decrypt': []
    },
    'CUSTOMER': {
        'encrypt': ['name', 'email', 'phone', 'companyName'],
        'decrypt': ['name', 'email', 'phone', 'companyName']
    },
    'USER': {
        'encrypt': ['firstName', 'lastName', 'name'],
        'decrypt': ['firstName', 'lastName', 'name']
    },
    'INSTALL': {
        'encrypt': [],
        'decrypt': []
    },
    'DEVICE': {
        'encrypt': ['SerialNumber', 'serialNumber'],
        'decrypt': ['SerialNumber', 'serialNumber']
    }
}


def get_fields_to_encrypt(entity_type):
    """Get list of fields to encrypt for entity type"""
    return ENCRYPTION_CONFIG.get(entity_type, {}).get('encrypt', [])


def get_fields_to_decrypt(entity_type):
    """Get list of fields to decrypt for entity type"""
    return ENCRYPTION_CONFIG.get(entity_type, {}).get('decrypt', [])


# Initialize encryption instance for the module
encryption = FieldEncryption(region='ap-south-2', key_alias='alias/iot-platform-data')


def prepare_item_for_storage(item, entity_type):
    """
    Encrypt sensitive fields before storing to DynamoDB
    
    Args:
        item: Dictionary of data to store
        entity_type: Type of entity (DEVICE, SIM, CUSTOMER, etc.)
    
    Returns:
        Item with encrypted fields
    """
    fields_to_encrypt = get_fields_to_encrypt(entity_type)
    if not fields_to_encrypt:
        return item
    
    result = item.copy()
    for field in fields_to_encrypt:
        if field in result and result[field]:
            result[field] = encryption.encrypt_field(result[field], field)
    
    logger.debug(f"Prepared {entity_type} for storage with {len(fields_to_encrypt)} encrypted fields")
    return result


def prepare_item_for_response(item, entity_type, decrypt=False):
    """
    Optionally decrypt sensitive fields after retrieving from DynamoDB
    
    Args:
        item: Dictionary of data retrieved
        entity_type: Type of entity (DEVICE, SIM, CUSTOMER, etc.)
        decrypt: Boolean - if True, decrypt fields; if False, return as-is (encrypted)
    
    Returns:
        Item with decrypted fields (if decrypt=True) or encrypted fields (if decrypt=False)
    
    By default, returns encrypted data. Pass decrypt=True to get plaintext.
    """
    def _is_encrypted_dict(value):
        return isinstance(value, dict) and "encrypted_value" in value

    if not decrypt:
        # Return encrypted data; if plaintext is present, encrypt it for the response
        fields_to_encrypt = get_fields_to_encrypt(entity_type)
        if not fields_to_encrypt:
            return item

        result = item.copy()
        for field in fields_to_encrypt:
            if field in result and result[field] and not _is_encrypted_dict(result[field]):
                result[field] = encryption.encrypt_field(result[field], field)

        logger.debug(f"Prepared {entity_type} for response with {len(fields_to_encrypt)} encrypted fields")
        return result
    
    # Only decrypt if explicitly requested
    fields_to_decrypt = get_fields_to_decrypt(entity_type)
    if not fields_to_decrypt:
        return item
    
    result = item.copy()
    for field in fields_to_decrypt:
        if field in result and result[field]:
            result[field] = encryption.decrypt_field(result[field], field)
    
    logger.debug(f"Prepared {entity_type} for response with {len(fields_to_decrypt)} decrypted fields")
    return result
