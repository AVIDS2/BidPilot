from pydantic import BaseModel


class InvitationCreate(BaseModel):
    email: str


class InvitationRead(BaseModel):
    id: str
    org_id: str
    email: str
    status: str
    created_at: str | None = None
