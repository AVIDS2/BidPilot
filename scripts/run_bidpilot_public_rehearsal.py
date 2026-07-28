"""Run the P0-D7 public-material rehearsal through the real local BidPilot stack."""

from __future__ import annotations

from pathlib import Path

from run_bidpilot_golden_path import REPOSITORY_ROOT, RunnerDefaults, main as run_golden_path


PUBLIC_REHEARSAL_DEFAULTS = RunnerDefaults(
    description="Run the local BidPilot P0-D7 public-material rehearsal.",
    evidence_kind="bidpilot_p0_d7_public_rehearsal",
    run_prefix="p0d7",
    output_file=Path("tmp") / "p0-d7-public-rehearsal.json",
    material_dir=REPOSITORY_ROOT / "tmp" / "p0-d7-public-rehearsal",
    material_manifest=REPOSITORY_ROOT / "sample-data" / "bidpilot-public-rehearsal" / "manifest.json",
    material_origin="public_historical_procurement",
    material_label="P0-D7 public historical procurement materials",
    project_name_prefix="P0-D7 Public Procurement Rehearsal",
    actor_label="P0-D7 Public Rehearsal",
)


if __name__ == "__main__":
    raise SystemExit(run_golden_path(defaults=PUBLIC_REHEARSAL_DEFAULTS))
