# Governed Memory Scope Hardening

## Finding

The project-scoped default memory listing did not restrict its shared query to
`project_shared`. A project-private `user_private` record could therefore be
returned to another project member when they used the default project Wiki
view, despite the explicit product contract that personal preferences are
owner-only.

## Fix

- `list_memory_records` now accepts an SQL `scope` filter.
- The default project query makes two separate reads: active project-shared
  records and the caller's own active project-private records.
- Scoped private reads stay owner-filtered, and unscoped private reads continue
  to exclude project-bound preferences with source locators.
- A regression test proves a project viewer receives an empty default listing
  when another member is the only owner of project-private memory.

## Verification

- `tests/memory/test_commands.py` plus `tests/assistant/test_memory_tools.py`:
  `12 passed` on a temporary isolated SQLite `_test` database.
- Memory Ruff check passed.
- `test_context_pack.py` requires PostgreSQL `pgvector` and PostgreSQL FTS;
  its three retrieval assertions cannot execute against SQLite and still need a
  configured migrated `docpilot_test` PostgreSQL database for this session's
  full verification.

## Follow-up

The Knowledge Portfolio Index is now delivered at `/knowledge`.

- It aggregates only project-shared health from authorized, non-deleted
  projects and deep-links back to the project Bid Wiki.
- The Assistant and LangGraph Operator share a read-only
  `list_knowledge_portfolio` capability. It returns only safe aggregate
  metadata and never constructs a cross-project context pack.
- Opening the portfolio through the Assistant is allowlisted at `/knowledge`.

Focused capability regression passed without a database fixture: five
Assistant/Operator assertions plus eleven registry-policy assertions, with
Ruff and diff checks clean. A full fixture-backed PostgreSQL run in this local
session stalled before reporting a test result; it is not counted as passed and
should be diagnosed separately before release evidence is updated.
