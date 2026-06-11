from pydantic import BaseModel


class AuthRegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthUserItem(BaseModel):
    id: str
    username: str
    role: str


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserItem
