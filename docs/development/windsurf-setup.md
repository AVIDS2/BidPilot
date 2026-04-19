# Windsurf Setup for DocPilot

## Goal

Configure Windsurf for this repository with minimal, stable customization and without breaking unrelated workspaces.

## What is already configured on this machine

Global Windsurf locations currently in use:

- Global rules: `C:\Users\Lenovo\.windsurf\rules`
- Global hooks: `C:\Users\Lenovo\.windsurf\hooks.json`
- Global skills: `C:\Users\Lenovo\.codeium\windsurf\skills`
- Global MCP config: `C:\Users\Lenovo\.codeium\windsurf\mcp_config.json`

Project-level files added for this repository:

- `AGENTS.md`
- `.windsurf/rules/docpilot-core.md`
- `.windsurf/skills/docpilot-dev/SKILL.md`
- `docs/development/glm5.1-docpilot-playbook.md`

## Guidance style for this repository

The repository-level Windsurf guidance for `DocPilot` is intentionally light-touch.

- It is meant to create strong defaults, not brittle hard gates.
- It should help `glm5.1` prefer the right tools without making normal development awkward.
- If a preferred tool is unavailable, the fallback is to use source code, existing project docs, or official documentation and keep moving.

If you want the project-specific development habits in one place, start here:

- `docs/development/glm5.1-docpilot-playbook.md`

## Recommended minimum setup

### Project-level

- `AGENTS.md` for repo-wide instructions
- one always-on rule in `.windsurf/rules`
- one workspace skill in `.windsurf/skills`

### Global MCPs

- `context7`
- `mcp-playwright`
- `memorix`
- `shadcn`
- `postgres-docpilot` when a local database is available

## Why MCP is global

Windsurf currently documents MCP configuration through the global file:

- `~/.codeium/windsurf/mcp_config.json`

That means MCP is shared across workspaces, so changes should be additive and conservative.

## Safe installation workflow

1. Back up `C:\Users\Lenovo\.codeium\windsurf\mcp_config.json`
2. Add or update only the MCP entries you need
3. Restart Windsurf
4. Open Cascade and inspect the `MCPs` panel
5. Enable or disable tools per server in the UI as needed

## Current backup created

- `C:\Users\Lenovo\.codeium\windsurf\mcp_config.json.bak-20260418-163819`

## Environment variables to set

### Recommended secrets

This repository now uses a project-local secret file for the DocPilot database MCP:

- `.windsurf/secrets/docpilot_database_url.txt`

Current value:

- `postgresql://docpilot:docpilot@localhost:5433/docpilot`

### Optional environment variables

```powershell
setx CONTEXT7_API_KEY "your-context7-api-key"
setx GITHUB_PAT "your-github-personal-access-token"
setx DOCPILOT_DATABASE_URL "postgresql://docpilot:docpilot@localhost:5433/docpilot"
```

Restart Windsurf after setting environment variables.

You do not need `DOCPILOT_DATABASE_URL` for the current MCP setup unless you want to switch back to env-based interpolation.

## Optional commands

### Install the official shadcn/ui skill later

Run inside the project once your Node tooling is ready:

```powershell
pnpm dlx skills add shadcn/ui
```

If `pnpm` is unavailable:

```powershell
npx -y @antfu/ni dlx skills add shadcn/ui
```

### Initialize shadcn in the frontend later

Run this after the frontend app exists:

```powershell
npx -y shadcn@latest init
```

## MCP notes

### `context7`

- best for up-to-date library docs
- API key recommended for higher limits

### `mcp-playwright`

- best for UI verification and interaction testing
- no token needed

### `memorix`

- points to the local HTTP control plane at `http://localhost:3211/mcp`
- no extra token needed if your local Memorix service is already running

### `shadcn`

- best for browsing and installing shadcn registry components
- no token needed for the standard public shadcn registry
- private registries may require `REGISTRY_TOKEN`

### `postgres-docpilot`

- points to the Docker PostgreSQL service exposed at `localhost:5433`
- reads its connection string from `.windsurf/secrets/docpilot_database_url.txt`
- recommended to use a read-only or development database user in the future

## Windsurf UI paths

### Manage rules

- Open Cascade
- Click the `Customizations` icon
- Open `Rules`

### Manage skills

- Open Cascade
- Click the three-dot menu
- Open `Skills`

### Manage MCP

- Open Cascade
- Click `MCPs` in the top-right menu
- Or go to `Windsurf Settings > Cascade > MCP Servers`

## Troubleshooting

- If a new MCP does not appear, restart Windsurf after editing `mcp_config.json`
- If a MCP appears but has no tools, open the MCP panel and refresh it
- If `shadcn` cannot install components, make sure the target frontend project has `components.json`
- If `postgres-docpilot` fails, confirm `DOCPILOT_DATABASE_URL` is set and the database is reachable
- If `postgres-docpilot` fails, confirm Docker Postgres is running and the secret file still points to `localhost:5433`
