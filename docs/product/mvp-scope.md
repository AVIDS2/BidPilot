# DocPilot MVP Scope

## Product target

The first shippable version of DocPilot must prove one complete and credible scenario:

- create a BidPilot project
- upload a realistic document bundle
- extract structured requirements
- generate evidence-backed section drafts
- run human review and approval inside the system
- export a final deliverable package
- show a clear audit trail and trace correlation

## MVP user promise

For a proposal or presales team, the system should turn a bundle of source materials into a reviewable draft package with source attribution and workflow state, without forcing review work to happen outside the product.

## MVP audience

- proposal manager
- presales engineer
- solution architect
- reviewer or approver

## Must-have capabilities

### Project workspace

- create and list projects
- attach scenario package metadata
- track project status

### Bundle intake

- register uploaded source documents
- queue parsing
- store normalized parse output

### Requirement extraction

- derive requirement items from parsed sources
- support manual correction of extracted requirements

### Evidence graph

- attach evidence records to sections and requirements
- preserve source locator metadata

### Section drafting

- request a section draft
- store draft output as a versioned section snapshot
- preserve generation run metadata

### Review flow

- comment on sections
- approve or reject sections
- rerun a section after review feedback

### Export

- export approved content into a deliverable artifact
- record export status and output location

### Governance

- record audit events
- surface execution run status
- correlate output to evidence and generation metadata

## Nice-to-have but not required for MVP

- multi-scenario packages
- advanced template marketplace
- real-time collaborative editing
- provider comparison dashboards
- automatic red-team or compliance scoring
- external enterprise connectors beyond a demo-safe adapter

## Explicitly out of scope for MVP

- generic workflow builder UI
- fully autonomous multi-agent autonomy loops
- external messaging automation
- custom model training product surface
- office-suite parity editing
- heavy microservice decomposition

## Acceptance bar

The MVP is only complete when all of the following are true:

- one sample BidPilot project can run end to end in a local environment
- one reviewer can approve or reject a section in-system
- one exported deliverable is produced from approved content
- every generated section has evidence links or an explicit missing-evidence marker
- key events are inspectable through audit and trace views

## Demo narrative

The preferred public demo story is:

1. create a project
2. upload an RFP or presales bundle
3. inspect extracted requirements
4. trigger drafting for one high-value section
5. review the draft with citations
6. reject or approve
7. export the section or final artifact
8. inspect the audit trail
