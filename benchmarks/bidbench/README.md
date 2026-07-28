# BidBench

BidBench is BidPilot's versioned offline evaluation corpus for requirement extraction, source localization, evidence matching, claim grounding, and bid-readiness workflows.

## Dataset Roles

- `development`: visible fixtures used while implementing and debugging.
- `regression`: frozen, diverse fixtures used for repeatable quality gates.
- `hidden`: separately controlled acceptance fixtures used to detect overfitting.

The repository currently contains development fixtures only. Results from development fixtures are not commercial accuracy claims.

## Annotation Rules

1. Annotate one independently actionable requirement per record.
2. Preserve the original source wording and add a concise normalized wording.
3. Mark a requirement mandatory only when omission or non-compliance can invalidate the response or explicitly violates a stated minimum.
4. Mark scoring criteria as `scored` and record the stated score weight.
5. Every mandatory or scored requirement needs a source locator.
6. Evidence is linked only when the source materially supports the requirement. Related marketing language is not sufficient evidence.
7. `covered` means the supplied evidence is sufficient for a credible response; `partial` means useful but incomplete; `uncovered` means the submitted sources do not support the requirement.
8. Accepted claims without evidence must be marked as inference or counted as unsupported.

## Matching Policy

Initial development scoring uses explicit ground-truth ids where available. Later semantic matching must record the matcher version, threshold, and review policy. Frozen and hidden sets require two-person review for mandatory and scored requirements.

## Safety and Provenance

Every committed dataset must declare origin and license. Private customer files must never be copied into this directory without documented anonymization and authorization.

The `demo-smart-community` dataset is entirely synthetic. Company names, customers, qualifications, staffing, delivery history, and performance figures are fictional and do not represent real credentials or contracts.

## Development Baseline

Run the four offline evaluators together with:

```powershell
uv run --directory services/api python ../../scripts/run_development_baseline.py
```

The command writes BidBench, RetrievalBench, MemoryBench, AssistantBench, and
one aggregate receipt. The receipt records the current Git commit, every
dataset fingerprint, report SHA-256, capture mode, and the total fixed-case
count. It uses only control fixtures and performs no provider call, so it is a
development diagnostic artifact, never a release-quality claim. Production
promotion still requires reviewed `regression` or `hidden` captures through
the quality-gate policy.
