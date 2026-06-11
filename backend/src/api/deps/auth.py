from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from domain.auth import AuthenticatedUser, RetriFlowAuthService


def _auth_service() -> RetriFlowAuthService:
    return RetriFlowAuthService()


def require_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return _auth_service().get_current_user(token)


CurrentUser = Annotated[AuthenticatedUser, Depends(require_current_user)]


def require_admin_user(user: CurrentUser) -> AuthenticatedUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin access required")
    return user


AdminUser = Annotated[AuthenticatedUser, Depends(require_admin_user)]
