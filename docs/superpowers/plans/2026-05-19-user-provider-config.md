# User Custom API Provider Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement.

**Goal:** Allow users to configure their own AI provider API keys/endpoints (OpenAI + Anthropic) via a settings page, with per-user DB storage.

**Architecture:** 
- ProviderConfig model (user_id, provider_type, api_key, api_url, model, label, is_active)
- CRUD API at /auth/me/providers
- Worker resolves provider from DB instead of env vars
- New Anthropic/Claude adapter
- Frontend settings page

**Tech Stack:** FastAPI + SQLAlchemy + httpx + React/TypeScript + shadcn/ui

---

### Task A: Backend — ProviderConfig Model + Migration + API

**Files:**
- Modify: `services/api/app/models.py` (add ProviderConfig model)
- Create: `services/api/app/providers/schemas.py`
- Create: `services/api/app/providers/service.py`  
- Create: `services/api/app/providers/router.py`
- Modify: `services/api/app/main.py` (register router)
- Create: `services/api/alembic/versions/*_add_provider_config_table.py`

### Task B: Worker — Anthropic/Claude Adapter

**Files:**
- Create: `services/worker/app/adapters/anthropic_llm.py`
- Create: `services/worker/tests/test_anthropic_adapter.py`

### Task C: Worker — Provider Registry + Task Wiring

**Files:**
- Create: `services/worker/app/provider_registry.py`
- Modify: `services/worker/app/adapters/llm.py` (accept config params)
- Modify: `services/worker/app/adapters/embedding.py` (accept config params)
- Modify: `services/worker/app/execution/drafting.py` (resolve and pass provider)
- Modify: `services/worker/app/tasks.py` (accept provider_config_id)
- Modify: `services/api/app/drafting/service.py` (pass provider_config_id)

### Task D: Frontend — Settings Page

**Files:**
- Create: `apps/web/src/features/settings/provider-settings-page.tsx`
- Create: `apps/web/src/features/settings/provider-settings-page.test.tsx`
- Create: `apps/web/src/features/settings/components/provider-form.tsx`
- Create: `apps/web/src/features/settings/components/provider-list.tsx`
- Modify: `apps/web/src/lib/api.ts` (add provider API functions)
- Modify: `apps/web/src/app.tsx` (add route)

### Task E: Integration Verification

- Run all tests
- Test connection with real API key
- Update known-limitations.md
- Commit
