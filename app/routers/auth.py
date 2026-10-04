from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, DbSession, TokenPayload
from app.core.errors import AppError, error_responses, unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.models import RevokedToken, User, utcnow
from app.schemas.auth import RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


def _email_taken() -> AppError:
    return AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")


@router.post(
    "/register",
    status_code=201,
    response_model=UserOut,
    summary="Create an account",
    description="Creates a consumer or merchant account. (In production, merchants would be onboarded separately.)",
    responses=error_responses(409, 422),
)
def register(body: RegisterIn, db: DbSession) -> User:
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise _email_taken()
    user = User(email=email, hashed_password=hash_password(body.password), role=body.role, created_at=utcnow())
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _email_taken()
    return user


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Log in and get a JWT",
    description="OAuth2 password form: put the email in `username`. Used by Swagger's **Authorize** button.",
    responses=error_responses(401, 422),
)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> TokenOut:
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not verify_password(form.password, user.hashed_password):
        raise unauthorized("INVALID_CREDENTIALS", "Incorrect email or password.")
    token, expires_in = create_access_token(user.id, user.role.value)
    return TokenOut(access_token=token, expires_in=expires_in, role=user.role)


@router.post(
    "/logout",
    status_code=204,
    summary="Revoke the current token",
    description="Adds the token's `jti` to the denylist, so it is rejected from now on even before it expires.",
    responses=error_responses(401),
)
def logout(payload: TokenPayload, db: DbSession) -> Response:
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    db.add(RevokedToken(jti=payload["jti"], expires_at=expires_at))
    db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserOut, summary="Current user", responses=error_responses(401))
def me(user: CurrentUser) -> User:
    return user
