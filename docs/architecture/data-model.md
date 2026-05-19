# Data Model

## Overview

The data model is centered around durable business objects rather than prompt traces or agent execution logs. AI-generated artifacts are attached to these objects as versioned, immutable snapshots, ensuring that the system's record of truth lives in the database independent of any single inference run. The schema is designed for relational integrity first, with JSON columns reserved for semi-structured metadata that is not expected to be queried relationally.

## Entity Relationship Summary

All tables use UUID string primary keys (VARCHAR(36)). The 19 tables are grouped into six domains:

### Organization & Users
- **Organization** -- tenant root; owns projects, users, and teams
- **Team** -- named group within an organization (scoped by org_id)
- **TeamMember** -- many-to-many join between team and user, with role
- **User** -- authenticated member of an organization
- **Invitation** -- pending invitation for a user to join an organization

### Project & Content
- **Project** -- represents one working engagement (proposal, RFP response, etc.)
- **Bundle** -- logical upload batch within a project
- **SourceDocument** -- original uploaded or imported file
- **ParsedAsset** -- normalized output produced by a parser pipeline step

### Knowledge & Retrieval
- **KnowledgeChunk** -- text chunk with pgvector embedding for semantic search
- **RequirementItem** -- structured requirement extracted from source materials
- **Evidence** -- source-backed citation record linking sections to source documents

### Delivery & Review
- **Deliverable** -- logical output artifact (e.g., a proposal document)
- **DeliverableSection** -- section within a deliverable; the unit of drafting and review
- **SectionVersion** -- immutable snapshot of section content
- **ReviewThread** -- human or AI review conversation anchored to a section
- **ReviewComment** -- individual comment within a review thread

### Operations & Audit
- **ExecutionRun** -- one invocation of an execution graph (pipeline run)
- **AuditEvent** -- append-only event log for security and traceability

### Subscription & Billing
- **Subscription** -- per-user plan and Stripe integration
- **ProviderConfig** -- per-user LLM provider credentials (OpenAI, Anthropic)
- **RefreshToken** -- JWT refresh token tracking for authentication

## Table Reference

### Organization
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| slug | VARCHAR(100) | UNIQUE, NOT NULL |
| name | VARCHAR(255) | NOT NULL |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Root tenant entity. Every project, user, and team belongs to exactly one organization.

**Relationships:** one-to-many with User, Project, Team (teams cascade delete with the organization).

---

### Team
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| org_id | VARCHAR(36) | FK -> organization.id, NOT NULL |
| name | VARCHAR(255) | NOT NULL |
| slug | VARCHAR(100) | NOT NULL |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Groups users within an organization for role-based access control.

**Constraints:** Unique on (org_id, slug) to prevent duplicate team names within the same org.

**Design note:** Slug is unique per-org rather than globally, which is appropriate since teams are tenant-scoped.

---

### TeamMember
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| team_id | VARCHAR(36) | FK -> team.id, NOT NULL |
| user_id | VARCHAR(36) | FK -> user.id, NOT NULL |
| role | VARCHAR(30) | default "member" |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Join table with role for team membership.

**Constraints:** Unique on (team_id, user_id) preventing duplicate membership.

---

### User
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| org_id | VARCHAR(36) | FK -> organization.id, NOT NULL |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| display_name | VARCHAR(255) | NOT NULL |
| role | VARCHAR(30) | default "member" |
| disabled | BOOLEAN | default FALSE |
| email_verified | BOOLEAN | default FALSE |
| password_hash | VARCHAR(255) | NOT NULL |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Authenticated user account scoped to an organization. Email is globally unique for cross-org uniqueness.

**Relationships:** Each user has exactly one Subscription (uselist=False), and may have multiple ProviderConfig records. Both cascade delete with the user.

---

### Invitation
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| org_id | VARCHAR(36) | FK -> organization.id, NOT NULL |
| invited_by | VARCHAR(36) | FK -> user.id, NOT NULL |
| email | VARCHAR(255) | NOT NULL |
| token | VARCHAR(255) | UNIQUE, NOT NULL |
| status | VARCHAR(30) | default "pending" |
| expires_at | TIMESTAMP | NOT NULL |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Tracks pending user invitations to join an organization. The token is used in the registration link and is globally unique.

---

### Project
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| org_id | VARCHAR(36) | FK -> organization.id, NOT NULL |
| slug | VARCHAR(100) | UNIQUE, NOT NULL |
| name | VARCHAR(255) | NOT NULL |
| scenario_package | VARCHAR(50) | NOT NULL; which prompt/workflow template to use |
| status | VARCHAR(30) | default "active" |
| created_at | TIMESTAMP | server default now() |
| updated_at | TIMESTAMP | auto-updates on row change |

