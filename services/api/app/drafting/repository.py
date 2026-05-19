from sqlalchemy.orm import Session

from app.models import ExecutionRun


def create_run(db: Session, run: ExecutionRun) -> ExecutionRun:
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
