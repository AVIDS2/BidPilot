"""Small, deterministic source material for the opt-in BidPilot demo workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BUILTIN_DEMO_STORAGE_PREFIX = "builtin://bidpilot-demo/"
DEMO_PROJECT_NAME = "演示 · 智慧社区 AI 治理平台投标"
DEMO_BUNDLE_LABEL = "内置演示资料包"

_DEMO_DATA_ROOT = Path(__file__).resolve().parents[4] / "sample-data" / "bidpilot-demo"


@dataclass(frozen=True)
class DemoDocument:
    key: str
    filename: str
    content: str


@dataclass(frozen=True)
class DemoRequirement:
    key: str
    document_key: str
    section_key: str
    text: str
    heading: str
    priority: str
    category: str
    mandatory: bool
    score_weight: float | None
    risk_level: str
    coverage_status: str
    evidence_status: str
    verification_status: str


@dataclass(frozen=True)
class DemoEvidence:
    key: str
    document_key: str
    quote: str
    heading: str
    confidence: float
    requirement_keys: tuple[str, ...]


def _load_demo_document_text(filename: str) -> str:
    """Load the tracked synthetic source used by both demo and regression tests."""

    return (_DEMO_DATA_ROOT / filename).read_text(encoding="utf-8")


DEMO_DOCUMENTS = (
    DemoDocument(
        key="rfp",
        filename="01-招标文件-智慧社区AI治理平台.md",
        content=_load_demo_document_text("01-招标文件-智慧社区AI治理平台.md"),
    ),
    DemoDocument(
        key="supplier",
        filename="02-供应商能力资料-星河云智科技.md",
        content=_load_demo_document_text("02-供应商能力资料-星河云智科技.md"),
    ),
    DemoDocument(
        key="case-study",
        filename="03-同类案例-智慧园区治理平台.md",
        content=_load_demo_document_text("03-同类案例-智慧园区治理平台.md"),
    ),
)

DEMO_REQUIREMENTS = (
    DemoRequirement(
        key="event-governance",
        document_key="rfp",
        section_key="technical-approach",
        text="建设覆盖事件上报、派单、改派、超时提醒、处理反馈和满意度评价的事件治理闭环。",
        heading="3.1 事件治理",
        priority="high",
        category="technical",
        mandatory=True,
        score_weight=10.0,
        risk_level="high",
        coverage_status="partial",
        evidence_status="sufficient",
        verification_status="verified",
    ),
    DemoRequirement(
        key="ai-capabilities",
        document_key="rfp",
        section_key="technical-approach",
        text="提供事件自动分类、处理建议、周报月报生成与自然语言查询能力。",
        heading="3.2 AI 辅助能力",
        priority="high",
        category="technical",
        mandatory=False,
        score_weight=12.0,
        risk_level="high",
        coverage_status="partial",
        evidence_status="weak",
        verification_status="unverified",
    ),
    DemoRequirement(
        key="security-and-localization",
        document_key="rfp",
        section_key="technical-approach",
        text="支持国产化数据库与操作系统适配，并提供角色权限、操作审计、数据访问日志和基础安全能力。",
        heading="3.5 权限与安全",
        priority="high",
        category="technical",
        mandatory=True,
        score_weight=8.0,
        risk_level="high",
        coverage_status="partial",
        evidence_status="sufficient",
        verification_status="verified",
    ),
    DemoRequirement(
        key="delivery-milestones",
        document_key="rfp",
        section_key="staffing-plan",
        text="在 90 个自然日内完成建设与验收，并按里程碑完成调研、原型、开发和试运行。",
        heading="五、项目实施要求",
        priority="high",
        category="delivery",
        mandatory=True,
        score_weight=8.0,
        risk_level="high",
        coverage_status="uncovered",
        evidence_status="missing",
        verification_status="unverified",
    ),
    DemoRequirement(
        key="support-service",
        document_key="rfp",
        section_key="staffing-plan",
        text="提供 7x12 小时远程支持，重大故障 2 小时内响应、8 小时内给出解决方案。",
        heading="六、服务要求",
        priority="high",
        category="delivery",
        mandatory=True,
        score_weight=2.0,
        risk_level="high",
        coverage_status="uncovered",
        evidence_status="missing",
        verification_status="unverified",
    ),
    DemoRequirement(
        key="submission-structure",
        document_key="rfp",
        section_key="exec-summary",
        text="投标文件应包含技术响应表、总体方案、AI 建设方案、实施计划、运维服务方案和案例证明。",
        heading="八、投标文件章节要求",
        priority="high",
        category="submission",
        mandatory=True,
        score_weight=None,
        risk_level="critical",
        coverage_status="uncovered",
        evidence_status="missing",
        verification_status="unverified",
    ),
)

DEMO_EVIDENCE = (
    DemoEvidence(
        key="platform-capability",
        document_key="supplier",
        quote="公司已形成事件上报、工单派发、网格协同、移动巡检、居民评价、数据看板和运维监管一体化能力。",
        heading="2.1 社区治理平台能力",
        confidence=0.96,
        requirement_keys=("event-governance",),
    ),
    DemoEvidence(
        key="ai-security",
        document_key="supplier",
        quote="公司建设了面向社区事件的文本分类、智能摘要、风险识别、处理建议推荐和报表自动生成能力。",
        heading="2.2 AI 辅助治理能力",
        confidence=0.86,
        requirement_keys=("ai-capabilities",),
    ),
    DemoEvidence(
        key="delivery-experience",
        document_key="case-study",
        quote="项目建设周期为 75 天：",
        heading="四、实施周期",
        confidence=0.78,
        requirement_keys=("delivery-milestones",),
    ),
    DemoEvidence(
        key="security-capability",
        document_key="supplier",
        quote="公司平台支持以下安全机制：",
        heading="2.3 数据安全能力",
        confidence=0.9,
        requirement_keys=("security-and-localization",),
    ),
)


def get_builtin_demo_document(storage_key: str) -> DemoDocument | None:
    """Resolve a private built-in document without depending on object storage."""

    if not storage_key.startswith(BUILTIN_DEMO_STORAGE_PREFIX):
        return None
    key = storage_key.removeprefix(BUILTIN_DEMO_STORAGE_PREFIX)
    return next((document for document in DEMO_DOCUMENTS if document.key == key), None)
