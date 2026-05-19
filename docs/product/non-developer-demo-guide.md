# Non-Developer Demo Guide

This guide enables a non-developer (proposal manager, presales engineer, or reviewer) to demonstrate the complete BidPilot workflow without technical assistance.

**Prerequisite**: The DocPilot application must be running and a demo account must be provisioned. Contact the pilot owner for credentials.

## Step-by-step walkthrough

### 1. Log in

1. Open the DocPilot URL in your browser (e.g., `http://localhost:5173`)
2. Enter the demo email and password provided to you
3. Click **Login**
4. You should see the **Projects** page

### 2. Create a project

1. Click the **+ New Project** button
2. Enter a project name (e.g., "Acme Corp RFP Response")
3. Select **BidPilot** as the scenario package
4. Click **Create**
5. You are automatically taken to the project detail page

### 3. Upload source documents

1. Click the **Bundles** tab
2. In the **Bundle Label** field, type a name (e.g., "RFP Source Documents")
3. Click **Register Bundle**
4. The bundle appears in an accordion — click the bundle name to expand it
5. Click **Choose File** under "Upload Document"
6. Select a document from your computer (PDF, DOCX, or TXT)
7. The document is uploaded and queued for parsing

### 4. Review extracted requirements

1. Click the **Requirements** tab
2. After parsing completes, extracted requirements are listed with section keys and requirement text
3. You can manually add or correct requirements if needed

### 5. Draft a section

1. Click the **Deliverables** tab
2. Click **+ Add Deliverable**, choose type "proposal", and give it a title
3. Click the **Review** tab
4. Select a section and click **Generate Draft** (or the system may auto-draft)
5. The draft appears with evidence links showing which source documents support each claim
6. If evidence is missing, the system shows an explicit **missing-evidence marker**

### 6. Review and approve

1. Still on the **Review** tab, read the generated draft
2. To approve: click the **Approve** button on the section
3. To request changes: add a comment and click **Reject** — the section can be re-drafted
4. Only approved sections are included in the export

### 7. Export the deliverable

1. Click the **Export** tab
2. Click **Export as DOCX**
3. The system generates a Word document from all approved sections
4. Download the file to your computer

### 8. Inspect the audit trail

1. Click the **Audit** tab (visible to admin users only)
2. Review the chronological list of events: project creation, bundle uploads, draft generations, approvals, exports
3. Each event shows who performed the action, when, and on which resource

### 9. Check system status (admin only)

1. Click the **System** tab
2. View the runtime summary: queue depth, failed runs, success rate, and dependency health

## What to verify

After completing the walkthrough, confirm the following:

- [ ] You successfully logged in without developer help
- [ ] You created a project and uploaded at least one document
- [ ] You saw extracted requirements from the uploaded document
- [ ] You generated or viewed a draft section with evidence links
- [ ] You approved or rejected a section
- [ ] You exported a DOCX file
- [ ] You viewed the audit trail
- [ ] The experience was understandable without reading source code

## Known limitations

See `docs/product/known-limitations.md` for the current list of known issues and constraints.

## Getting help

If you encounter issues during the demo:

1. Check `docs/ops/deployment-and-runbook.md` for common troubleshooting
2. Email the bootstrap admin for technical support
3. Report the issue to the pilot owner for escalation
