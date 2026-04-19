# Repository Blueprint

## Goal

Show the intended repository structure once implementation is underway.

This is the structural target, not a requirement that every folder exists immediately.

## Top-level target

```text
docpilot/
  apps/
    web/
  services/
    api/
    worker/
  packages/
    contracts/
  scripts/
  docs/
```

## Frontend target

```text
apps/web/
  src/
    app/
    routes/
    features/
    components/
    lib/
    styles/
    test/
  .storybook/
```

## API target

```text
services/api/
  app/
    core/
    db/
    projects/
    bundles/
    documents/
    requirements/
    retrieval/
    execution/
    deliverables/
    review/
    audit/
    auth/
    providers/
  tests/
  alembic/
```

## Worker target

```text
services/worker/
  app/
    tasks/
    execution/
    adapters/
    services/
  tests/
```

## Contracts target

```text
packages/contracts/
  src/
    api/
    events/
    ids/
    enums/
```

## Rules

- do not create folders only for hypothetical future abstractions
- prefer feature- or domain-oriented grouping over generic utility sprawl
- keep shared code truly shared; otherwise leave it in the owning feature
- when in doubt, align new files to this blueprint and the corresponding application architecture docs
