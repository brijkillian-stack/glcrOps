"""Phase 1: Example protected routes"""

from fastapi import APIRouter, Depends
from .auth import get_current_user_with_role, UserRole

router = APIRouter(prefix="/protected", tags=["Phase 1 - Auth"])

@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user_with_role)):
    """Get current user profile (requires authentication)"""
    return current_user

@router.get("/admin-only")
async def admin_only(current_user: dict = Depends(get_current_user_with_role)):
    """Example: Only Admin and Sudo Admin can access"""
    if current_user["role"] not in [UserRole.ADMIN, UserRole.SUDO_ADMIN]:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return {"message": "Welcome, admin!", "user": current_user}