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
