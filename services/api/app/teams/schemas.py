from datetime import datetime
from pydantic import BaseModel


class TeamCreate(BaseModel):
    name: str
    slug: str


class TeamUpdate(BaseModel):
    name: str | None = None


class TeamMemberAdd(BaseModel):
    user_id: str
    role: str = "member"


class TeamMemberRead(BaseModel):
    id: str
    user_id: str
    user_email: str = ""
    user_display_name: str = ""
    role: str
    created_at: datetime | None = None


class TeamRead(BaseModel):
    id: str
    org_id: str
    name: str
    slug: str
    created_at: datetime | None = None
    members: list[TeamMemberRead] = []


class TeamListResponse(BaseModel):
    items: list[TeamRead]
    total: int
