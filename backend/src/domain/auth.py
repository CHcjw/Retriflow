from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from core.config import get_settings
from core.state import get_connection
from schemas.auth import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthRegisterRequest,
    AuthUserItem,
)


@dataclass
class AuthenticatedUser:
    id: str
    username: str
    role: str


class RetriFlowAuthService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def register(self, request: AuthRegisterRequest) -> AuthUserItem:
        username = request.username.strip()
        password = request.password.strip()
        role = request.role.strip() or "user"

        if len(username) < 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username too short")
        if len(password) < 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password too short")

        with get_connection() as connection:
            existing = connection.execute(
                """
                select id
                from users
                where username = ?
                limit 1
                """,
                (username,),
            ).fetchone()
            if existing is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")

            user_id = f"user-{uuid.uuid4().hex[:12]}"
            connection.execute(
                """
                insert into users (id, username, password_hash, role)
                values (?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    self._hash_password(password),
                    role,
                ),
            )
            connection.commit()

        return AuthUserItem(id=user_id, username=username, role=role)

    def login(self, request: AuthLoginRequest) -> AuthLoginResponse:
        username = request.username.strip()
        password = request.password.strip()

        with get_connection() as connection:
            row = connection.execute(
                """
                select id, username, password_hash, role
                from users
                where username = ?
                limit 1
                """,
                (username,),
            ).fetchone()

        if row is None or not self._verify_password(password, str(row["password_hash"])):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")

        user = AuthUserItem(
            id=str(row["id"]),
            username=str(row["username"]),
            role=str(row["role"]),
        )
        return AuthLoginResponse(
            access_token=self._create_access_token(user),
            user=user,
        )

    def get_current_user(self, token: str) -> AuthenticatedUser:
        payload = self._decode_access_token(token)
        user_id = str(payload.get("sub", "")).strip()
        username = str(payload.get("username", "")).strip()
        role = str(payload.get("role", "user")).strip() or "user"
        if not user_id or not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

        with get_connection() as connection:
            row = connection.execute(
                """
                select id, username, role
                from users
                where id = ?
                limit 1
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")

        return AuthenticatedUser(
            id=str(row["id"]),
            username=str(row["username"]),
            role=str(row["role"]),
        )

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
        return f"{salt}${digest}"

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        try:
            salt, expected = password_hash.split("$", 1)
        except ValueError:
            return False
        actual = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
        return hmac.compare_digest(actual, expected)

    def _create_access_token(self, user: AuthUserItem) -> str:
        expires_at = datetime.now(UTC) + timedelta(hours=max(1, self.settings.auth_access_token_ttl_hours))
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "exp": int(expires_at.timestamp()),
        }
        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_json).decode("ascii").rstrip("=")
        signature = hmac.new(
            self.settings.auth_secret_key.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        return f"{payload_b64}.{signature_b64}"

    def _decode_access_token(self, token: str) -> dict[str, object]:
        try:
            payload_b64, signature_b64 = token.split(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc

        expected_signature = hmac.new(
            self.settings.auth_secret_key.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_signature = base64.urlsafe_b64decode(self._restore_b64_padding(signature_b64))
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

        payload_json = base64.urlsafe_b64decode(self._restore_b64_padding(payload_b64)).decode("utf-8")
        payload = json.loads(payload_json)
        exp = int(payload.get("exp", 0))
        if exp <= int(datetime.now(UTC).timestamp()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired")
        return payload

    @staticmethod
    def _restore_b64_padding(value: str) -> str:
        return value + "=" * (-len(value) % 4)