**Purpose:** Central engagement entity. Represents one proposal, RFP response, or bid. Everything below is project-scoped.

**Design note:** `scenario_package` is a string key rather than a FK to a scenario table, keeping the model simple while allowing the application layer to map it to the appropriate workflow template.

---

### Bundle
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| project_id | VARCHAR(36) | FK -> project.id, NOT NULL |
| label | VARCHAR(255) | NOT NULL |
| source_type | VARCHAR(50) | NOT NULL; e.g., "upload", "import", "scrape" |
| ingest_status | VARCHAR(30) | default "queued" |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Groups source documents that were uploaded or imported together as a batch. The `source_type` and `ingest_status` fields track ingestion pipeline progress.

---

### SourceDocument
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| bundle_id | VARCHAR(36) | FK -> bundle.id, NOT NULL |
| storage_key | VARCHAR(500) | NOT NULL; blob storage path |
| mime_type | VARCHAR(100) | NOT NULL |
| checksum | VARCHAR(64) | NOT NULL; SHA-256 hex digest |
| original_filename | VARCHAR(500) | NOT NULL |
| page_count | INTEGER | nullable |
| parse_status | VARCHAR(30) | default "pending" |

**Purpose:** Represents one raw source file. The file itself is stored in blob storage (referenced by `storage_key`); the database holds only metadata. The checksum enables deduplication and integrity verification.

---

### ParsedAsset
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| source_document_id | VARCHAR(36) | FK -> source_document.id, NOT NULL |
| parser_name | VARCHAR(100) | NOT NULL |
| parser_version | VARCHAR(30) | NOT NULL |
| content_json | JSON | nullable; structured parsed content |
| layout_json | JSON | nullable; layout/formatting data |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Captures the output of a document parsing step. Using JSON for content allows different parser types to emit different schemas without schema migrations. The parser_name/parser_version pair supports versioned parsing pipelines.

---

### KnowledgeChunk
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| project_id | VARCHAR(36) | FK -> project.id, NOT NULL |
| source_document_id | VARCHAR(36) | FK -> source_document.id, NOT NULL |
| chunk_index | INTEGER | NOT NULL |
| content | TEXT | NOT NULL |
| metadata_json | JSON | nullable |
| embedding | VECTOR(1536) | nullable; pgvector column |

**Purpose:** The atomic retrieval unit for RAG. Text is split into chunks, each stored with a 1536-dimensional OpenAI embedding in a pgvector column. The vector index enables efficient ANN search. `metadata_json` stores per-chunk metadata (e.g., page number, heading hierarchy) without schema changes.

**Design note:** This is the only table using `Vector` from pgvector. The dimension (1536) matches OpenAI's text-embedding-ada-002 model. There is no FK relationship to Project; data is denormalized at the chunk level for query performance (filtering by project_id avoids a join during search).

---

### RequirementItem
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| project_id | VARCHAR(36) | FK -> project.id, NOT NULL |
| section_key | VARCHAR(100) | NOT NULL; maps to a deliverable section |
| requirement_text | TEXT | NOT NULL |
| priority | VARCHAR(30) | default "normal" |
| status | VARCHAR(30) | default "open" |

**Purpose:** Structured requirement extracted from solicitation documents. Each requirement is tagged with a `section_key` that aligns it to a target deliverable section, forming the bridge between source analysis and content generation.

---

### Evidence
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| project_id | VARCHAR(36) | FK -> project.id, NOT NULL |
| section_version_id | VARCHAR(36) | FK -> section_version.id, nullable |
| source_document_id | VARCHAR(36) | FK -> source_document.id, nullable |
| chunk_id | VARCHAR(36) | FK -> knowledge_chunk.id, nullable |
| quote_text | TEXT | NOT NULL |
| locator_json | JSON | nullable; page/position info |
| confidence | FLOAT | nullable |

**Purpose:** Citation record that links generated content back to source material. All three FK columns are nullable to allow partial evidence (e.g., a quote tied to a document but not yet mapped to a specific chunk or section version).

---

### Deliverable
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| project_id | VARCHAR(36) | FK -> project.id, NOT NULL |
| type | VARCHAR(50) | NOT NULL; e.g., "proposal", "technical_volume" |
| title | VARCHAR(255) | NOT NULL |
| status | VARCHAR(30) | default "draft" |
| current_version_id | VARCHAR(36) | NOT a FK; soft reference to SectionVersion.id |
| export_status | VARCHAR(30) | default "not_exported" |
| export_storage_key | VARCHAR(500) | nullable; blob storage path of exported file |

