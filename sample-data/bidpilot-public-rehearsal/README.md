# BidPilot Public Rehearsal Pack

This pack is a reproducible engineering rehearsal based on publicly accessible
historical procurement documents. It is intentionally not a customer demo pack
and not a representation of any live solicitation.

## What is tracked

Only the source manifest is committed:

- publisher and public source URL
- historical publication date when available
- expected byte length and SHA-256 checksum
- role, retrieval checks, and expected text anchors

The raw PDF files are downloaded into the ignored `tmp/` directory. This keeps
third-party source bytes, public contact details, and changed upstream content
out of Git history.

## Fetch and verify

From the repository root:

```powershell
uv run --directory services/api --locked --no-sync python ../../scripts/fetch_bidpilot_public_rehearsal.py
```

The downloader verifies HTTPS, file size, PDF signature, and the pinned
SHA-256 hash. It fails closed when a publisher changes a file. Review that
change before intentionally updating the manifest.

## Run the rehearsal

With the local API, Worker, PostgreSQL, Redis, and MinIO stack running:

```powershell
$env:DOCPILOT_DATABASE_URL = "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot"
uv run --directory services/api --locked --no-sync python ../../scripts/run_bidpilot_public_rehearsal.py
```

The run creates an isolated local user, organization, and project. It uploads
the fetched PDFs through the normal API, waits for Worker parsing and indexing,
checks retrieval locators, runs the LangGraph drafting workflow, exercises
reject/redraft/approve, validates DOCX export, and then tests the public retry
path with controlled local fault injection.

The redacted evidence artifact is written under `tmp/` and contains IDs,
hashes, counts, and statuses only. It never records source body text,
credentials, JWTs, or model responses.

## Boundary

The documents include historical public procurement content and may include
outdated terms, contact details, or requirements. They are valid only as a
parser, retrieval, citation, and governed-workflow rehearsal. They must never
be used as legal, procurement, commercial, or supplier-capability advice.
