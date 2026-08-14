from pydantic import BaseModel


class UserRegister(BaseModel):
    email: str
    display_name: str
    password: str
    invitation_token: str | None = None
    org_name: str | None = None
    org_slug: str | None = None
    turnstile_token: str | None = None


class UserLogin(BaseModel):
    email: str
    password: str
    turnstile_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    plan: str = "starter"
    email_verified: bool = False
    disabled: bool = False
    org_id: str = ""
    org_slug: str = ""
    # Present only on registration. True means the provider accepted the
    # verification email, not that the recipient has already received it.
    verification_email_accepted: bool | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    current_password: str | None = None
    new_password: str | None = None


class SubscriptionRead(BaseModel):
    plan: str
    status: str
    stripe_customer_id: str | None = None


class SubscriptionUpdate(BaseModel):
    user_id: str
    plan: str


class UsersPaginatedResponse(BaseModel):
    items: list[CurrentUser]
    total: int
    page: int
    page_size: int
    pages: int


class PasswordResetRequest(BaseModel):
    email: str
    turnstile_token: str | None = None


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