**Purpose:** A logical output artifact composed of sections. `current_version_id` is intentionally not a foreign key -- it points to whichever section version represents the canonical "current" output, but database-level referential integrity is not enforced here because the deliverable's "current" state is a logical rather than strictly relational concept.

---

### DeliverableSection
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| deliverable_id | VARCHAR(36) | FK -> deliverable.id, NOT NULL |
| section_key | VARCHAR(100) | NOT NULL |
| title | VARCHAR(255) | NOT NULL |
| status | VARCHAR(30) | default "draft" |
| assignee_type | VARCHAR(30) | default "ai"; "ai" or "human" |

**Purpose:** The unit of drafting, review, and versioning within a deliverable. Each section can be assigned to AI or human generation. Sections cascade-delete with their deliverable.

---

### SectionVersion
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| deliverable_section_id | VARCHAR(36) | FK -> deliverable_section.id, NOT NULL |
| version_number | INTEGER | NOT NULL; monotonically increasing per section |
| content_json | JSON | nullable; structured representation |
| content_markdown | TEXT | nullable; rendered markdown |
| created_by_actor | VARCHAR(30) | default "ai"; who/what created this version |
| generation_run_id | VARCHAR(36) | FK -> execution_run.id, nullable |

**Purpose:** Immutable snapshot of section content. Each new generation or edit creates a new row; rows are never updated. `generation_run_id` links back to the execution run that produced it. This design provides full version history, audit trail, and the ability to revert or compare.

---

### ExecutionRun
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| project_id | VARCHAR(36) | FK -> project.id, NOT NULL |
| run_type | VARCHAR(50) | NOT NULL; e.g., "generate", "review", "extract" |
| status | VARCHAR(30) | default "queued" |
| input_json | JSON | nullable |
| output_json | JSON | nullable |
| started_at | TIMESTAMP | nullable |
| finished_at | TIMESTAMP | nullable |

**Purpose:** Records one invocation of an execution graph. Input and output are stored as JSON blobs because their schemas vary by run_type. This table is the operational record for pipeline runs, distinct from the business objects those runs produce.

---

### ReviewThread
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| deliverable_section_id | VARCHAR(36) | FK -> deliverable_section.id, NOT NULL |
| status | VARCHAR(30) | default "open" |
| opened_by | VARCHAR(36) | NOT NULL; polymorphic actor ID (user or AI run) |
| resolved_by | VARCHAR(36) | nullable |

**Purpose:** A review conversation anchored to a deliverable section. The `opened_by` and `resolved_by` fields use polymorphic IDs (they could reference a user ID or execution run ID); the interpretation depends on application context rather than a foreign key constraint. This is the soft-referenced actor pattern.

---

### ReviewComment
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| review_thread_id | VARCHAR(36) | FK -> review_thread.id, NOT NULL |
| author_type | VARCHAR(30) | NOT NULL; "user" or "ai" |
| author_id | VARCHAR(36) | NOT NULL; polymorphic reference |
| body | TEXT | NOT NULL |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Individual comment within a review thread. The `author_type`/`author_id` pair identifies who wrote the comment -- either a human user or an AI execution run. This is a separate soft-referenced actor pattern from ReviewThread.

---

### AuditEvent
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| project_id | VARCHAR(36) | FK -> project.id, NOT NULL |
| actor_type | VARCHAR(30) | NOT NULL; "user" or "system" or "ai" |
| actor_id | VARCHAR(36) | NOT NULL; polymorphic reference |
| event_type | VARCHAR(100) | NOT NULL; e.g., "section_generated", "review_resolved" |
| payload_json | JSON | nullable |
| created_at | TIMESTAMP | server default now() |

**Purpose:** Append-only event log. Rows are never updated or deleted under normal operation. `payload_json` stores event-specific data without schema changes. The `actor_type`/`actor_id` pair identifies which user, system process, or AI run triggered the event.

---

### Subscription
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| user_id | VARCHAR(36) | FK -> user.id, UNIQUE, NOT NULL |
| plan | VARCHAR(30) | default "starter" |
| status | VARCHAR(30) | default "active" |
| stripe_customer_id | VARCHAR(255) | nullable |
| created_at | TIMESTAMP | server default now() |
| updated_at | TIMESTAMP | auto-updates on row change |

**Purpose:** Per-user subscription plan with Stripe integration. One-to-one with User (enforced by unique FK). Cascade deletes with the parent user.

---

