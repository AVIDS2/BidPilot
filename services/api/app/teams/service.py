from sqlalchemy.orm import Session

from app.models import Organization, Team, TeamMember, User


def create_team_command(db: Session, org_id: str, name: str, slug: str) -> Team:
    existing = db.query(Team).filter_by(org_id=org_id, slug=slug).first()
    if existing is not None:
        raise ValueError("A team with this slug already exists in your organization")
    team = Team(org_id=org_id, name=name, slug=slug)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def list_teams_query(db: Session, org_id: str) -> list[Team]:
    return db.query(Team).filter_by(org_id=org_id).order_by(Team.name).all()


def get_team_by_id(db: Session, team_id: str) -> Team | None:
    return db.get(Team, team_id)


def update_team_command(db: Session, team_id: str, name: str | None) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    if name is not None:
        team.name = name
    db.commit()
    db.refresh(team)
    return team


def delete_team_command(db: Session, team_id: str) -> None:
    team = db.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    db.delete(team)
    db.commit()


def add_team_member_command(db: Session, team_id: str, user_id: str, role: str = "member") -> TeamMember:
    team = db.get(Team, team_id)
    if team is None:
        raise ValueError("Team not found")
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    existing = db.query(TeamMember).filter_by(team_id=team_id, user_id=user_id).first()
    if existing is not None:
        raise ValueError("User is already a member of this team")
    member = TeamMember(team_id=team_id, user_id=user_id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_team_member_command(db: Session, team_id: str, user_id: str) -> None:
    member = db.query(TeamMember).filter_by(team_id=team_id, user_id=user_id).first()
    if member is None:
        raise ValueError("Team member not found")
    db.delete(member)
    db.commit()


def list_team_members_query(db: Session, team_id: str) -> list[TeamMember]:
    return db.query(TeamMember).filter_by(team_id=team_id).all()
