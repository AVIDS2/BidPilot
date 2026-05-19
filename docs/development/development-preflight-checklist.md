# Development Preflight Checklist

## Goal

Give implementation agents a short checklist to run before meaningful work.

## Checklist

- [ ] shell is `powershell`
- [ ] Python environment is `conda activate llm`
- [ ] current phase has been identified from `docs/development/current-execution-state.md`
- [ ] current phase plan has been opened
- [ ] Docker is available if infrastructure is needed
- [ ] `docpilot-postgres` is running on `localhost:5433` if database work is involved
- [ ] local provider base URL and models are loaded from `docs/development/local-environment-baseline.md`
- [ ] no undocumented stack substitution is being introduced
- [ ] the next task belongs to the active phase

## Stop conditions

Stop and report instead of improvising when:

- Docker is unavailable but the task requires documented Docker services
- the conda environment cannot be activated
- the required service cannot be started inside the documented project stack
- a foundational choice appears to conflict with the docs

## Working rule

Passing this checklist is required before large implementation changes or environment surgery.
