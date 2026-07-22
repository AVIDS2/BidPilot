from typing import Literal

from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str
    slug: str


class OrganizationRead(BaseModel):
    id: str
    slug: str
    name: str


class OrganizationSwitchRequest(BaseModel):
    org_id: str


class OrganizationMemberRead(BaseModel):
    id: str
    display_name: str
    email: str
    role: Literal["owner", "admin", "member"]
    is_billing_owner: bool = False


class OrganizationMemberRoleUpdate(BaseModel):
    role: Literal["owner", "admin", "member"]


class OrganizationBillingOwnerTransfer(BaseModel):
    user_id: str


class OrganizationMemberRemovalRead(BaseModel):
    user_id: str
    active_org: OrganizationRead
    personal_workspace_created: bool
