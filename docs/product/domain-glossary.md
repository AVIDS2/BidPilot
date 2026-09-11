# Domain Glossary

## Goal

Keep product and implementation language consistent across documents, code, and UI.

## Terms

### Project

The top-level working engagement in DocPilot. All bundles, runs, deliverables, reviews, and audit events belong to a project.

### Scenario package

A reusable product surface built on the DocPilot core for a specific business domain. `BidPilot` is the first scenario package.

### Bundle

A project-scoped group of source materials uploaded or imported together.

### Source document

An original artifact such as a PDF, DOCX, image, spreadsheet, or markdown file stored as source input.

### Parsed asset

The normalized output produced by the parser layer from a source document.

### Knowledge chunk

A retrieval unit derived from normalized parsed content and stored for search, ranking, and evidence generation.

### Requirement item

A structured requirement extracted from project materials that can later be mapped to sections, evidence, and response content.

### Evidence

A source-backed citation record that links generated output to a durable locator in project materials.

### Deliverable

A logical output artifact for the project, such as a bid response package, proposal output, or delivery document set.

### Deliverable section

A section-level unit inside a deliverable that can be drafted, reviewed, rerun, approved, and exported.

### Section version

An immutable snapshot of a deliverable section at a point in time.

### Execution run

A durable record representing one asynchronous or long-running operation in the system.

### Review thread

A durable human review conversation and decision object attached to a section or other reviewable unit.

### Audit event

An append-only record describing a security-, workflow-, or governance-relevant action.

### Control plane

The product layer that owns durable business truth and commands.

### Execution plane

The layer that performs long-running, asynchronous, or AI-driven work and reports outcomes back into the control plane.

### Integration plane

The layer that adapts model providers, parsers, retrievers, tools, and external systems into stable internal contracts.

### Operations plane

The layer responsible for observability, deployment, recovery, and operational discipline.

## User-facing memory language

The product must not expose the four memory types as four technical navigation
items. They are an implementation model used to decide what can be stored,
who can read it, and how it is retrieved.

| Engineering type | BidPilot product term | What users see | Source of truth |
| --- | --- | --- | --- |
| Working memory | 当前工作上下文 | 当前项目、当前会话、附件、待确认事项和正在进行的任务 | conversation/runtime state |
| Episodic memory | 工作记录 | 已完成任务、审核决定、失败原因、修订过程和项目复盘 | ChatMessage, RuntimeRun/Event, review/audit records |
| Semantic memory | 项目知识 | 已确认的项目事实、要求、风险、决定和术语，均带来源 | PostgreSQL MemoryRecord + evidence links |
| Procedural memory | 团队方法 | 模板、写作规范、审批规则、组织流程和可复用操作方式 | published org/project knowledge and skills |

`用户偏好` is a separate personalization scope, not a fifth business-memory
system. It is the only data currently delegated to the optional Mem0 adapter:
language, response format, communication style, and explicitly confirmed work
habits. Mem0 must never become the source of truth for tender facts, deadlines,
prices, qualifications, documents, or evidence.

### Naming rules

- Use `当前工作上下文`, `工作记录`, `项目知识`, `团队方法`, and `用户偏好` in
  product copy.
- Do not use `运行记录`, `处理队列`, `Mem0`, `向量记忆`, `checkpointer`, or
  `Store` in ordinary customer navigation or toast messages.
- `运行记录` remains an administrator/recovery surface and is reached from a
  failed or interrupted task, not from the primary sidebar.
- `知识库` is the user-facing home for project knowledge and source-backed
  retrieval. It is not a synonym for user preference memory.
