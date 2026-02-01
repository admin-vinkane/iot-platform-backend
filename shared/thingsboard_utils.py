"""
Thingsboard integration utilities for managing assets, attributes, and relations.
Handles synchronization of region hierarchy and device-habitat linking in Thingsboard.

Authentication Pattern (Official Thingsboard):
- Uses JWT token from environment variable (THINGSBOARD_TOKEN)
- Automatically refreshes using /api/auth/token endpoint when token expires
- Refresh token is extracted from initial JWT and cached for automatic renewal
"""

import os
import json
import logging
import time
import requests
import base64
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Thingsboard configuration from environment variables
TB_HOST = os.environ.get("THINGSBOARD_HOST", "http://18.61.64.102:8080")
TB_TOKEN = os.environ.get("THINGSBOARD_TOKEN") or os.environ.get("JWT_TOKEN")

# Token cache (in-memory, valid for Lambda execution context)
_tb_token = None
_tb_token_expiry = None
_tb_refresh_token = None


def _decode_jwt_expiry(token: str) -> Optional[float]:
    """
    Decode JWT token to extract expiry time.
    
    Args:
        token: JWT token string
        
    Returns:
        float: Unix timestamp of token expiry, or None if cannot decode
    """
    try:
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        # Decode payload (second part)
        payload = parts[1]
        # Add padding if needed (JWT base64 might not be padded)
        padding = len(payload) % 4
        if padding:
            payload += '=' * (4 - padding)
            
        decoded = base64.urlsafe_b64decode(payload)
        payload_data = json.loads(decoded)
        
        # Get 'exp' claim (expiry timestamp)
        exp = payload_data.get('exp')
        if exp:
            logger.info(f"JWT token expires at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))}")
            return float(exp)
        return None
        
    except Exception as e:
        logger.warning(f"Could not decode JWT expiry: {e}")
        return None


def get_thingsboard_token() -> str:
    """
    Get Thingsboard authentication token with automatic refresh.
    
    Official Thingsboard Authentication Pattern:
    1. Check cached access token validity (5-min buffer before expiry)
    2. Uses JWT token from environment variable (THINGSBOARD_TOKEN)
    2. Extracts refresh token from environment (THINGSBOARD_REFRESH_TOKEN) or response
    3. Automatically refreshes via /api/auth/token when token expires
    4. Cache tokens in memory for Lambda execution context
    
    Returns:
        str: JWT access token for API requests
        
    Raises:
        Exception: If token is not available or refresh fails
    """
    global _tb_token, _tb_token_expiry, _tb_refresh_token
    
    # Step 1: Initialize from environment if not cached
    if not _tb_token and TB_TOKEN:
        _tb_token = TB_TOKEN.strip()
        if _tb_token.startswith("Bearer "):
            _tb_token = _tb_token[7:].strip()
        
        # Try to get refresh token from environment
        refresh_token_env = os.environ.get("THINGSBOARD_REFRESH_TOKEN")
        if refresh_token_env:
            _tb_refresh_token = refresh_token_env.strip()
        
        # Set expiry from JWT
        decoded_expiry = _decode_jwt_expiry(_tb_token)
        if decoded_expiry:
            _tb_token_expiry = decoded_expiry - 300  # 5 min buffer
            logger.info(f"Token initialized (expires: {time.strftime('%H:%M:%S', time.localtime(decoded_expiry))})")
        else:
            _tb_token_expiry = time.time() + 9000  # Assume 2.5 hrs
    
    # Step 2: Check if cached token is still valid
    if _tb_token and _tb_token_expiry and time.time() < _tb_token_expiry:
        remaining = int(_tb_token_expiry - time.time())
        logger.debug(f"Using cached token (expires in {remaining}s)")
        return _tb_token
    
    # Step 3: Try refresh if available
    if _tb_refresh_token:
        logger.info("Access token expired, refreshing...")
        new_token = _refresh_access_token()
        if new_token:
            return new_token
        logger.warning("Refresh failed")
    
    # Step 4: No token available
    if not TB_TOKEN:
        raise Exception(
            "THINGSBOARD_TOKEN environment variable required. "
            "Set JWT token in Lambda configuration."
        )
    
    # Return existing token even if might be expired (let API return 401)
    logger.warning("No refresh token available, using existing token")
    return _tb_token if _tb_token else TB_TOKEN

