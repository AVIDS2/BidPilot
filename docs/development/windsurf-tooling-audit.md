# Windsurf Tooling Audit

## Scope

This document records the current Windsurf customization state for the DocPilot workspace and whether each item is actually usable.

## Current rules and agents instructions

### Global rule

- `C:\Users\Lenovo\.windsurf\rules\memorix.md`
- Purpose: global Memorix memory behavior
- Status: present

### Workspace rule

- `.windsurf/rules/docpilot-core.md`
- Purpose: keep DocPilot work grounded in docs, Playwright verification, and stack constraints
- Status: present and valid

### Workspace AGENTS

- `AGENTS.md`
- Purpose: repo-wide stack and architecture instructions
- Status: present and valid

## Current skills

### Global custom skill

- `C:\Users\Lenovo\.codeium\windsurf\skills\ui-ux-pro-max`
- Status: repaired locally after reinstall
- Root cause found: the Windows/Windsurf install had written `scripts` and `data` as plain text pointer files instead of real directories
- Current state: `scripts/search.py` and the data tables are present again, so the skill is no longer missing its script payload

### Global custom skill

- `C:\Users\Lenovo\.codeium\windsurf\skills\tui-design`
- Status: structurally present with `SKILL.md` and reference files
- Confidence: likely available; not functionally smoke-tested in this audit

### Workspace skill

- `.windsurf/skills/docpilot-dev`
- Status: present and valid
- Purpose: project-specific implementation guidance

### Official shadcn skill

- `.agents/skills/shadcn`
- `.windsurf/skills/shadcn` -> junction to `.agents/skills/shadcn`
- Status: installed successfully and discoverable by Windsurf
- Purpose: official shadcn/ui guidance and registry workflow

## Current MCPs

MCP config file:

- `C:\Users\Lenovo\.codeium\windsurf\mcp_config.json`

### context7

- Status: enabled
- Alignment: aligned in shape with the official remote HTTP setup
- Notes: currently uses a hardcoded API key in config; should move to env or file interpolation later

### mcp-playwright

- Status: enabled
- Alignment: aligned with official standard config
- Verification: package resolution succeeded

### memorix

- Status: enabled
- Alignment: project-specific local MCP setup, not a third-party official public server
- Verification: config present

### shadcn

- Status: enabled
- Alignment: aligned with official `npx shadcn@latest mcp` setup
- Verification: package resolution succeeded

### postgres-docpilot

- Status: enabled
- Alignment: aligned with official PostgreSQL MCP reference server style
- Verification:
  - Docker container is healthy
  - host port `5433` is reachable
  - database accepts queries
  - `vector` extension created

### github

- Status: enabled
- Alignment: not aligned with the current official GitHub MCP recommendation
- Reason: current config uses `@modelcontextprotocol/server-github`, while GitHub now recommends the official `github/github-mcp-server` remote or local server
- Recommendation: migrate later, do not change blindly during unrelated work

### linear

- Status: disabled
- Alignment: not audited in depth

### tavily

- Status: enabled
- Alignment: not audited in depth
- Notes: currently uses a hardcoded API key in config; should move to env or file interpolation later

## Docker-backed database status

### Container

- Name: `docpilot-postgres`
- Image: `pgvector/pgvector:pg17`
- Host port: `5433`
- Database: `docpilot`
- User: `docpilot`

### Verification summary

- container started successfully
- health check is healthy
- query `select current_database(), current_user` succeeded
- `create extension if not exists vector` succeeded

## Recommended next cleanup

1. restart Windsurf so the updated MCP config is reloaded
2. confirm `postgres-docpilot` shows healthy in the MCP panel
3. move hardcoded `Context7`, `GitHub`, and `Tavily` secrets to env or file interpolation
4. later migrate `github` MCP to the official GitHub MCP server
5. if `ui-ux-pro-max` still errors after restart, verify whether Windsurf requires a `python3` command alias on Windows in addition to the restored script files
