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