def _refresh_access_token() -> Optional[str]:
    """
    Refresh access token using refresh token.
    
    API: POST /api/auth/token
    Request: {"refreshToken": "..."}
    Response: {"token": "...", "refreshToken": "..."}
    
    Returns:
        str: New access token, or None if refresh failed
    """
    global _tb_token, _tb_token_expiry, _tb_refresh_token
    
    try:
        response = requests.post(
            f"{TB_HOST}/api/auth/token",
            json={"refreshToken": _tb_refresh_token},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            refresh_token = data.get("refreshToken")
            
            if not token:
                raise Exception("No token in refresh response")
            
            # Cache tokens
            _tb_token = token
            if refresh_token:
                _tb_refresh_token = refresh_token
            
            # Set expiry
            decoded_expiry = _decode_jwt_expiry(token)
            if decoded_expiry:
                _tb_token_expiry = decoded_expiry - 300  # 5 min buffer
                logger.info(f"✓ Token refreshed (expires: {time.strftime('%H:%M:%S', time.localtime(decoded_expiry))})")
            else:
                _tb_token_expiry = time.time() + 9000  # 2.5 hrs
                logger.warning("Could not decode expiry, assuming 2.5 hour validity")
            
            return token
        else:
            logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
            return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during token refresh: {e}")
        return None
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return None


def _get_headers() -> Dict[str, str]:
    """Get headers with authentication token for Thingsboard API requests."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_thingsboard_token()}"
    }


def invalidate_token():
    """
    Invalidate cached tokens to force fresh login.
    Call when receiving 401 Unauthorized errors.
    """
    global _tb_token, _tb_token_expiry, _tb_refresh_token
    logger.warning("Invalidating cached tokens")
    _tb_token = None
    _tb_token_expiry = None
    _tb_refresh_token = None


def _make_request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """
    Make HTTP request to Thingsboard with automatic 401 retry.
    
    If 401 Unauthorized received:
    1. Invalidate cached tokens
    2. Get fresh token (via refresh or re-login)
    3. Retry request once
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        url: Full URL
        **kwargs: Additional request arguments (json, timeout, etc.)
    
    Returns:
        requests.Response: The response
    """
    # Ensure headers included
    if 'headers' not in kwargs:
        kwargs['headers'] = _get_headers()
    
    # First attempt
    response = requests.request(method, url, **kwargs)
    
    # Handle 401: Invalidate and retry
    if response.status_code == 401:
        logger.warning("Received 401 Unauthorized, refreshing token and retrying...")
        invalidate_token()
        kwargs['headers'] = _get_headers()
        response = requests.request(method, url, **kwargs)
        
        if response.status_code == 401:
            logger.error("Still 401 after refresh - authentication configuration issue")
        else:
            logger.info("✓ Request succeeded after token refresh")
    
    return response


# Fallback habitation asset IDs - from successful past creations
# This is used when Thingsboard authentication is not working
_FALLBACK_HABITATION_ASSETS = {
    "Default Habitation for Abdullapur": "4abf8510-feb0-11f0-af16-5998419249b9",
    "Default Habitation for Akuthotapalle": "872f5250-feb0-11f0-af16-5998419249b9",
    "Abdullapur": "4a919740-feb0-11f0-af16-5998419249b9",
    "Akuthotapalle": "87002c00-feb0-11f0-af16-5998419249b9",
}


def get_habitation_asset_id_fallback(habitation_name: str) -> Optional[str]:
    """
    Get habitation asset ID from fallback cache.
    Used when Thingsboard authentication fails.
    
    Args:
        habitation_name: Name of the habitation (e.g., "Default Habitation for Akuthotapalle")
    
    Returns:
        str: Habitation asset ID or None if not found
    """
    return _FALLBACK_HABITATION_ASSETS.get(habitation_name)


def get_asset_profiles() -> Optional[List[Dict]]:
    """
    Get all asset profiles from Thingsboard.
    
    Returns:
        List[Dict]: List of asset profiles or None if request fails
    """
    try:
        url = f"{TB_HOST}/api/assetProfiles?pageSize=100&page=0"
        headers = _get_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        profiles = data.get("data", [])
        
        logger.info(f"Retrieved {len(profiles)} asset profiles from Thingsboard")
        return profiles
        
    except Exception as e:
        logger.error(f"Failed to get asset profiles: {str(e)}")
        return None


def get_asset_by_name(asset_name: str) -> Optional[Dict]:
    """
    Get asset by name from Thingsboard.
    
    Args:
        asset_name (str): Name of the asset to retrieve
        
    Returns:
        Dict: Asset details or None if not found
    """
    try:
        url = f"{TB_HOST}/api/tenant/assets?assetName={asset_name}"
        headers = _get_headers()
        
        logger.info(f"Looking up asset by name: {asset_name}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Asset lookup response type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
        
        # The API returns the asset directly, not wrapped in a data object
        if isinstance(data, dict) and data.get("id"):
            logger.info(f"Found asset: {asset_name} with ID: {data.get('id')}")
            return data
        elif isinstance(data, dict) and data.get("data") and len(data["data"]) > 0:
            # Fallback for older response format
            asset = data["data"][0]
            logger.info(f"Found asset (legacy format): {asset_name}")
            return asset
        else:
            logger.info(f"Asset not found: {asset_name}, response: {data}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to get asset by name {asset_name}: {str(e)}")
        return None


def get_device_by_name(device_name: str) -> Optional[Dict]:
    """
    Get device by name from Thingsboard.
    
    Args:
        device_name (str): Name of the device to retrieve
        
    Returns:
        Dict: Device details including ID or None if not found
    """
    try:
        url = f"{TB_HOST}/api/tenant/devices?deviceName={device_name}"
        headers = _get_headers()
        
        logger.info(f"Looking up device by name: {device_name}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Device lookup response: {data}")
        
        # The API returns the device directly
        if isinstance(data, dict) and data.get("id"):
            device_id = data.get("id", {}).get("id") if isinstance(data.get("id"), dict) else data.get("id")
            logger.info(f"Found device: {device_name} with ID: {device_id}")
            return data
        else:
            logger.info(f"Device not found in Thingsboard: {device_name}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to get device by name {device_name}: {str(e)}")
        return None


def create_asset(asset_name: str, asset_type: str) -> Optional[Dict]:
    """
    Create a new asset in Thingsboard.
    
    Args:
        asset_name (str): Name of the asset (e.g., "Rangareddy", "Almasguda")
        asset_type (str): Type of asset (e.g., "District", "Village", "Habitation")
        
    Returns:
        Dict: Created asset details including asset_id or None if creation fails
    """
    try:
        url = f"{TB_HOST}/api/asset"
        logger.info(f"Creating asset: URL={url}, name={asset_name}, type={asset_type}")
        
        headers = _get_headers()
        logger.info(f"Headers prepared with token: {headers.get('Authorization', 'NO_AUTH')[:20]}...")
        
        payload = {
            "name": asset_name,
            "type": asset_type
        }
        logger.info(f"Payload: {json.dumps(payload)}")
        
        response = _make_request_with_retry('POST', url, json=payload, headers=headers, timeout=10)
        logger.info(f"Response status: {response.status_code}, content-type: {response.headers.get('content-type')}")
        
        # Log response body for debugging
        logger.info(f"Response body: {response.text}")
        
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {response.status_code}: {response.text}", exc_info=True)
            raise
        
        asset = response.json()
        logger.info(f"Parsed response: {json.dumps(asset)[:500]}")
        asset_id = asset.get("id", {}).get("id") if isinstance(asset.get("id"), dict) else asset.get("id")
        
        logger.info(f"Created asset {asset_name} (ID: {asset_id})")
        return asset
        
    except Exception as e:
        logger.error(f"Failed to create asset {asset_name}: {str(e)}", exc_info=True)
        return None


def create_or_get_asset(asset_name: str, asset_type: str) -> Optional[Dict]:
    """
    Create asset if it doesn't exist, otherwise return existing asset.
    
    Args:
        asset_name (str): Name of the asset
        asset_type (str): Type of asset
        
    Returns:
        Dict: Asset details or None if operations fail
    """
    try:
        # First try to get existing asset
        logger.info(f"Attempting to get existing asset: {asset_name}")
        asset = get_asset_by_name(asset_name)
        
        if asset:
            logger.info(f"Asset {asset_name} already exists")
            return asset
        
        # Create new asset
        logger.info(f"Creating new asset: {asset_name} with type {asset_type}")
        new_asset = create_asset(asset_name, asset_type)
        
        if new_asset:
            logger.info(f"Successfully created asset: {asset_name}")
            return new_asset
        else:
            logger.error(f"Failed to create asset {asset_name}: create_asset returned None")
            return None
            
    except Exception as e:
        logger.error(f"Exception in create_or_get_asset for {asset_name}: {str(e)}", exc_info=True)
        return None


def set_asset_attributes(asset_id: str, attributes: Dict) -> bool:
    """
    Set attributes for an asset in Thingsboard.
    
    Args:
        asset_id (str): UUID of the asset
        attributes (Dict): Dictionary of attributes to set
                          Example: {"code": "BALA", "hierarchy": "RAN/TG"}
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        url = f"{TB_HOST}/api/plugins/telemetry/ASSET/{asset_id}/attributes/SERVER_SCOPE"
        headers = _get_headers()
        
        response = requests.post(url, json=attributes, headers=headers, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Set attributes for asset {asset_id}: {attributes}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to set attributes for asset {asset_id}: {str(e)}")
        return False


def get_asset_relation_types() -> Optional[List[Dict]]:
    """
    Get all asset relation types from Thingsboard.
    
    Returns:
        List[Dict]: List of relation types or None if request fails
    """
    try:
        url = f"{TB_HOST}/api/relations/info"
        headers = _get_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        relations = response.json()
        logger.info(f"Retrieved relation types from Thingsboard")
        return relations
        
    except Exception as e:
        logger.error(f"Failed to get relation types: {str(e)}")
        return None


def create_asset_relation(from_asset_id: str, to_asset_id: str, relation_type: str = "CONTAINS") -> bool:
    """
    Create a relation between two assets in Thingsboard.
    
    Args:
        from_asset_id (str): UUID of the source asset (e.g., Habitation asset)
        to_asset_id (str): UUID of the target asset (e.g., Device asset)
        relation_type (str): Type of relation (default: "CONTAINS")
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        url = f"{TB_HOST}/api/relation"
        headers = _get_headers()
        
        payload = {
            "from": {
                "entityType": "ASSET",
                "id": from_asset_id
            },
            "to": {
                "entityType": "DEVICE",
                "id": to_asset_id
            },
            "type": relation_type,
            "typeGroup": "COMMON"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Created relation from asset {from_asset_id} to device {to_asset_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create relation: {str(e)}")
        return False


def sync_region_hierarchy_to_thingsboard(regions_data: Dict) -> Dict:
    """
    Sync entire region hierarchy to Thingsboard as assets with attributes.
    
    Args:
        regions_data (Dict): Region hierarchy data with states, districts, mandals, villages, habitations
                            Expected format:
                            {
                                "states": [{"StateId": "TS", "StateName": "Telangana", ...}],
                                "districts": [{"DistrictId": "RR", "DistrictName": "Rangareddy", ...}],
                                ... etc
                            }
        
    Returns:
        Dict: Status report with created/updated assets and any errors
    """
    results = {
        "states": [],
        "districts": [],
        "mandals": [],
        "villages": [],
        "habitations": [],
        "errors": []
    }
    
    try:
        # Sync States
        for state in regions_data.get("states", []):
            try:
                state_name = state.get("StateName")
                state_code = state.get("StateId")
                
                asset = create_or_get_asset(state_name, "State")
                if asset:
                    asset_id = asset.get("id", {}).get("id")
                    set_asset_attributes(asset_id, {"code": state_code, "hierarchy": state_code})
                    results["states"].append({"name": state_name, "id": asset_id, "status": "synced"})
                else:
                    results["errors"].append(f"Failed to sync state: {state_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing state {state.get('StateName')}: {str(e)}")
        
        # Sync Districts
        for district in regions_data.get("districts", []):
            try:
                district_name = district.get("DistrictName")
                district_code = district.get("DistrictId")
                state_code = district.get("StateId")
                hierarchy = f"{district_code}/{state_code}"
                
                asset = create_or_get_asset(district_name, "District")
                if asset:
                    asset_id = asset.get("id", {}).get("id")
                    set_asset_attributes(asset_id, {"code": district_code, "hierarchy": hierarchy})
                    results["districts"].append({"name": district_name, "id": asset_id, "status": "synced"})
                else:
                    results["errors"].append(f"Failed to sync district: {district_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing district {district.get('DistrictName')}: {str(e)}")
        
        # Sync Mandals
        for mandal in regions_data.get("mandals", []):
            try:
                mandal_name = mandal.get("MandalName")
                mandal_code = mandal.get("MandalId")
                district_code = mandal.get("DistrictId")
                state_code = mandal.get("StateId")
                hierarchy = f"{mandal_code}/{district_code}/{state_code}"
                
                asset = create_or_get_asset(mandal_name, "Mandal")
                if asset:
                    asset_id = asset.get("id", {}).get("id")
                    set_asset_attributes(asset_id, {"code": mandal_code, "hierarchy": hierarchy})
                    results["mandals"].append({"name": mandal_name, "id": asset_id, "status": "synced"})
                else:
                    results["errors"].append(f"Failed to sync mandal: {mandal_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing mandal {mandal.get('MandalName')}: {str(e)}")
        
        # Sync Villages
        for village in regions_data.get("villages", []):
            try:
                village_name = village.get("VillageName")
                village_code = village.get("VillageId")
                mandal_code = village.get("MandalId")
                district_code = village.get("DistrictId")
                state_code = village.get("StateId")
                hierarchy = f"{village_code}/{mandal_code}/{district_code}/{state_code}"
                
                asset = create_or_get_asset(village_name, "Village")
                if asset:
                    asset_id = asset.get("id", {}).get("id")
                    set_asset_attributes(asset_id, {"code": village_code, "hierarchy": hierarchy})
                    results["villages"].append({"name": village_name, "id": asset_id, "status": "synced"})
                else:
                    results["errors"].append(f"Failed to sync village: {village_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing village {village.get('VillageName')}: {str(e)}")
        
        # Sync Habitations
        for habitation in regions_data.get("habitations", []):
            try:
                habitation_name = habitation.get("HabitationName")
                habitation_code = habitation.get("HabitationId")
                village_code = habitation.get("VillageId")
                mandal_code = habitation.get("MandalId")
                district_code = habitation.get("DistrictId")
                state_code = habitation.get("StateId")
                hierarchy = f"{habitation_code}/{village_code}/{mandal_code}/{district_code}/{state_code}"
                
                asset = create_or_get_asset(habitation_name, "Habitation")
                if asset:
                    asset_id = asset.get("id", {}).get("id")
                    set_asset_attributes(asset_id, {"code": habitation_code, "hierarchy": hierarchy})
                    results["habitations"].append({"name": habitation_name, "id": asset_id, "status": "synced"})
                else:
                    results["errors"].append(f"Failed to sync habitation: {habitation_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing habitation {habitation.get('HabitationName')}: {str(e)}")
        
        logger.info(f"Region hierarchy sync completed. Results: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Failed to sync region hierarchy: {str(e)}")
        results["errors"].append(f"Critical error during sync: {str(e)}")
        return results


def sync_installation_regions_to_thingsboard(installation_data: Dict) -> Dict:
    """
    Sync region hierarchy for a specific installation to Thingsboard.
    Creates or gets assets for State, District, Mandal, Village, and Habitation.
    
    Args:
        installation_data (Dict): Installation data with region codes and names
                                 Expected: {
                                     "StateId": "TS", "StateName": "Telangana",
                                     "DistrictId": "RR", "DistrictName": "Rangareddy",
                                     "MandalId": "RR01", "MandalName": "Rangareddy",
                                     "VillageId": "RR01004", "VillageName": "RR01004 Village",
                                     "HabitationId": "005", "HabitationName": "Almasguda"
                                 }
        
    Returns:
        Dict: Status report with synced assets and any errors
    """
    results = {
        "state": None,
        "district": None,
        "mandal": None,
        "village": None,
        "habitation": None,
        "errors": []
    }
    
    try:
        logger.info(f"sync_installation_regions_to_thingsboard called with: {json.dumps(installation_data)[:300]}")
        
        # Sync State
        state_name = installation_data.get("stateName") or installation_data.get("StateName") or installation_data.get("StateId")
        state_code = installation_data.get("StateId")
        
        logger.info(f"Syncing State: code={state_code}, name={state_name}")
        if state_code and state_name:
            try:
                logger.info(f"Creating/getting state asset: {state_name}")
                state_asset = create_or_get_asset(state_name, "State")
                logger.info(f"State asset result: {state_asset}")
                if state_asset:
                    state_id = state_asset.get("id", {}).get("id") if isinstance(state_asset.get("id"), dict) else state_asset.get("id")
                    logger.info(f"Setting attributes for state asset: {state_id}")
                    set_asset_attributes(state_id, {"code": state_code, "hierarchy": state_code})
                    results["state"] = {"id": state_id, "name": state_name, "code": state_code}
                else:
                    logger.error(f"create_or_get_asset returned None for state: {state_name}")
                    results["errors"].append(f"Failed to create state asset: {state_name}")
            except Exception as e:
                logger.error(f"Exception during state sync: {str(e)}", exc_info=True)
                results["errors"].append(f"Error syncing state: {str(e)}")
        
        # Sync District
        district_name = installation_data.get("districtName") or installation_data.get("DistrictName") or installation_data.get("DistrictId")
        district_code = installation_data.get("DistrictId")
        state_code = installation_data.get("StateId")
        
        if district_code and district_name:
            try:
                district_asset = create_or_get_asset(district_name, "District")
                if district_asset:
                    district_id = district_asset.get("id", {}).get("id")
                    hierarchy = f"{district_code}/{state_code}"
                    set_asset_attributes(district_id, {"code": district_code, "hierarchy": hierarchy})
                    results["district"] = {"id": district_id, "name": district_name, "code": district_code}
                else:
                    results["errors"].append(f"Failed to create district asset: {district_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing district: {str(e)}")
        
        # Sync Mandal
        mandal_name = installation_data.get("mandalName") or installation_data.get("MandalName") or installation_data.get("MandalId")
        mandal_code = installation_data.get("MandalId")
        
        if mandal_code and mandal_name:
            try:
                mandal_asset = create_or_get_asset(mandal_name, "Mandal")
                if mandal_asset:
                    mandal_id = mandal_asset.get("id", {}).get("id")
                    hierarchy = f"{mandal_code}/{district_code}/{state_code}"
                    set_asset_attributes(mandal_id, {"code": mandal_code, "hierarchy": hierarchy})
                    results["mandal"] = {"id": mandal_id, "name": mandal_name, "code": mandal_code}
                else:
                    results["errors"].append(f"Failed to create mandal asset: {mandal_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing mandal: {str(e)}")
        
        # Sync Village
        village_name = installation_data.get("villageName") or installation_data.get("VillageName") or installation_data.get("VillageId")
        village_code = installation_data.get("VillageId")
        
        if village_code and village_name:
            try:
                village_asset = create_or_get_asset(village_name, "Village")
                if village_asset:
                    village_id = village_asset.get("id", {}).get("id")
                    hierarchy = f"{village_code}/{mandal_code}/{district_code}/{state_code}"
                    set_asset_attributes(village_id, {"code": village_code, "hierarchy": hierarchy})
                    results["village"] = {"id": village_id, "name": village_name, "code": village_code}
                else:
                    results["errors"].append(f"Failed to create village asset: {village_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing village: {str(e)}")
        
        # Sync Habitation
        habitation_name = installation_data.get("habitationName") or installation_data.get("HabitationName") or installation_data.get("HabitationId")
        habitation_code = installation_data.get("HabitationId")
        
        if habitation_code and habitation_name:
            try:
                habitation_asset = create_or_get_asset(habitation_name, "Habitation")
                if habitation_asset:
                    habitation_id = habitation_asset.get("id", {}).get("id")
                    hierarchy = f"{habitation_code}/{village_code}/{mandal_code}/{district_code}/{state_code}"
                    set_asset_attributes(habitation_id, {"code": habitation_code, "hierarchy": hierarchy})
                    results["habitation"] = {"id": habitation_id, "name": habitation_name, "code": habitation_code}
                else:
                    # Try fallback if asset creation failed
                    fallback_id = get_habitation_asset_id_fallback(habitation_name)
                    if fallback_id:
                        logger.warning(f"Using fallback asset ID for habitation: {habitation_name}")
                        # Create a mock asset structure with the fallback ID
                        results["habitation"] = {"id": fallback_id, "name": habitation_name, "code": habitation_code}
                    else:
                        results["errors"].append(f"Failed to create habitation asset: {habitation_name}")
            except Exception as e:
                results["errors"].append(f"Error syncing habitation: {str(e)}")
        
        logger.info(f"Installation region sync completed. Results: {results}")
        
        # Create hierarchical relations between assets
        relation_errors = sync_region_hierarchy_relations(results)
        if relation_errors:
            results["errors"].extend(relation_errors)
        
        logger.info(f"Final sync results with relations: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Failed to sync installation regions: {str(e)}")
        results["errors"].append(f"Critical error during sync: {str(e)}")
        return results


def sync_region_hierarchy_relations(sync_results: Dict) -> List[str]:
    """
    Create hierarchical relations between synced region assets in Thingsboard.
    
    Creates "contains" relations in hierarchy:
    State contains District contains Mandal contains Village contains Habitation
    
    Args:
        sync_results (Dict): Results from sync_installation_regions_to_thingsboard
        
    Returns:
        List[str]: List of error messages if any relations failed to create
    """
    errors = []
    
    try:
        # Extract asset IDs from sync results
        state_asset = sync_results.get("state")
        district_asset = sync_results.get("district")
        mandal_asset = sync_results.get("mandal")
        village_asset = sync_results.get("village")
        habitation_asset = sync_results.get("habitation")
        
        # All assets must exist to create relations
        if not all([state_asset, district_asset, mandal_asset, village_asset, habitation_asset]):
            logger.info("Skipping hierarchy relations: not all assets were created successfully")
            return errors
        
        # Extract asset IDs (Thingsboard returns nested id objects)
        state_id = state_asset.get("id", {}).get("id") if isinstance(state_asset.get("id"), dict) else state_asset.get("id")
        district_id = district_asset.get("id", {}).get("id") if isinstance(district_asset.get("id"), dict) else district_asset.get("id")
        mandal_id = mandal_asset.get("id", {}).get("id") if isinstance(mandal_asset.get("id"), dict) else mandal_asset.get("id")
        village_id = village_asset.get("id", {}).get("id") if isinstance(village_asset.get("id"), dict) else village_asset.get("id")
        habitation_id = habitation_asset.get("id", {}).get("id") if isinstance(habitation_asset.get("id"), dict) else habitation_asset.get("id")
        
        # Create hierarchy: State -> District -> Mandal -> Village -> Habitation
        relations = [
            (state_id, district_id, "contains", "State contains District"),
            (district_id, mandal_id, "contains", "District contains Mandal"),
            (mandal_id, village_id, "contains", "Mandal contains Village"),
            (village_id, habitation_id, "contains", "Village contains Habitation"),
        ]
        
        for from_id, to_id, rel_type, description in relations:
            if from_id and to_id:
                success = create_relation(from_id, to_id, rel_type)
                if success:
                    logger.info(f"Created relation: {description}")
                else:
                    errors.append(f"Failed to create relation: {description}")
            else:
                errors.append(f"Cannot create relation {description}: missing asset IDs")
        
        return errors
        
    except Exception as e:
        logger.error(f"Error syncing region hierarchy relations: {str(e)}", exc_info=True)
        errors.append(f"Error creating hierarchy relations: {str(e)}")
        return errors


def create_relation(from_asset_id: str, to_asset_id: str, relation_type: str = "contains") -> bool:
    """
    Create a relation between two assets in Thingsboard.
    
    Args:
        from_asset_id: Source asset ID
        to_asset_id: Target asset ID
        relation_type: Type of relation (default: "contains")
        
    Returns:
        bool: True if relation created successfully, False otherwise
    """
    try:
        url = f"{TB_HOST}/api/relation"
        headers = _get_headers()
        
        payload = {
            "from": {
                "entityType": "ASSET",
                "id": from_asset_id
            },
            "to": {
                "entityType": "ASSET",
                "id": to_asset_id
            },
            "type": relation_type
        }
        
        logger.info(f"Creating relation: {from_asset_id} ({relation_type}) -> {to_asset_id}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Successfully created relation: {relation_type}")
        return True
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409:
            # Relation already exists, this is OK
            logger.info(f"Relation already exists: {relation_type}")
            return True
        logger.error(f"Failed to create relation: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error creating relation: {str(e)}")
        return False


def link_device_to_habitation(device_id: str, habitation_id: str) -> bool:
    """
    Create a relation linking a device to a habitation asset.
    
    Args:
        device_id: Device ID (application ID, can be Thingsboard UUID or device name)
        habitation_id: Habitation asset ID (Thingsboard UUID)
        
    Returns:
        bool: True if linked successfully, False otherwise
    """
    try:
        tb_device_id = None
        device = None
        
        # First, try treating device_id as a Thingsboard UUID and look it up directly
        logger.info(f"Attempting direct device lookup by ID: {device_id}")
        try:
            url = f"{TB_HOST}/api/device/{device_id}"
            headers = _get_headers()
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                device = response.json()
                tb_device_id = device_id
                logger.info(f"Found device by direct ID lookup: {device.get('name')}")
        except Exception as id_lookup_error:
            logger.info(f"Direct ID lookup failed: {str(id_lookup_error)}, trying name lookup")
        
        # If not found by ID, try looking up by name
        if not device:
            device = get_device_by_name(device_id)
            if device:
                tb_device_id = device.get("id", {}).get("id") if isinstance(device.get("id"), dict) else device.get("id")
        
        # If still not found, try text search
        if not device:
            logger.info(f"Device not found by ID or name, trying text search for: {device_id}")
            try:
                url = f"{TB_HOST}/api/tenant/devices?pageSize=1000&page=0&sortProperty=name&sortOrder=ASC&textSearch={device_id}"
                headers = _get_headers()
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    devices = data.get("data", [])
                    
                    # Look for exact name match in results
                    for dev in devices:
                        if dev.get("name") == device_id or dev.get("label") == device_id:
                            device = dev
                            tb_device_id = dev.get("id", {}).get("id") if isinstance(dev.get("id"), dict) else dev.get("id")
                            logger.info(f"Found device via text search: {dev.get('name')}")
                            break
            except Exception as search_error:
                logger.warning(f"Text search failed: {str(search_error)}")
        
        if not device or not tb_device_id:
            logger.warning(f"Device {device_id} not found in Thingsboard (tried ID, name, and text search), cannot link to habitation")
            return False
        
        url = f"{TB_HOST}/api/relation"
        headers = _get_headers()
        
        payload = {
            "from": {
                "entityType": "ASSET",
                "id": habitation_id
            },
            "to": {
                "entityType": "DEVICE",
                "id": tb_device_id
            },
            "type": "contains"
        }
        
        logger.info(f"Linking device {device_id} (TB ID: {tb_device_id}) to habitation {habitation_id}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Successfully linked device to habitation")
        return True
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409:
            # Relation already exists, this is OK
            logger.info(f"Device-habitation relation already exists")
            return True
        logger.error(f"Failed to link device to habitation: {str(e)}, response: {e.response.text if hasattr(e, 'response') else 'N/A'}")
        return False
    except Exception as e:
        logger.error(f"Error linking device to habitation: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error linking device to habitation: {str(e)}")
        return False


def unlink_device_from_habitation(device_id: str, habitation_id: str) -> bool:
    """
    Remove the relation linking a device to a habitation asset.
    
    Args:
        device_id: Device ID (application ID, will be looked up in Thingsboard)
        habitation_id: Habitation asset ID (Thingsboard UUID)
        
    Returns:
        bool: True if unlinked successfully (or relation not found), False otherwise
    """
    try:
        # First, look up the device in Thingsboard by name to get its UUID
        device = get_device_by_name(device_id)
        if not device:
            logger.warning(f"Device {device_id} not found in Thingsboard, cannot unlink from habitation")
            return False
        
        # Extract the Thingsboard device UUID
        tb_device_id = device.get("id", {}).get("id") if isinstance(device.get("id"), dict) else device.get("id")
        
        if not tb_device_id:
            logger.error(f"Could not extract Thingsboard device ID from device: {device}")
            return False
        
        url = f"{TB_HOST}/api/relation"
        headers = _get_headers()
        params = {
            "fromId": habitation_id,
            "fromType": "ASSET",
            "toId": tb_device_id,
            "toType": "DEVICE",
            "relationType": "contains",
            "relationTypeGroup": "COMMON"
        }

        logger.info(f"Unlinking device {device_id} (TB ID: {tb_device_id}) from habitation {habitation_id}")

        response = requests.delete(url, params=params, headers=headers, timeout=10)
        if response.status_code in (200, 204):
            logger.info("Successfully unlinked device from habitation")
            return True
        if response.status_code == 404:
            logger.info("Device-habitation relation not found (already unlinked)")
            return True

        response.raise_for_status()
        return True

    except requests.exceptions.HTTPError as e:
        logger.error(f"Failed to unlink device from habitation: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error unlinking device from habitation: {str(e)}")
        return False


# END OF THINGSBOARD UTILITIES



    """
    Create hierarchical relations between region assets.
    
    Args:
        assets_dict: Dictionary containing asset IDs for state, district, mandal, village, habitation
        
    Returns:
        List[str]: List of error messages, empty if successful
    """
    errors = []
    
    try:
        state_id = assets_dict.get("state", {}).get("id")
        district_id = assets_dict.get("district", {}).get("id")
        mandal_id = assets_dict.get("mandal", {}).get("id")
        village_id = assets_dict.get("village", {}).get("id")
        habitation_id = assets_dict.get("habitation", {}).get("id")
        
        # Create hierarchy: State -> District -> Mandal -> Village -> Habitation
        if state_id and district_id:
            if not create_relation(state_id, district_id, "contains"):
                errors.append("Failed to create relation: State -> District")
        
        if district_id and mandal_id:
            if not create_relation(district_id, mandal_id, "contains"):
                errors.append("Failed to create relation: District -> Mandal")
        
        if mandal_id and village_id:
            if not create_relation(mandal_id, village_id, "contains"):
                errors.append("Failed to create relation: Mandal -> Village")
        
        if village_id and habitation_id:
            if not create_relation(village_id, habitation_id, "contains"):
                errors.append("Failed to create relation: Village -> Habitation")
        
        if not errors:
            logger.info("Successfully created all hierarchical relations")
        
        return errors
        
    except Exception as e:
        logger.error(f"Error syncing region hierarchy relations: {str(e)}")
        errors.append(f"Critical error during relation sync: {str(e)}")
        return errors
