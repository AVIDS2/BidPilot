"""Worker view of the shared persistence models.

The API and worker share one database schema. Re-exporting the contracts
module wholesale avoids a stale hand-maintained subset when a scheduled task
starts using a newly introduced domain model.
"""

from contracts.models import *  # noqa: F403
