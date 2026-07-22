"""Small, deterministic source material for the opt-in BidPilot demo workspace."""

from __future__ import annotations

from dataclasses import dataclass


BUILTIN_DEMO_STORAGE_PREFIX = "builtin://bidpilot-demo/"
DEMO_PROJECT_NAME = "演示 · 智慧社区 AI 治理平台投标"
DEMO_BUNDLE_LABEL = "内置演示资料包"


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


DEMO_DOCUMENTS = (
    DemoDocument(
        key="rfp",
        filename="01-招标文件-智慧社区AI治理平台.md",
        content="""# 智慧社区 AI 治理平台建设项目招标文件（演示）

## 项目概况

采购人计划建设一套智慧社区 AI 治理平台，服务街道、社区、物业、网格员与居民。项目预算为 280 万元，建设周期为 90 个自然日，质保期不少于 3 年。

## 功能与技术要求

- 支持居民、网格员、物业人员提交事件，并覆盖派单、改派、超时提醒、处理反馈与满意度评价。
- 支持 AI 自动分类、处理建议、周报月报生成与自然语言查询。
- 支持街道、社区、小区三级数据看板，并可按时间、社区、事件类型和处理状态筛选。
- 支持国产化数据库与国产操作系统适配，文件存储采用对象存储并提供标准 REST API。

## 实施与服务要求

- 第 10 天完成需求调研与实施计划，第 90 天完成验收交付。
- 提供 7x12 小时远程技术支持；重大故障 2 小时内响应，8 小时内给出解决方案。
- 提供源码、部署文档、接口文档和用户手册。

## 评分与提交

技术部分 60 分，其中 AI 能力方案 12 分、总体架构设计 10 分、数据安全与权限方案 8 分。投标文件应包含技术响应表、项目理解与总体方案、AI 能力建设方案、实施计划、运维服务方案和项目团队与案例证明。
""",
    ),
    DemoDocument(
        key="supplier",
        filename="02-供应商能力资料-星河云智科技.md",
        content="""# 星河云智科技能力资料（演示）

## 平台能力

星河云智提供基于容器化部署的社区治理平台，支持 PostgreSQL、对象存储、标准 REST API、角色权限控制、操作审计和数据访问日志。

## AI 与安全

平台可对社区事件进行文本分类、趋势分析和处置建议生成。敏感配置采用服务端加密管理，平台支持登录保护、访问审计、备份恢复演练和最小权限访问。

## 交付方式

项目采用调研、原型确认、开发测试、试运行、培训和验收交接的分阶段实施方式，并提供部署文档、接口文档和管理员培训材料。
""",
    ),
    DemoDocument(
        key="case-study",
        filename="03-同类案例-智慧园区治理平台.md",
        content="""# 智慧园区治理平台同类案例（演示）

项目为多个园区提供事件闭环、设施巡检、移动协同和运营看板能力。交付团队在 12 周内完成需求梳理、核心原型、联调试运行和管理员培训。

案例中沉淀了项目实施计划、权限矩阵、运维值守和交接清单，可作为本项目的同类交付经验参考，但不能替代本次招标文件中的强制要求。
""",
    ),
)

DEMO_REQUIREMENTS = (
    DemoRequirement(
        key="event-governance",
        document_key="rfp",
        section_key="technical-approach",
        text="建设覆盖事件上报、派单、改派、超时提醒、处理反馈和满意度评价的事件治理闭环。",
        heading="功能与技术要求",
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
        heading="功能与技术要求",
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
        heading="功能与技术要求",
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
        heading="实施与服务要求",
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
        heading="实施与服务要求",
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
        heading="评分与提交",
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
        quote="星河云智提供基于容器化部署的社区治理平台，支持 PostgreSQL、对象存储、标准 REST API、角色权限控制、操作审计和数据访问日志。",
        heading="平台能力",
        confidence=0.96,
        requirement_keys=("event-governance", "security-and-localization"),
    ),
    DemoEvidence(
        key="ai-security",
        document_key="supplier",
        quote="平台可对社区事件进行文本分类、趋势分析和处置建议生成。敏感配置采用服务端加密管理。",
        heading="AI 与安全",
        confidence=0.86,
        requirement_keys=("ai-capabilities", "security-and-localization"),
    ),
    DemoEvidence(
        key="delivery-experience",
        document_key="case-study",
        quote="交付团队在 12 周内完成需求梳理、核心原型、联调试运行和管理员培训。",
        heading="同类案例",
        confidence=0.78,
        requirement_keys=("delivery-milestones",),
    ),
)


def get_builtin_demo_document(storage_key: str) -> DemoDocument | None:
    """Resolve a private built-in document without depending on object storage."""

    if not storage_key.startswith(BUILTIN_DEMO_STORAGE_PREFIX):
        return None
    key = storage_key.removeprefix(BUILTIN_DEMO_STORAGE_PREFIX)
    return next((document for document in DEMO_DOCUMENTS if document.key == key), None)
