# ADR 0002: Scenario Package Model

- Status: Superseded in part by ADR 0003
- Date: 2026-04-18

## Decision

Scenario variation must be introduced through package metadata, templates, and execution configuration without replacing the core project, review, evidence, and deliverable models.

## Context

DocPilot needs to support multiple document workflows (bid response, contract review, delivery acceptance) without duplicating control-plane logic. Each scenario differs in:
- Default section structure
- Requirement extraction keywords
- Drafting system prompts
- Export naming conventions

## Model

A `ScenarioPackage` dataclass in `services/api/app/scenarios/registry.py` defines:
- `key`: unique identifier (e.g., "bidpilot", "contractpilot")
- `label`: display name
- `description`: short purpose
- `default_sections`: list of section keys auto-created on project creation
- `requirement_keywords`: domain-specific words for pattern-based requirement extraction
- `drafting_system_prompt`: LLM system prompt for section drafting
- `export_filename_pattern`: naming template for exports

## Rules

1. **Scenario-specific DB tables**: This original prohibition is superseded by ADR 0003. Mature vertical concepts may use explicit extension tables while the shared control plane remains reusable.
2. **Core models are shared**: Project, Bundle, Deliverable, Section, Evidence, Review, Audit are scenario-agnostic.
3. **Scenario variation is adapter-level**: The drafting adapter, requirement extractor, and template resolver accept scenario parameters but use the same control-plane tables.
4. **Adding a scenario = adding a registry entry**: No code changes outside `registry.py` are required to add a new scenario.

## Consequences

- Adding a new scenario (e.g., "deliverypilot") requires only a new `ScenarioPackage` entry.
- The project creation flow auto-creates deliverable + sections from the scenario template.
- Drafting and requirement extraction are scenario-aware through injected parameters.
- The control plane remains stable across all scenarios.
