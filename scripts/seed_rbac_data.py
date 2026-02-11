#!/usr/bin/env python3
"""
RBAC Data Seeding Script
Seeds roles, permissions, role-permission mappings, and components from permissions.json
"""

import json
import requests
import sys
from typing import Dict, List

# API Configuration
API_BASE_URL = "https://103wz10k37.execute-api.ap-south-2.amazonaws.com/dev/users"
PERMISSIONS_JSON_PATH = "permissions.json"

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(text: str):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def load_permissions_config() -> Dict:
    """Load permissions.json file"""
    try:
        with open(PERMISSIONS_JSON_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print_error(f"File not found: {PERMISSIONS_JSON_PATH}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in {PERMISSIONS_JSON_PATH}: {str(e)}")
        sys.exit(1)


def get_role_id_by_name(role_name: str) -> str:
    """Fetch roleId for a roleName via API list endpoint"""
    url = f"{API_BASE_URL}/permissions/roles"

    try:
        response = requests.get(url)
        if response.status_code != 200:
            return ""

        items = response.json().get("data", [])
        for item in items:
            if item.get("roleName") == role_name:
                return item.get("roleId", "")
    except Exception:
        return ""

    return ""


def get_permission_id_by_name(permission_name: str) -> str:
    """Fetch permissionId for a permissionName via API list endpoint"""
    url = f"{API_BASE_URL}/permissions"

    try:
        response = requests.get(url)
        if response.status_code != 200:
            return ""

        items = response.json().get("data", [])
        for item in items:
            if item.get("permissionName") == permission_name:
                return item.get("permissionId", "")
    except Exception:
        return ""

    return ""


def create_permission(permission_name: str, permission_data: Dict) -> str:
    """Create a single permission via API"""
    url = f"{API_BASE_URL}/permissions"
    
    payload = {
        "permissionName": permission_name,
        "displayName": permission_data.get("displayName"),
        "description": permission_data.get("description"),
        "resource": permission_data.get("resource"),
        "action": permission_data.get("action"),
        "category": permission_data.get("category")
    }
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 201:
            permission_id = response.json().get("data", {}).get("permissionId")
            print_success(f"Created permission: {permission_name}")
            return permission_id
        elif response.status_code == 409:
            print_warning(f"Permission already exists: {permission_name}")
            return get_permission_id_by_name(permission_name)
        else:
            print_error(f"Failed to create permission {permission_name}: {response.text}")
            return ""
            
    except Exception as e:
        print_error(f"Error creating permission {permission_name}: {str(e)}")
        return ""


def create_role(role_name: str, role_data: Dict) -> str:
    """Create a single role via API"""
    url = f"{API_BASE_URL}/permissions/roles"
    
    payload = {
        "roleName": role_name,
        "displayName": role_data.get("displayName"),
        "description": role_data.get("description"),
        "level": role_data.get("level", 10),
        "isSystem": role_data.get("isSystem", False)
    }
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 201:
            role_id = response.json().get("data", {}).get("roleId")
            print_success(f"Created role: {role_name}")
            return role_id
        elif response.status_code == 409:
            print_warning(f"Role already exists: {role_name}")
            return get_role_id_by_name(role_name)
        else:
            print_error(f"Failed to create role {role_name}: {response.text}")
            return ""
            
    except Exception as e:
        print_error(f"Error creating role {role_name}: {str(e)}")
        return ""


def assign_permission_to_role(role_id: str, permission_id: str) -> bool:
    """Assign a permission to a role via API"""
    url = f"{API_BASE_URL}/permissions/roles/{role_id}/permissions"
    
    payload = {
        "permissionId": permission_id
    }
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 201:
            return True
        elif response.status_code == 409:
            return True  # Already assigned
        else:
            print_error(f"Failed to assign {permission_id} to {role_id}: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Error assigning {permission_id} to {role_id}: {str(e)}")
        return False


def create_component(component_name: str, component_data: Dict) -> bool:
    """Create a UI component via API"""
    url = f"{API_BASE_URL}/permissions/components"
    
    payload = {
        "componentName": component_name,
        "path": component_data.get("path"),
        "icon": component_data.get("icon"),
        "order": component_data.get("order", 0),
        "category": component_data.get("category"),
        "requiredPermissions": component_data.get("requiredPermissions", []),
        "optionalPermissions": component_data.get("optionalPermissions", [])
    }
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 201:
            print_success(f"Created component: {component_name}")
            return True
        elif response.status_code == 409:
            print_warning(f"Component already exists: {component_name}")
            return True
        else:
            print_error(f"Failed to create component {component_name}: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Error creating component {component_name}: {str(e)}")
        return False


def seed_permissions(permissions: Dict) -> tuple:
    """Seed all permissions"""
    print_header("SEEDING PERMISSIONS")
    
    success_count = 0
    fail_count = 0
    permission_id_map = {}
    
    for perm_name, perm_data in permissions.items():
        permission_id = create_permission(perm_name, perm_data)
        if permission_id:
            permission_id_map[perm_name] = permission_id
            success_count += 1
        else:
            fail_count += 1
    
    print_info(f"\nPermissions: {success_count} succeeded, {fail_count} failed")
    return success_count, fail_count, permission_id_map


def seed_roles(roles: Dict) -> tuple:
    """Seed all roles"""
    print_header("SEEDING ROLES")
    
    success_count = 0
    fail_count = 0
    role_id_map = {}
    
    for role_name, role_data in roles.items():
        role_id = create_role(role_name, role_data)
        if role_id:
            role_id_map[role_name] = role_id
            success_count += 1
        else:
            fail_count += 1
    
    print_info(f"\nRoles: {success_count} succeeded, {fail_count} failed")
    return success_count, fail_count, role_id_map


def seed_role_permissions(roles: Dict, permissions: Dict, role_id_map: Dict, permission_id_map: Dict) -> tuple:
    """Seed role-permission assignments"""
    print_header("SEEDING ROLE-PERMISSION ASSIGNMENTS")
    
    success_count = 0
    fail_count = 0
    
    for role_name, role_data in roles.items():
        role_id = role_id_map.get(role_name)
        if not role_id:
            print_warning(f"Skipping role permissions for '{role_name}' (missing roleId)")
            fail_count += len(role_data.get("permissions", []))
            continue
        role_permissions = role_data.get("permissions", [])
        
        # Handle wildcard permission (admin)
        if "*" in role_permissions:
            print_info(f"Role '{role_name}' has wildcard permissions (*) - assigning all")
            role_permissions = list(permissions.keys())
        
        print_info(f"\nAssigning {len(role_permissions)} permissions to role '{role_name}'...")
        
        for perm_name in role_permissions:
            permission_id = permission_id_map.get(perm_name)
            if not permission_id:
                print_warning(f"Skipping permission '{perm_name}' (missing permissionId)")
                fail_count += 1
                continue
            if assign_permission_to_role(role_id, permission_id):
                success_count += 1
            else:
                fail_count += 1
    
    print_info(f"\nRole-Permission assignments: {success_count} succeeded, {fail_count} failed")
    return success_count, fail_count


def seed_components(components: Dict) -> tuple:
    """Seed UI components"""
    print_header("SEEDING UI COMPONENTS")
    
    success_count = 0
    fail_count = 0
    
    for comp_name, comp_data in components.items():
        if create_component(comp_name, comp_data):
            success_count += 1
        else:
            fail_count += 1
    
    print_info(f"\nComponents: {success_count} succeeded, {fail_count} failed")
    return success_count, fail_count


def assign_roles_to_users(user_assignments: List[Dict], role_id_map: Dict) -> tuple:
    """Assign roles to specific users"""
    print_header("ASSIGNING ROLES TO USERS")
    
    success_count = 0
    fail_count = 0
    
    for assignment in user_assignments:
        user_id = assignment.get("userId")
        role_name = assignment.get("roleName")
        role_id = role_id_map.get(role_name)
        if not role_id:
            print_warning(f"Skipping assignment for '{user_id}' (missing roleId for '{role_name}')")
            fail_count += 1
            continue
        
        url = f"{API_BASE_URL}/permissions/users/{user_id}/roles"
        payload = {
            "userId": user_id,
            "roleId": role_id,
            "assignedBy": "system"
        }
        
        try:
            response = requests.post(url, json=payload)
            
            if response.status_code == 201:
                print_success(f"Assigned role '{role_name}' to user '{user_id}'")
                success_count += 1
            elif response.status_code == 409:
                print_warning(f"Role '{role_name}' already assigned to user '{user_id}'")
                success_count += 1
            else:
                print_error(f"Failed to assign role to {user_id}: {response.text}")
                fail_count += 1
                
        except Exception as e:
            print_error(f"Error assigning role to {user_id}: {str(e)}")
            fail_count += 1
    
    print_info(f"\nUser-Role assignments: {success_count} succeeded, {fail_count} failed")
    return success_count, fail_count


def main():
    """Main seeding orchestrator"""
    print_header("RBAC DATA SEEDING SCRIPT")
    print_info(f"API Base URL: {API_BASE_URL}")
    print_info(f"Permissions File: {PERMISSIONS_JSON_PATH}")
    
    # Load permissions configuration
    print_info("\nLoading permissions configuration...")
    config = load_permissions_config()
    
    print_success(f"Loaded configuration:")
    print_info(f"  - {len(config.get('permissions', {}))} permissions")
    print_info(f"  - {len(config.get('roles', {}))} roles")
    print_info(f"  - {len(config.get('components', {}))} components")
    
    # Seed data in order
    total_success = 0
    total_fail = 0
    
    # 1. Seed permissions (must come first)
    perm_success, perm_fail, permission_id_map = seed_permissions(config.get("permissions", {}))
    total_success += perm_success
    total_fail += perm_fail
    
    # 2. Seed roles
    role_success, role_fail, role_id_map = seed_roles(config.get("roles", {}))
    total_success += role_success
    total_fail += role_fail
    
    # 3. Seed role-permission assignments
    rp_success, rp_fail = seed_role_permissions(
        config.get("roles", {}),
        config.get("permissions", {}),
        role_id_map,
        permission_id_map
    )
    total_success += rp_success
    total_fail += rp_fail
    
    # 4. Seed UI components
    comp_success, comp_fail = seed_components(config.get("components", {}))
    total_success += comp_success
    total_fail += comp_fail
    
    # 5. Assign roles to specific users (example assignments)
    # Assign admin role to admin@vinkane.com
    user_assignments = [
        {"userId": "admin@vinkane.com", "roleName": "admin"},
        {"userId": "nagendrantn@gmail.com", "roleName": "device_manager"}
    ]
    
    user_success, user_fail = assign_roles_to_users(user_assignments, role_id_map)
    total_success += user_success
    total_fail += user_fail
    
    # Final summary
    print_header("SEEDING COMPLETE")
    
    if total_fail == 0:
        print_success(f"✅ All operations succeeded! ({total_success} total)")
    else:
        print_warning(f"⚠️  {total_success} succeeded, {total_fail} failed")
    
    print_info("\nYou can now:")
    print_info("  1. View roles: GET /permissions/roles")
    print_info("  2. View permissions: GET /permissions")
    print_info("  3. View user roles: GET /permissions/users/{userId}/roles")
    print_info("  4. View user permissions: GET /permissions/users/{userId}/permissions")
    
    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
