from sqlalchemy.orm import Session

from app.models import Organization, User


def create_org_command(db: Session, name: str, slug: str) -> Organization:
    existing = db.query(Organization).filter_by(slug=slug).first()
    if existing is not None:
        raise ValueError("An organization with this slug already exists")
    org = Organization(name=name, slug=slug)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def list_user_orgs_query(db: Session, user_id: str) -> list[Organization]:
    """Return all orgs a user belongs to (future: support multi-org membership)."""
    user = db.get(User, user_id)
    if user is None:
        return []
    org = db.get(Organization, user.org_id)
    return [org] if org else []


def get_org_by_id(db: Session, org_id: str) -> Organization | None:
    return db.get(Organization, org_id)


def switch_user_org_command(db: Session, user_id: str, org_id: str) -> User:
    """Switch a user's active org. Validates the user can access the org."""
    org = db.get(Organization, org_id)
    if org is None:
        raise ValueError("Organization not found")
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    user.org_id = org_id
    db.commit()
    db.refresh(user)
    return user
