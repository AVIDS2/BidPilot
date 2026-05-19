"""Seed the database with a realistic synthetic Chinese RFP document.

Reads tests/fixtures/rfp-sample.md, creates a project, bundle, source documents,
knowledge chunks, requirement items, and a deliverable with sections.

Stores document content directly (no MinIO dependency).

Usage:
    cd <repo-root>
    python scripts/seed_with_real_data.py
"""

import sys
import os

# Ensure the API app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

from app.db import SessionLocal
from app.models import (
    Project,
    Bundle,
    SourceDocument,
    ParsedAsset,
    KnowledgeChunk,
    RequirementItem,
    Deliverable,
    DeliverableSection,
    Organization,
)
from sqlalchemy import text as sa_text

RFP_PATH = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "rfp-sample.md")
PROJECT_NAME = "智慧政务平台建设投标"
PROJECT_SLUG = "smart-government-platform-bid"
SCENARIO = "bidpilot"

# Default org used when none exists yet
DEFAULT_ORG_SLUG = "default"
DEFAULT_ORG_NAME = "Default Organization"


def _read_rfp() -> str:
    with open(RFP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _get_or_create_org(db) -> Organization:
    """Return an existing organization or create a default one."""
    org = db.execute(
        sa_text("SELECT * FROM organization ORDER BY created_at ASC LIMIT 1")
    ).first()
    if org:
        return db.get(Organization, org.id)

    org = Organization(slug=DEFAULT_ORG_SLUG, name=DEFAULT_ORG_NAME)
    db.add(org)
    db.flush()
    print(f"Created default organization: {org.id}")
    return org


def _chunk_markdown(content: str) -> list[dict]:
    """Split markdown document into chunks by ## headings.

    Each chunk is a dict with 'heading', 'content' and 'index'.
    """
    lines = content.split("\n")
    chunks = []
    current_heading = "文档开头"
    current_lines: list[str] = []
    chunk_index = 0

    for line in lines:
        if line.startswith("## ") and current_lines:
            chunks.append(
                {
                    "index": chunk_index,
                    "heading": current_heading,
                    "content": "\n".join(current_lines).strip(),
                }
            )
            chunk_index += 1
            current_heading = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    # Last chunk
    if current_lines:
        chunks.append(
            {
                "index": chunk_index,
                "heading": current_heading,
                "content": "\n".join(current_lines).strip(),
            }
        )

    return chunks


def seed():
    db = SessionLocal()
    try:
        # ── Idempotency check ──────────────────────────────────────────
        existing = db.execute(
            sa_text("SELECT id FROM project WHERE slug = :slug"),
            {"slug": PROJECT_SLUG},
        ).scalar()
        if existing:
            print(f"Project '{PROJECT_SLUG}' already exists (id={existing}), skipping.")
            return

        # ── Read RFP document ──────────────────────────────────────────
        rfp_content = _read_rfp()
        print(f"Read RFP document ({len(rfp_content)} chars)")

        # ── Organization ───────────────────────────────────────────────
        org = _get_or_create_org(db)
        org_id = org.id

        # ── 1. Create project ──────────────────────────────────────────
        project = Project(
            name=PROJECT_NAME,
            slug=PROJECT_SLUG,
            scenario_package=SCENARIO,
            status="active",
            org_id=org_id,
        )
        db.add(project)
        db.flush()
        print(f"[1/7] Created project: {project.id} ({PROJECT_NAME})")

        # ── 2. Create bundle ───────────────────────────────────────────
        bundle = Bundle(
            project_id=project.id,
            label="智慧政务平台RFP招标文件",
            source_type="upload",
            ingest_status="ingested",
        )
        db.add(bundle)
        db.flush()
        print(f"[2/7] Created bundle: {bundle.id}")

        # ── 3. Create source document (inline content) ─────────────────
        doc = SourceDocument(
            bundle_id=bundle.id,
            storage_key=f"inline://{PROJECT_SLUG}/rfp-sample.md",
            mime_type="text/markdown",
            checksum="inline-seed-" + str(hash(rfp_content) % (2**31)),
            original_filename="rfp-sample.md",
            parse_status="parsed",
        )
        db.add(doc)
        db.flush()

        # Store the full document content in a parsed asset (no MinIO)
        asset = ParsedAsset(
            source_document_id=doc.id,
            parser_name="inline-reader",
            parser_version="1.0",
            content_json={
                "storage": "inline",
                "mime_type": "text/markdown",
                "text": rfp_content,
            },
        )
        db.add(asset)
        db.flush()
        print(f"[3/7] Created source document + parsed asset: {doc.id}")

        # ── 4. Create knowledge chunks from document sections ─────────
        chunks_data = _chunk_markdown(rfp_content)
        chunks = []
        for cd in chunks_data:
            kc = KnowledgeChunk(
                project_id=project.id,
                source_document_id=doc.id,
                chunk_index=cd["index"],
                content=cd["content"],
                metadata_json={
                    "parser_name": "inline-reader",
                    "chunk_type": "paragraphs",
                    "heading": cd["heading"],
                    "heading_path": [h.strip() for h in cd["heading"].split(" > ")],
                    "heading_level": 2,
                },
            )
            db.add(kc)
            chunks.append(kc)
        db.flush()
        print(f"[4/7] Created {len(chunks)} knowledge chunks")

        # ── 5. Create requirement items extracted from RFP ────────────
        requirements = [
            RequirementItem(
                project_id=project.id,
                section_key="architecture",
                requirement_text="系统须采用微服务架构设计，通过 API 网关统一管理服务",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="architecture",
                requirement_text="支持容器化部署（Docker + Kubernetes），实现弹性伸缩和灰度发布",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="architecture",
                requirement_text="前端使用 Vue.js 或 React，后端使用 Spring Cloud 或同类微服务框架",
                priority="medium",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="architecture",
                requirement_text="须适配华为云、阿里云、政务云等多种云平台",
                priority="medium",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="architecture",
                requirement_text="须支持国产芯片架构（鲲鹏、飞腾、龙芯）和国产操作系统（麒麟、统信UOS）",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="security",
                requirement_text="系统须通过国家网络安全等级保护三级测评",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="security",
                requirement_text="敏感数据全程加密，传输层 TLS 1.3，存储层国密 SM4 算法加密",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="security",
                requirement_text="遵守《个人信息保护法》，提供数据脱敏、访问审计、权限管控机制",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="security",
                requirement_text="支持多因素认证（MFA），集成统一身份认证平台",
                priority="medium",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="implementation",
                requirement_text="项目建设周期不超过 12 个月，须提供详细分阶段实施计划",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="implementation",
                requirement_text="项目团队不少于 15 人，项目经理须持有 PMP 或高级项目经理证书",
                priority="medium",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="implementation",
                requirement_text="须提供不少于 80 学时的系统培训",
                priority="medium",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="qualification",
                requirement_text="投标人须具有 CMMI 三级及以上认证",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="qualification",
                requirement_text="须具有 ISO 9001 和 ISO 27001 认证",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="qualification",
                requirement_text="近三年须完成至少 2 个合同金额不低于 1000 万元的政务信息化项目",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="sla",
                requirement_text="系统可用率不低于 99.9%，月度停机不超过 43 分钟",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="sla",
                requirement_text="严重故障响应 ≤ 1 小时，恢复 ≤ 4 小时",
                priority="high",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="sla",
                requirement_text="每日全量备份，RPO ≤ 24 小时，RTO ≤ 4 小时",
                priority="medium",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="sla",
                requirement_text="提供三年免费运维服务，含驻场运维工程师",
                priority="medium",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="deliverables",
                requirement_text="须按阶段提交 14 项交付物，包括需求规格说明、系统设计、源代码、测试报告等",
                priority="medium",
                status="open",
            ),
            RequirementItem(
                project_id=project.id,
                section_key="deliverables",
                requirement_text="所有交付物须提供中文版本，源代码须符合规范编码标准",
                priority="low",
                status="open",
            ),
        ]
        for r in requirements:
            db.add(r)
        db.flush()
        print(f"[5/7] Created {len(requirements)} requirement items")

        # ── 6. Create deliverable with sections ────────────────────────
        deliverable = Deliverable(
            project_id=project.id,
            type=SCENARIO,
            title=f"{PROJECT_NAME} — 投标文件",
            status="draft",
        )
        db.add(deliverable)
        db.flush()

        sections_data = [
            ("technical-approach", "技术方案"),
            ("implementation-plan", "实施方案"),
            ("qualification-evidence", "资质证明"),
            ("exec-summary", "执行摘要"),
            ("pricing-summary", "报价方案"),
            ("past-performance", "过往业绩"),
            ("staffing-plan", "人员配置计划"),
        ]
        sections = []
        for section_key, title in sections_data:
            sec = DeliverableSection(
                deliverable_id=deliverable.id,
                section_key=section_key,
                title=title,
                status="draft",
                assignee_type="ai",
            )
            db.add(sec)
            sections.append(sec)
        db.flush()
        print(f"[6/7] Created deliverable with {len(sections)} sections: {deliverable.id}")

        # ── 7. (No review threads / users — keep focused on RFP data) ─

        db.commit()
        print("\n[7/7] Seed data committed successfully!")
        print(f"   Project:       {PROJECT_NAME} ({project.id})")
        print(f"   Bundle:        {bundle.id}")
        print(f"   Document:      {doc.id}")
        print(f"   Chunks:        {len(chunks)}")
        print(f"   Requirements:  {len(requirements)}")
        print(f"   Deliverable:   {deliverable.id}")
        print(f"   Sections:      {len(sections)}")

    except Exception as e:
        db.rollback()
        print(f"\nError seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