### ProviderConfig
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| user_id | VARCHAR(36) | FK -> user.id, NOT NULL |
| provider_type | VARCHAR(20) | NOT NULL; "openai" or "anthropic" |
| api_key | TEXT | NOT NULL; encrypted at the application layer |
| api_url | VARCHAR(500) | nullable; custom endpoint |
| model | VARCHAR(100) | NOT NULL |
| label | VARCHAR(100) | NOT NULL |
| is_active | BOOLEAN | default FALSE |
| created_at | TIMESTAMP | server default now() |
| updated_at | TIMESTAMP | auto-updates on row change |

**Purpose:** Stores per-user LLM provider credentials. Multiple provider configs can exist per user (e.g., one OpenAI and one Anthropic), but only one can be active at a time. API keys are stored in the database for user-managed BYOK scenarios; production deployments should add application-level encryption.

---

### RefreshToken
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) | PK, UUID |
| user_id | VARCHAR(36) | FK -> user.id, NOT NULL |
| token_hash | VARCHAR(255) | UNIQUE, NOT NULL |
| expires_at | TIMESTAMP | NOT NULL |
| revoked | BOOLEAN | default FALSE |
| created_at | TIMESTAMP | server default now() |

**Purpose:** JWT refresh token tracking. Only the hash is stored; the raw token is returned to the client once at creation. The `revoked` flag enables token revocation without deletion.

---

## Key Design Patterns

### UUID Primary Keys Throughout
All tables use UUID v4 strings (VARCHAR(36)) as primary keys. Rationale: UUIDs prevent enumeration attacks, allow safe client-side generation, and avoid sequential ID collisions in distributed or offline scenarios. The trade-off is slightly larger index footroom compared to auto-increment integers.

### JSON Fields for Extensible Metadata
Several tables use JSON columns (content_json, layout_json, metadata_json, payload_json, input_json, output_json, locator_json) to store semi-structured data that varies by type or context. This pattern avoids schema migrations when adding new parser outputs, event payloads, or execution inputs. The rule of thumb is: if the data is queried relationally, promote it to a column; if it is stored and retrieved as a blob, keep it in JSON.

### Immutable Versioning Pattern (SectionVersion)
SectionVersion follows an append-only, never-update pattern. Each change to a deliverable section creates a new row with an incremented `version_number`. No row is ever updated or deleted. This provides:
- Full version history for audit and rollback
- Parallel draft comparison
- Clear lineage (each version links to its generating execution run via `generation_run_id`)

The Deliverable.current_version_id field (a soft pointer) determines which version is the "published" one without requiring a denormalized "is_current" flag on the version table itself.

### Soft-Referenced Actors (actor_id / actor_type)
ReviewThread, ReviewComment, and AuditEvent all use a polymorphic actor pattern: an `actor_type` (or `author_type`) column discriminates the kind of actor ("user", "ai", "system"), and an `actor_id` column holds the ID of the record in the corresponding table. This avoids rigid foreign key constraints while preserving traceability. The application layer resolves the actual entity at query time.

### pgvector Integration for Embeddings
KnowledgeChunk.embedding uses pgvector's `VECTOR(1536)` type, enabling in-database nearest-neighbor search. The dimension matches OpenAI's text-embedding-ada-002 model. This avoids the operational complexity of a separate vector database while keeping vectors transactionally consistent with their source documents. An IVFFlat or HNSW index should be created on this column for production performance.

## Cascade Rules

| Parent | Child | Cascade Behavior |
|---|---|---|
| Organization | Team | `all, delete-orphan` |
| Team | TeamMember | `all, delete-orphan` |
| Organization | User | No cascade (users survive org deletion -- error expected if org is deleted with active users) |
| User | Subscription | `all, delete-orphan` |
| User | ProviderConfig | `all, delete-orphan` |
| Organization | Project | No cascade (projects survive org deletion) |
| Project | Bundle | `all, delete-orphan` |
| Bundle | SourceDocument | `all, delete-orphan` |
| SourceDocument | ParsedAsset | `all, delete-orphan` |
| Deliverable | DeliverableSection | `all, delete-orphan` |
| DeliverableSection | SectionVersion | `all, delete-orphan` |

Tables without explicit cascade rules in the model (KnowledgeChunk, RequirementItem, Evidence, ExecutionRun, ReviewThread, ReviewComment, AuditEvent, Invitation, RefreshToken) rely on application-level cleanup or refer to parents that should not be routinely deleted.

## Migration Strategy

Database schema migrations are managed via **Alembic**, configured at `services/api/alembic/`. The migration environment is set up in `services/api/alembic/env.py`, and the Alembic configuration lives at `services/api/alembic.ini`.

New migrations are auto-generated by comparing the SQLAlchemy model definitions against the current database state:

```
alembic revision --autogenerate -m "description of change"
```

All migration revision files live under `services/api/alembic/versions/`. Migrations should be reviewed and tested before applying to production.
