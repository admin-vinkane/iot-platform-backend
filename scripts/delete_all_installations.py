#!/usr/bin/env python3
"""
Script to delete all installations with cascade=true option.
This will remove installations and all their associations (devices, contacts).
"""

import requests
import sys
import time
from typing import List, Dict, Any

# Configuration
API_BASE_URL = "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev"

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def print_header():
    """Print script header."""
    print("=" * 60)
    print("  DELETE ALL INSTALLATIONS (CASCADE)")
    print("=" * 60)
    print()


def get_all_installations() -> List[Dict[str, Any]]:
    """Fetch all installations from the API."""
    try:
        response = requests.get(f"{API_BASE_URL}/installs", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Handle both array and nested object formats
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'installs' in data:
            return data['installs']
        else:
            return []
    except requests.RequestException as e:
        print(f"{RED}Error fetching installations: {e}{NC}")
        sys.exit(1)


def delete_installation(install_id: str, deleted_by: str) -> tuple[bool, str, int]:
    """
    Delete a single installation with cascade.
    
    Returns:
        tuple: (success, message, total_deleted)
    """
    try:
        url = f"{API_BASE_URL}/installs/{install_id}"
        params = {
            "cascade": "true",
            "deletedBy": deleted_by
        }
        
        response = requests.delete(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            total_deleted = data.get("totalDeleted", "N/A")
            return True, f"Success ({total_deleted} records)", total_deleted
        else:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("error") or error_data.get("message") or "Unknown error"
            return False, f"{error_msg} (HTTP {response.status_code})", 0
            
    except requests.RequestException as e:
        return False, f"Request failed: {str(e)}", 0


def main():
    """Main execution function."""
    print_header()
    
    # Get deleted_by parameter
    deleted_by = sys.argv[1] if len(sys.argv) > 1 else "admin"
    
    print(f"{YELLOW}WARNING: This will delete ALL installations and their associations!{NC}")
    print(f"{YELLOW}Deleted by: {deleted_by}{NC}")
    print()
    
    confirmation = input("Are you sure you want to continue? (type 'YES' to confirm): ")
    if confirmation != "YES":
        print(f"{RED}Operation cancelled.{NC}")
        sys.exit(0)
    
    print()
    print("Fetching all installations...")
    
    # Get all installations
    installations = get_all_installations()
    
    if not installations:
        print(f"{YELLOW}No installations found.{NC}")
        sys.exit(0)
    
    total_count = len(installations)
    print(f"{GREEN}Found {total_count} installation(s) to delete{NC}")
    print()
    
    # Initialize counters
    success_count = 0
    fail_count = 0
    total_records_deleted = 0
    
    # Loop through each installation
    for idx, install in enumerate(installations, 1):
        install_id = install.get("InstallationId") or install.get("installationId")
        
        if not install_id:
            print(f"{RED}✗ Skipping installation without ID{NC}")
            fail_count += 1
            continue
        
        print(f"[{idx}/{total_count}] Deleting installation: {install_id}")
        
        # Delete with cascade
        success, message, deleted_count = delete_installation(install_id, deleted_by)
        
        if success:
            print(f"{GREEN}✓ {install_id}: {message}{NC}")
            success_count += 1
            if isinstance(deleted_count, int):
                total_records_deleted += deleted_count
        else:
            print(f"{RED}✗ {install_id}: {message}{NC}")
            fail_count += 1
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    # Print summary
    print()
    print("=" * 60)
    print("  DELETION SUMMARY")
    print("=" * 60)
    print(f"Total installations: {total_count}")
    print(f"{GREEN}Successfully deleted: {success_count}{NC}")
    print(f"{RED}Failed: {fail_count}{NC}")
    print(f"{BLUE}Total database records deleted: {total_records_deleted}{NC}")
    print()
    
    if fail_count == 0:
        print(f"{GREEN}All installations deleted successfully!{NC}")
        sys.exit(0)
    else:
        print(f"{YELLOW}Some deletions failed. Check the output above for details.{NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
