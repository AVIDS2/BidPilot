# Data Model

## Modeling strategy

The data model is designed around project execution, not around prompts or agent traces. AI artifacts are attached to durable business objects.

## Core entities

### Project

Represents one working engagement.

Fields:

- `id`
- `slug`
- `name`
- `scenario_package`
- `status`
- `created_at`
- `updated_at`

### Bundle

Logical upload batch within a project.

Fields:

- `id`
- `project_id`
- `label`
- `source_type`
- `ingest_status`
- `created_at`

### SourceDocument

Original file or imported source.

Fields:

- `id`
- `bundle_id`
- `storage_key`
- `mime_type`
- `checksum`
- `original_filename`
- `page_count`
- `parse_status`

### ParsedAsset

Normalized output from parsing.

Fields:

- `id`
- `source_document_id`
- `parser_name`
- `parser_version`
- `content_json`
- `layout_json`
- `created_at`

### KnowledgeChunk

Retrieval unit stored for search and ranking.

Fields:

- `id`
- `project_id`
- `source_document_id`
- `chunk_index`
- `content`
- `metadata_json`
- `embedding`

### RequirementItem

Structured requirement extracted from source materials.

Fields:

- `id`
- `project_id`
- `section_key`
- `requirement_text`
- `priority`
- `status`

### Evidence

Source-backed citation record.

Fields:

- `id`
- `project_id`
- `source_document_id`
- `chunk_id`
- `quote_text`
- `locator_json`
- `confidence`

### Deliverable

Logical output artifact.

Fields:

- `id`
- `project_id`
- `type`
- `title`
- `status`
- `current_version_id`

### DeliverableSection

Section-level unit for drafting and review.

Fields:

- `id`
- `deliverable_id`
- `section_key`
- `title`
- `status`
- `assignee_type`

### SectionVersion

Immutable section snapshot.

Fields:

- `id`
- `deliverable_section_id`
- `version_number`
- `content_json`
- `content_markdown`
- `created_by_actor`
- `generation_run_id`

### ExecutionRun

One run of an execution graph.

Fields:

- `id`
- `project_id`
- `run_type`
- `status`
- `input_json`
- `output_json`
- `started_at`
- `finished_at`

### ReviewThread

Human review conversation and decision object.

Fields:

- `id`
- `deliverable_section_id`
- `status`
- `opened_by`
- `resolved_by`

### AuditEvent

Immutable event for security and traceability.

Fields:

- `id`
- `project_id`
- `actor_type`
- `actor_id`
- `event_type`
- `payload_json`
- `created_at`

## Storage rules

- raw files never live in the database
- business truth never lives only in an execution trace
- generated content is versioned immutably
- audit events are append-only
- provider metadata is stored in JSON payloads, not promoted into first-class schema unless stable

## Indexing priorities

- `project_id`
- `deliverable_id`
- `deliverable_section_id`
- `status`
- `created_at`
- vector index on `knowledge_chunk.embedding`

## Deletion policy

- user-facing deletes are soft deletes by default
- audit events are never hard deleted from operational history without an explicit retention process
