"""Nostra Health auth — JWT verification."""

import jwt
from fastapi import HTTPException
from tova_core.providers.auth import BaseAuth


class NostraAuth(BaseAuth):
    """Verifies custom JWTs signed by the Nostra Node.js backend."""

    def __init__(self, jwt_secret: str):
        self.secret = jwt_secret

    async def verify_token(self, token: str) -> str:
        if not self.secret:
            raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
        try:
            decoded = jwt.decode(token, self.secret, algorithms=["HS256"])
            return decoded["userId"]
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
