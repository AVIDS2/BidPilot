import pytest
from pydantic import ValidationError

from contracts.memory import (
    MemoryCitation,
    MemoryContextItem,
    MemoryContextPack,
    MemoryKind,
    MemoryProposal,
    MemoryProposalOrigin,
    MemoryScope,
)


def _citation() -> MemoryCitation:
    return MemoryCitation(
        source_type="knowledge_chunk",
        source_id="chunk-1",
        label="招标技术规范，第 3 节",
    )


def test_project_shared_proposal_requires_a_project_id() -> None:
    with pytest.raises(ValidationError, match="project-shared memory requires project_id"):
        MemoryProposal(
            org_id="org-1",
            scope=MemoryScope.PROJECT_SHARED,
            kind=MemoryKind.FACT,
            title="部署要求",
            body_markdown="系统需要私有化部署。",
            origin=MemoryProposalOrigin.SYSTEM,
            evidence_ids=["chunk-1"],
        )


def test_user_private_proposal_requires_an_owner() -> None:
    with pytest.raises(ValidationError, match="user-private memory requires owner_user_id"):
        MemoryProposal(
            org_id="org-1",
            project_id="project-1",
            scope=MemoryScope.USER_PRIVATE,
            kind=MemoryKind.PREFERENCE,
            title="偏好",
            body_markdown="优先使用简洁表述。",
            origin=MemoryProposalOrigin.USER,
        )


def test_system_proposal_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="system-generated memory requires evidence_ids"):
        MemoryProposal(
            org_id="org-1",
            project_id="project-1",
            scope=MemoryScope.PROJECT_SHARED,
            kind=MemoryKind.FACT,
            title="无来源事实",
            body_markdown="没有出处的事实不能写入记忆。",
            origin=MemoryProposalOrigin.SYSTEM,
        )


def test_memory_contract_rejects_unknown_scope_and_empty_context_provenance() -> None:
    with pytest.raises(ValidationError):
        MemoryProposal(
            org_id="org-1",
            scope="global",
            kind=MemoryKind.FACT,
            title="错误作用域",
            body_markdown="内容",
            origin=MemoryProposalOrigin.USER,
        )

    with pytest.raises(ValidationError, match="memory context item requires provenance"):
        MemoryContextItem(
            record_id="memory-1",
            title="部署要求",
            body_markdown="系统需要私有化部署。",
            scope=MemoryScope.PROJECT_SHARED,
            kind=MemoryKind.FACT,
        )


def test_context_pack_requires_a_version_and_keeps_citations() -> None:
    item = MemoryContextItem(
        record_id="memory-1",
        title="部署要求",
        body_markdown="系统需要私有化部署。",
        scope=MemoryScope.PROJECT_SHARED,
        kind=MemoryKind.FACT,
        citations=[_citation()],
    )
    pack = MemoryContextPack(
        org_id="org-1",
        user_id="user-1",
        project_id="project-1",
        memory_version="memory-v1",
        items=[item],
    )

    assert pack.items[0].citations[0].source_id == "chunk-1"
