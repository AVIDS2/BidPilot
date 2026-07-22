# BidPilot Competitive Red-Team Audit

Date: 2026-07-22

## Purpose

This is a product-stop audit, not a feature roadmap. It tests whether BidPilot
should continue as an AI bid-writing product after OpenBidKit / YiBiao and the
existing proposal-management market were identified.

Evidence labels:

- `source-verified`: directly inspected public source code or license text.
- `vendor-claimed`: published by a vendor; useful for capability comparison,
  not proof of quality, adoption, or security.
- `hypothesis`: must be validated with real target users before investment.

## Hard Finding: Generic AI Bid Writing Is Not a Viable Position

OpenBidKit is an active, free, open-source desktop bid-workspace competitor.
As of this audit it has a current release cadence, a public AGPL-3.0 license,
and source-verified capabilities for local bid-workspace persistence, tender
analysis, knowledge-base storage, outline/content generation, duplicate and
rejection-risk checks, task recovery, and agent runtime integration.

This invalidates the product claim that BidPilot can win merely by offering:

- upload a tender document;
- parse requirements;
- retrieve company material;
- generate an outline or sections;
- check risk or duplication;
- export a Word document;
- provide an AI chat panel or a coding-agent-style harness.

Those are table stakes or already available at no software-license cost.

## OpenBidKit: Source-Verified Findings

Repository: <https://github.com/yibiaoai/yibiao-simple>

- License: AGPL-3.0. Do not copy, link intimately with, or modify its code for
  a closed SaaS without qualified license review. This is a legal risk note,
  not legal advice.
- Product form: Electron desktop application with Vite, React, TypeScript, and
  a local SQLite workspace (`better-sqlite3`).
- Agent runtime registry: OpenCode is the default runtime; Pi is an alternate
  embedded runtime. The source contains OpenCode environment/isolation checks
  and a local global task queue.
- Durable local work: the SQLite schema includes bid analysis, technical-plan,
  knowledge, rejection-check, duplicate-check, task, and export-template data.
  Interrupted local tasks are explicitly recovered or marked for retry.
- Engineering caution: `client/package.json` exposes build and packaging
  scripts but no normal unit-test script. That is not proof that the product
  has no tests, but it means public source inspection cannot treat it as a
  proven enterprise-quality system.
- Scope limitation: its architecture is a local, single-machine workspace. It
  is not evidence that it provides multi-tenant SaaS isolation, organization
  RBAC, externally auditable approval, enterprise billing, or central
  collaboration. Those gaps are possible product opportunities, not validated
  buyer demand.

Relevant source files:

- <https://github.com/yibiaoai/yibiao-simple/blob/main/client/package.json>
- <https://github.com/yibiaoai/yibiao-simple/blob/main/client/electron/services/agent/agentRuntimeRegistry.cjs>
- <https://github.com/yibiaoai/yibiao-simple/blob/main/client/electron/services/opencode/opencodeIsolationService.cjs>
- <https://github.com/yibiaoai/yibiao-simple/blob/main/client/electron/services/sqliteDatabase.cjs>

## Public Competitor Landscape

### China

`vendor-claimed` public product pages show broad coverage already exists:

- BQPoint / BiaoQiao offers tender parsing, AI bid writing, material market,
  bid checking, simulated bid opening, enterprise space, CA, and bid notices.
- YiBiao markets tender parsing, outline generation, long-form generation,
  duplicate checking, and Word export alongside its source-available desktop
  client.
- Other AI bid-writing services market the same flow: parsing, scoring-point
  extraction, outline/section generation, knowledge reuse, risk checking,
  formatting, and export. Some additionally claim permissions, audit, and
  private deployment.

Sources:

- <https://www.bqpoint.com>
- <https://yibiao.pro>
- <https://www.bid-gun.com/>
- <https://www.xiquebiaoshu.com/>

### Global Proposal / RFP Software

The global category is mature. Loopio and Responsive sell centralized content
libraries, response projects, workflow automation, collaboration, search,
access control, analytics, and AI-assisted drafting. This validates that teams
can pay for response operations beyond raw text generation, but it does not
prove that a Chinese bid team will buy a new entrant.

Sources:

- <https://loopio.com/blog/how-to-evaluate-rfp-tools>
- <https://loopio.com/blog/5-tips-manage-rfp-content-library>
- <https://www.responsive.io/pricing>

## Consequences for BidPilot

### Rejected Positioning

Do not position BidPilot as:

- a generic AI bid-writing SaaS;
- a free-vs-paid clone of OpenBidKit;
- an "AI Agent writes bids for you" wrapper;
- a generic workflow builder marketed as bid software.

The current product is less mature than the free desktop alternative for the
ordinary individual user. A prettier UI, more models, or a larger agent loop
does not reverse that.

### Conditional Position Worth Testing

The only potentially defensible direction is a BidOps / bid-readiness control
plane for teams that must coordinate people and prove what was submitted:

`requirement -> evidence -> claim -> owner -> review -> approval -> export`

Potential paid outcomes:

- a manager can see missing mandatory requirements before submission;
- every assertion in a deliverable can be traced to source evidence or marked
  as an approved inference;
- SMEs, proposal managers, legal, and reviewers have explicit ownership and
  deadlines instead of side-channel spreadsheet coordination;
- an enterprise can audit approvals, history, usage, and exported versions.

This is only a hypothesis. Global RFP platforms already sell parts of this.
Chinese-local tender formats, domestic enterprise integrations, private
deployment, and requirement-level traceability could matter, but none is a
moat until target users say it solves an expensive problem they cannot solve
with OpenBidKit, BQPoint, spreadsheets, and human review.

## Validation Before More Product Code

No new bid-writing, UI-polish, or generic-agent feature should be built before
the following discovery gate.

1. Interview at least five target users across bid management, presales/
   solution, review/legal, and company leadership.
2. Run one observed workflow using a real or sanitized tender package and the
   participant's current stack. Record handoffs, spreadsheets, rework,
   missing-evidence incidents, and approval points.
3. Ask users to compare the proposed readiness-control-plane outcome with
   OpenBidKit or their existing process. Do not ask whether they "like AI".
4. Require at least three participants to name the same costly unresolved
   workflow problem, and at least one to agree to a time-bounded pilot if it is
   solved.

If this gate fails, stop the commercial-product claim. Retain BidPilot as an
Agent engineering portfolio project with an honest scope: governed document
operations, durable LangGraph runs, retrieval, approval, and evaluation.

## Decision Options

### A. Conditional BidOps Pivot

Recommended only after the discovery gate passes. Build the smallest vertical
slice that closes one expensive team workflow, not another writer:

`tender intake -> requirement ledger -> evidence assignment -> review gate ->
approved readiness pack`

The Harness Agent becomes an operator over this control plane. Drafting remains
a downstream capability, not the value proposition.

### B. Open-Source Participation or Fork

Useful for learning or contributing, but not a shortcut to a proprietary
BidPilot SaaS because the upstream project is AGPL-3.0. Any integration plan
requires license review before code is copied or combined.

### C. Portfolio-First Closure

Stop claiming a commercial product. Complete one exemplary agent system with a
small, truthful demo dataset and hard evidence for durability, retrieval,
approval, policy, recovery, and evaluation. This is a credible interview
project even without a startup claim.

## Current Recommendation

Pause feature development. Run the discovery gate. If it validates a specific
team-control problem, pivot to Option A. If not, choose Option C and remove
commercial claims from the roadmap.
