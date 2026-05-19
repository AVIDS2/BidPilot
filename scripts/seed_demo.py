"""Seed the database with demo data for the MVP narrative.

Creates a project, bundle, source documents, knowledge chunks, requirements,
deliverable, sections, section versions, evidence, review thread, and audit events.

Usage:
    cd services/api
    uv run python ../../scripts/seed_demo.py
"""

import sys
import os

# Ensure the API app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

from app.db import SessionLocal, engine
from app.models import (
    Base, Project, Bundle, SourceDocument, ParsedAsset,
    KnowledgeChunk, RequirementItem, Evidence, Deliverable,
    DeliverableSection, SectionVersion, ExecutionRun,
    ReviewThread, ReviewComment, AuditEvent, User,
)
from sqlalchemy import text as sa_text

DEMO_PROJECT_NAME = "Acme Corp RFP Response"
DEMO_SCENARIO = "bidpilot"


def seed():
    db = SessionLocal()
    try:
        # Check if demo data already exists
        existing = db.execute(sa_text("SELECT id FROM project WHERE slug = 'acme-corp-rfp-response'")).scalar()
        if existing:
            print("Demo data already exists, skipping...")
            return

        # 1. Create project
        project = Project(
            name=DEMO_PROJECT_NAME,
            slug="acme-corp-rfp-response",
            scenario_package=DEMO_SCENARIO,
            status="active",
        )
        db.add(project)
        db.flush()
        print(f"Created project: {project.id}")

        # 2. Create bundle
        bundle = Bundle(
            project_id=project.id,
            label="Acme Corp RFP Bundle",
            source_type="upload",
            ingest_status="ingested",
        )
        db.add(bundle)
        db.flush()
        print(f"Created bundle: {bundle.id}")

        # 3. Create source documents
        docs = [
            SourceDocument(
                bundle_id=bundle.id,
                storage_key=f"{project.id}/acme-rfp.pdf",
                mime_type="application/pdf",
                checksum="abc123",
                original_filename="acme-rfp.pdf",
                page_count=12,
                parse_status="parsed",
            ),
            SourceDocument(
                bundle_id=bundle.id,
                storage_key=f"{project.id}/acme-requirements.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                checksum="def456",
                original_filename="acme-requirements.docx",
                parse_status="parsed",
            ),
        ]
        for d in docs:
            db.add(d)
        db.flush()
        print(f"Created {len(docs)} source documents")

        # 4. Create parsed assets
        for d in docs:
            pa = ParsedAsset(
                source_document_id=d.id,
                parser_name="docpilot-text-v1",
                parser_version="1.0",
                content_json={"extraction_method": "text", "mime_type": d.mime_type},
            )
            db.add(pa)
        db.flush()

        # 5. Create knowledge chunks
        chunk_texts = [
            "The vendor must provide a cloud-native solution with 99.9% uptime SLA and automatic failover capabilities.",
            "All data must be encrypted at rest using AES-256 and in transit using TLS 1.3 or higher.",
            "The solution must support SSO integration via SAML 2.0 and OpenID Connect protocols.",
            "Vendor must demonstrate compliance with SOC 2 Type II and ISO 27001 certifications.",
            "The platform shall provide a RESTful API for integration with existing enterprise systems.",
            "Pricing must include per-user licensing with volume discounts for 500+ seats.",
            "The solution must support multi-tenant architecture with data isolation guarantees.",
            "Vendor must provide 24/7 technical support with a 4-hour response time SLA.",
            "The platform must include automated backup and disaster recovery with RPO < 1 hour.",
            "All user-facing interfaces must be WCAG 2.1 AA compliant for accessibility.",
            "The vendor shall provide a detailed implementation timeline not exceeding 90 days.",
            "Training materials and onboarding support must be included for all user roles.",
        ]
        chunks = []
        for i, text in enumerate(chunk_texts):
            kc = KnowledgeChunk(
                project_id=project.id,
                source_document_id=docs[i % 2].id,
                chunk_index=i,
                content=text,
                metadata_json={"parser_name": "docpilot-text-v1", "local_chunk_index": i},
            )
            db.add(kc)
            chunks.append(kc)
        db.flush()
        print(f"Created {len(chunks)} knowledge chunks")

        # 6. Create requirements
        requirements = [
            RequirementItem(project_id=project.id, section_key="technical-architecture", requirement_text="Cloud-native with 99.9% uptime SLA", priority="high", status="open"),
            RequirementItem(project_id=project.id, section_key="security-compliance", requirement_text="AES-256 encryption at rest, TLS 1.3 in transit", priority="high", status="open"),
            RequirementItem(project_id=project.id, section_key="security-compliance", requirement_text="SOC 2 Type II and ISO 27001 compliance", priority="high", status="open"),
            RequirementItem(project_id=project.id, section_key="integration", requirement_text="SSO via SAML 2.0 and OIDC", priority="medium", status="open"),
            RequirementItem(project_id=project.id, section_key="integration", requirement_text="RESTful API for enterprise integration", priority="medium", status="open"),
            RequirementItem(project_id=project.id, section_key="pricing", requirement_text="Per-user licensing with volume discounts", priority="medium", status="open"),
            RequirementItem(project_id=project.id, section_key="support-operations", requirement_text="24/7 support with 4-hour response SLA", priority="high", status="open"),
            RequirementItem(project_id=project.id, section_key="support-operations", requirement_text="Automated backup with RPO < 1 hour", priority="medium", status="open"),
            RequirementItem(project_id=project.id, section_key="accessibility", requirement_text="WCAG 2.1 AA compliance", priority="low", status="open"),
            RequirementItem(project_id=project.id, section_key="implementation", requirement_text="Implementation timeline not exceeding 90 days", priority="high", status="open"),
        ]
        for r in requirements:
            db.add(r)
        db.flush()
        print(f"Created {len(requirements)} requirements")

        # 7. Create deliverable and sections
        deliverable = Deliverable(
            project_id=project.id,
            type="bidpilot",
            title="Acme Corp RFP Response",
            status="draft",
        )
        db.add(deliverable)
        db.flush()

        sections = [
            DeliverableSection(deliverable_id=deliverable.id, section_key="technical-architecture", title="Technical Architecture", status="approved"),
            DeliverableSection(deliverable_id=deliverable.id, section_key="security-compliance", title="Security & Compliance", status="draft"),
            DeliverableSection(deliverable_id=deliverable.id, section_key="integration", title="Integration", status="draft"),
            DeliverableSection(deliverable_id=deliverable.id, section_key="pricing", title="Pricing", status="draft"),
            DeliverableSection(deliverable_id=deliverable.id, section_key="support-operations", title="Support & Operations", status="draft"),
            DeliverableSection(deliverable_id=deliverable.id, section_key="accessibility", title="Accessibility", status="draft"),
            DeliverableSection(deliverable_id=deliverable.id, section_key="implementation", title="Implementation Plan", status="draft"),
        ]
        for s in sections:
            db.add(s)
        db.flush()
        print(f"Created {len(sections)} deliverable sections")

        # 8. Create section versions (draft content)
        run1 = ExecutionRun(
            project_id=project.id,
            run_type="draft_section",
            status="succeeded",
            input_json={"section_key": "technical-architecture"},
            output_json={"model_used": "stub"},
        )
        db.add(run1)
        db.flush()

        sv1 = SectionVersion(
            deliverable_section_id=sections[0].id,
            version_number=1,
            content_markdown="""## Technical Architecture

Our cloud-native platform is built on a microservices architecture deployed across multiple availability zones, ensuring **99.9% uptime SLA** with automatic failover capabilities.

### Key Architecture Highlights

- **Multi-AZ Deployment**: Active-active configuration across 3+ availability zones
- **Automatic Failover**: Sub-second failover with zero data loss
- **Container Orchestration**: Kubernetes-based deployment with auto-scaling
- **Data Replication**: Synchronous replication for critical data stores

### Infrastructure

| Component | Specification |
|-----------|--------------|
| Compute | Kubernetes cluster with auto-scaling (2-50 nodes) |
| Database | Managed PostgreSQL with read replicas |
| Cache | Redis cluster with sentinel-based failover |
| Storage | Object storage with 11 nines durability |

*This section addresses the RFP requirement for cloud-native architecture with 99.9% uptime SLA.*""",
            created_by_actor="ai",
            generation_run_id=run1.id,
        )
        db.add(sv1)
        db.flush()

        # Second version (after review)
        sv2 = SectionVersion(
            deliverable_section_id=sections[0].id,
            version_number=2,
            content_markdown="""## Technical Architecture

Our cloud-native platform is built on a microservices architecture deployed across multiple availability zones, ensuring **99.9% uptime SLA** with automatic failover capabilities.

### Key Architecture Highlights

- **Multi-AZ Deployment**: Active-active configuration across 3+ availability zones
- **Automatic Failover**: Sub-second failover with zero data loss
- **Container Orchestration**: Kubernetes-based deployment with auto-scaling
- **Data Replication**: Synchronous replication for critical data stores
- **Disaster Recovery**: Full DR site with automated runbook execution

### Infrastructure

| Component | Specification |
|-----------|--------------|
| Compute | Kubernetes cluster with auto-scaling (2-50 nodes) |
| Database | Managed PostgreSQL with read replicas |
| Cache | Redis cluster with sentinel-based failover |
| Storage | Object storage with 11 nines durability |

### Uptime Track Record

Our platform has maintained **99.97% uptime** over the past 12 months, exceeding the 99.9% SLA requirement.

*Revised to include DR capabilities and uptime track record per review feedback.*""",
            created_by_actor="ai",
            generation_run_id=run1.id,
        )
        db.add(sv2)
        db.flush()
        print(f"Created 2 section versions")

        # 9. Create evidence links
        evidence_items = [
            Evidence(project_id=project.id, section_version_id=sv1.id, source_document_id=docs[0].id, chunk_id=chunks[0].id, quote_text=chunk_texts[0], locator_json={"chunk_index": 0}, confidence=0.95),
            Evidence(project_id=project.id, section_version_id=sv1.id, source_document_id=docs[0].id, chunk_id=chunks[6].id, quote_text=chunk_texts[6], locator_json={"chunk_index": 6}, confidence=0.88),
            Evidence(project_id=project.id, section_version_id=sv2.id, source_document_id=docs[1].id, chunk_id=chunks[8].id, quote_text=chunk_texts[8], locator_json={"chunk_index": 8}, confidence=0.82),
        ]
        for ev in evidence_items:
            db.add(ev)
        db.flush()
        print(f"Created {len(evidence_items)} evidence records")

        # 10. Create review thread and comments
        review_thread = ReviewThread(
            deliverable_section_id=sections[0].id,
            status="resolved",
            opened_by="dev-user",
            resolved_by="dev-reviewer",
        )
        db.add(review_thread)
        db.flush()

        comments = [
            ReviewComment(review_thread_id=review_thread.id, author_type="human", author_id="dev-reviewer", body="Please add disaster recovery details and actual uptime metrics."),
            ReviewComment(review_thread_id=review_thread.id, author_type="ai", author_id="system", body="I'll revise the section to include DR capabilities and our uptime track record."),
        ]
        for c in comments:
            db.add(c)
        db.flush()
        print(f"Created review thread with {len(comments)} comments")

        # 11. Create audit events
        audit_events = [
            AuditEvent(project_id=project.id, actor_type="human", actor_id="dev-user", event_type="project.created", payload_json={"name": DEMO_PROJECT_NAME}),
            AuditEvent(project_id=project.id, actor_type="human", actor_id="dev-user", event_type="bundle.registered", payload_json={"bundle_id": bundle.id, "label": bundle.label}),
            AuditEvent(project_id=project.id, actor_type="system", actor_id="worker", event_type="bundle.ingested", payload_json={"bundle_id": bundle.id, "chunks_created": len(chunks)}),
            AuditEvent(project_id=project.id, actor_type="human", actor_id="dev-user", event_type="draft.requested", payload_json={"section_key": "technical-architecture"}),
            AuditEvent(project_id=project.id, actor_type="system", actor_id="worker", event_type="draft.succeeded", payload_json={"section_key": "technical-architecture", "model_used": "stub"}),
            AuditEvent(project_id=project.id, actor_type="human", actor_id="dev-reviewer", event_type="review.comment_added", payload_json={"thread_id": review_thread.id}),
            AuditEvent(project_id=project.id, actor_type="human", actor_id="dev-reviewer", event_type="review.approved", payload_json={"section_key": "technical-architecture"}),
        ]
        for ae in audit_events:
            db.add(ae)
        db.flush()
        print(f"Created {len(audit_events)} audit events")

        # 12. Create dev user
        import bcrypt
        dev_user = User(
            email="demo@docpilot.ai",
            display_name="Demo User",
            role="admin",
            password_hash=bcrypt.hashpw("demo1234".encode(), bcrypt.gensalt()).decode(),
        )
        db.add(dev_user)
        db.flush()
        print(f"Created demo user: demo@docpilot.ai / demo1234")

        db.commit()
        print("\n✅ Demo data seeded successfully!")
        print(f"   Project ID: {project.id}")
        print(f"   Login: demo@docpilot.ai / demo1234")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
