"""Run the role-aware RFP-to-evidence acceptance rehearsal locally.

This uses the checked-in synthetic material pack only.  P0-D7 separately
proves that the same governed workflow can process pinned public procurement
documents without committing those source bytes to the repository.
"""

from __future__ import annotations

from pathlib import Path

from run_bidpilot_golden_path import REPOSITORY_ROOT, RunnerDefaults, main as run_golden_path


HYBRID_REHEARSAL_DEFAULTS = RunnerDefaults(
    description="Run the local BidPilot role-aware RFP and supplier-evidence rehearsal.",
    evidence_kind="bidpilot_p0_d8_role_aware_rehearsal",
    run_prefix="p0d8",
    output_file=Path("tmp") / "p0-d8-role-aware-rehearsal.json",
    material_dir=REPOSITORY_ROOT / "sample-data" / "bidpilot-demo",
    material_manifest=REPOSITORY_ROOT / "sample-data" / "bidpilot-demo" / "manifest.json",
    material_origin="synthetic_checked_in_pack",
    material_label="P0-D8 role-aware synthetic bid materials",
    project_name_prefix="P0-D8 Role-Aware Bid Rehearsal",
    actor_label="P0-D8 Role-Aware Rehearsal",
    bundle_mode="role_aware",
    verify_requirement_evidence=True,
    section_key="past-performance",
)


if __name__ == "__main__":
    raise SystemExit(run_golden_path(defaults=HYBRID_REHEARSAL_DEFAULTS))
