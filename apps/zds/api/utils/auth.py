"""Phase 1: Auth utilities and role helpers"""

from enum import Enum
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import create_client, Client

import os

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class UserRole(str, Enum):
    GRAVES_OPS_SUPER = "graves_ops_super"
    DAYS_OPS_SUPER = "days_ops_super"
    SWINGS_OPS_SUPER = "swings_ops_super"
    UTILITY_OPS_SUPER = "utility_ops_super"
    OPS_SUPER = "ops_super"
    OPS_MANAGER = "ops_manager"
    OPS_DIRECTOR = "ops_director"
    ADMIN = "admin"
    SUDO_ADMIN = "sudo_admin"

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user from Supabase JWT"""
    try:
        token = credentials.credentials
        user = supabase.auth.get_user(token)
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_with_role(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user + role from database"""
    user = await get_current_user(credentials)
    
    # Fetch role from users table
    result = supabase.table("users").select("id, full_name, role").eq("id", user.user.id).execute()
    
    if not result.data:
        raise HTTPException(status_code=403, detail="User not found in system")
    
    return {
        "id": user.user.id,
        "full_name": result.data[0]["full_name"],
        "role": result.data[0]["role"]
    }

# Role hierarchy for permission checks
def has_permission(user_role: str, required_roles: list) -> bool:
    """Check if user role has required permission"""
    if user_role == UserRole.SUDO_ADMIN:
        return True
    return user_role in required_roles