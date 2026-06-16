from fastapi import APIRouter, status

from api.deps.auth import CurrentUser
from modules.auth import RetriFlowAuthService
from schemas.auth import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthRegisterRequest,
    AuthUserItem,
)


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _service() -> RetriFlowAuthService:
    return RetriFlowAuthService()


@router.post("/register", response_model=AuthUserItem, status_code=status.HTTP_201_CREATED)
def register(request: AuthRegisterRequest) -> AuthUserItem:
    return _service().register(request)


@router.post("/login", response_model=AuthLoginResponse)
def login(request: AuthLoginRequest) -> AuthLoginResponse:
    return _service().login(request)


@router.get("/me", response_model=AuthUserItem)
def current_user(user: CurrentUser) -> AuthUserItem:
    return AuthUserItem(id=user.id, username=user.username, role=user.role)
