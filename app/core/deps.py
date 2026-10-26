from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError, unauthorized
from app.core.security import decode_access_token
from app.database import get_db
from app.models import MerchantStatus, RevokedToken, User, UserRole

# pulls the raw token string out of the "Authorization: Bearer <token>" header at runtime
# Relative URL, so Swagger's Authorize also works when the API is served under /api behind Nginx.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

DbSession = Annotated[Session, Depends(get_db)]

# returns the decoded JWT, or raises 401.
def get_token_payload(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> dict[str, Any]:
    payload = decode_access_token(token)
    if db.get(RevokedToken, payload["jti"]) is not None:
        raise unauthorized("TOKEN_REVOKED", "Token has been revoked. Please log in again.")
    return payload


TokenPayload = Annotated[dict[str, Any], Depends(get_token_payload)]


# returns the User row, or raises 401.
def get_current_user(payload: TokenPayload, db: DbSession) -> User:
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise unauthorized("INVALID_TOKEN", "Token is invalid.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(role: UserRole):
    def checker(user: CurrentUser) -> User:
        if user.role != role:
            raise AppError(403, "FORBIDDEN_ROLE", f"This endpoint is only available to {role.value} accounts.")
        return user

    return checker


MerchantUser = Annotated[User, Depends(require_role(UserRole.merchant))]
ConsumerUser = Annotated[User, Depends(require_role(UserRole.consumer))]
AdminUser = Annotated[User, Depends(require_role(UserRole.admin))]


def require_active_merchant(merchant: MerchantUser) -> User:
    """Pending or suspended merchants can log in, but can't sell or configure financing yet."""
    if merchant.merchant_status != MerchantStatus.active:
        status = merchant.merchant_status.value if merchant.merchant_status else "missing"
        raise AppError(403, "MERCHANT_NOT_ACTIVE", f"Your merchant account is {status}. "
                                                   f"An Affirm admin must approve it first.")
    return merchant


ActiveMerchant = Annotated[User, Depends(require_active_merchant)]
