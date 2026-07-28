# BidPilot Non-Developer Demo Guide

This guide is for a bid manager, presales engineer, or reviewer. It explains
what to do in the product without requiring source-code knowledge.

Use only the synthetic files in
[`sample-data/bidpilot-demo`](../../sample-data/bidpilot-demo) for a public
demo. Do not upload a real tender, customer document, provider key, or
unredacted personal data during a demonstration.

## Before the demo

The pilot owner prepares these items before inviting a non-developer:

1. The API, Worker, PostgreSQL, Redis and object storage health checks are
   green.
2. A demo user is an owner or reviewer of one demo organization.
3. A server-side platform model configuration or an encrypted user provider
   configuration is active. API keys are never entered into the chat message
   box or displayed in the browser.
4. The background worker is consuming jobs. Parsing and drafting are not
   expected to finish inside a browser request.

## 15-minute workflow

### 1. Create a bid workspace

Create a project named `智慧社区 AI 治理平台投标演示`. The platform creates a
project scope, an initial deliverable/outline, membership, and audit history.

You may use the normal project screen or ask the Assistant:

> 创建一个名为“智慧社区 AI 治理平台投标演示”的项目

In the normal approval mode, accept the confirmation card. A confirmation is
evidence of policy enforcement, not a broken chat interaction.

**Verify:** the project appears in the project list and the audit trail shows
the creation action.

### 2. Add safe source material

Upload the three files from `sample-data/bidpilot-demo`:

- `01-招标文件-智慧社区AI治理平台.md`
- `02-供应商能力资料-星河云智科技.md`
- `03-同类案例-智慧园区治理平台.md`

The Assistant upload flow deliberately stages files privately first. Ask it to
place the staged files into the chosen project only after you have selected the
project boundary. This prevents a conversational file from silently becoming
shared project evidence.

**Verify:** each file has a document/parse status; the project only shows
documents that belong to its bundle.

### 3. Inspect requirements and evidence

Wait for parsing/indexing to finish, then open the Requirement Ledger. Look
for requirements around event governance, AI-assisted classification,
role-based security, delivery milestones, and service response.

Ask the Assistant a read-only question such as:

> 查看这个项目的需求、证据和当前准备度，指出缺口并给出来源位置。

**Verify:** the response identifies scoped project facts and source locators.
It should not fabricate a source. Missing support is displayed as a gap or
missing-evidence state.

### 4. Draft one section

Choose one outline section, such as a technical response or implementation
plan. Start drafting from the workspace or ask:

> 根据当前项目的已验证资料，起草“技术响应方案”章节。

Drafting is a background workflow. The Assistant creates a linked workflow
run, and the Worker performs retrieval, planning, drafting and validation.
The product may ask for confirmation because drafting has model/usage cost.

**Verify:** the live timeline shows an execution run; the completed result is
a versioned draft candidate with evidence links or an explicit missing-evidence
marker.

### 5. Review, reject once, then approve

Open the candidate version in the review surface. First reject it with a
specific change request, for example: “补充 90 天交付里程碑与 2 小时重大故障
响应依据”. Start a redraft, then approve the revised candidate if it is
acceptable.

**Verify:** both candidate versions remain visible. The old approved version is
not overwritten, and the decision/audit trail explains the reason for the
rerun.

### 6. Export approved content

Request a DOCX or PDF export after the required sections are approved.

**Verify:** the exported artifact is associated with approved versions only;
the export record and audit entry are visible. A draft that was rejected must
not appear in the export.

### 7. Show the operating trace

An administrator can inspect the run diagnostics for the Assistant or workflow
run. The diagnostic view correlates the public run, capability/approval states,
linked workflow run, usage/retrieval counters, and stable error categories.

**Verify:** it does not show prompt text, attachment content, provider keys,
raw tool arguments, database identifiers, or unredacted upstream errors.

## What a healthy demo looks like

| User-visible event | Durable evidence behind it |
| --- | --- |
| Assistant starts work | `RuntimeRun` and append-only `RuntimeEvent` records |
| A write asks for confirmation | `RuntimeApproval` plus policy/audit record |
| Drafting continues in background | linked `ExecutionRun` and worker events |
| Reviewer requests changes | immutable `SectionVersion`, review thread and decision |
| Export completes | approved-version snapshot and export/audit record |

## If something fails

- A provider/model error should be a short redacted product message, not a raw
  gateway exception. Record the Run ID and inspect the admin diagnostics.
- If a job is queued for too long, inspect Worker/Redis health before retrying.
- If the system asks for missing information or approval, provide the requested
  business information or confirmation. Do not work around it by re-sending
  the same request repeatedly.
- If a resource is inaccessible, confirm that the current user is a member of
  that project. Approval does not grant project permission.

## Demo acceptance checklist

- [ ] Created a project in the intended organization.
- [ ] Uploaded synthetic source documents into that project only.
- [ ] Saw source-bound requirements/evidence or an explicit gap.
- [ ] Started one background draft and observed a linked run.
- [ ] Rejected one candidate, regenerated it, and approved a later version.
- [ ] Exported only approved content.
- [ ] Inspected a safe operational trace without exposing secrets or source
  content.

For an engineering/interview-oriented walkthrough, use
[the golden-path script](interview-demo-script.md).
