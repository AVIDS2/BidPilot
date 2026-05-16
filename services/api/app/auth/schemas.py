from pydantic import BaseModel


class UserRegister(BaseModel):
    email: str
    display_name: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


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


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
