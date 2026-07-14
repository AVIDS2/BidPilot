import json
from pathlib import Path

from contracts import BidBenchDataset


REPO_ROOT = Path(__file__).resolve().parents[4]
DATASET_DIR = REPO_ROOT / "benchmarks" / "bidbench" / "v1" / "demo-smart-community"


def test_demo_dataset_is_valid_and_all_sources_exist() -> None:
    payload = json.loads((DATASET_DIR / "dataset.json").read_text(encoding="utf-8"))
    dataset = BidBenchDataset.model_validate(payload)

    assert dataset.dataset_role == "development"
    assert dataset.origin_type == "synthetic"
    assert len(dataset.requirements) == 44
    assert sum(requirement.is_mandatory for requirement in dataset.requirements) >= 15
    assert sum(requirement.requirement_type == "scored" for requirement in dataset.requirements) == 12

    for source in dataset.sources:
        assert (DATASET_DIR / source.path).is_file(), source.path
