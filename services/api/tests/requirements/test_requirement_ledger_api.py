import uuid

from app.db import SessionLocal
from app.models import (
    Bundle,
    Evidence,
    Organization,
    OrganizationMembership,
    Project,
    ProjectMember,
    RequirementItem,
    RequirementClaimLink,
    SourceDocument,
    User,
)
from app.requirements.repository import (
    get_project_for_org as get_requirement_project_for_org,
    get_requirement_for_org as get_requirement_for_org_repository,
    list_requirements_by_project,
)


def _create_project(client, name: str = "Ledger Project") -> str:
    response = client.post(
        "/projects",
        json={"name": name, "scenario_package": "bidpilot"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_create_filter_and_inspect_bid_requirement(client) -> None:
    project_id = _create_project(client)
    db = SessionLocal()
    try:
        bundle = Bundle(project_id=project_id, label="Tender package", source_type="upload")
        db.add(bundle)
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key="tests/tender.pdf",
            mime_type="application/pdf",
            checksum="c" * 64,
            original_filename="smart-community-tender.pdf",
        )
        db.add(source)
        db.commit()
        source_document_id = source.id
    finally:
        db.close()

    created = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "qualification",
            "requirement_text": "提供信息安全管理体系认证",
            "original_text": "投标人须提供有效的信息安全管理体系认证。",
            "priority": "high",
            "source_document_id": source_document_id,
            "source_locator_json": {"section": "3.2", "text_anchor": "信息安全管理体系认证"},
            "bid_profile": {
                "bid_category": "qualification",
                "is_mandatory": True,
                "score_weight": 5,
                "risk_level": "high",
            },
        },
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["lock_version"] == 1
    assert body["verification_status"] == "unverified"
    assert body["source_document_name"] == "smart-community-tender.pdf"
    assert body["bid_profile"]["bid_category"] == "qualification"
    assert body["bid_profile"]["coverage_status"] == "uncovered"
    requirement_id = body["id"]

    listed = client.get(
        "/requirements",
        params={
            "project_id": project_id,
            "bid_category": "qualification",
            "risk_level": "high",
            "coverage_status": "uncovered",
        },
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [requirement_id]

    detail = client.get(f"/requirements/{requirement_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["source_document_name"] == "smart-community-tender.pdf"
    assert detail.json()["source_locator_json"]["section"] == "3.2"


def test_requirement_patch_uses_optimistic_lock(client, default_user_id: str) -> None:
    project_id = _create_project(client, "Optimistic Lock Project")
    created = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "security",
            "requirement_text": "支持 RBAC",
            "priority": "high",
        },
    ).json()

    updated = client.patch(
        f"/requirements/{created['id']}",
        json={
            "lock_version": created["lock_version"],
            "verification_status": "verified",
            "owner_user_id": default_user_id,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["verification_status"] == "verified"
    assert updated.json()["lock_version"] == created["lock_version"] + 1

    stale = client.patch(
        f"/requirements/{created['id']}",
        json={"lock_version": created["lock_version"], "priority": "normal"},
    )
    assert stale.status_code == 409
    assert "changed" in stale.json()["detail"].lower()


def test_profile_only_update_advances_lock_and_invalidates_readiness_fingerprint(client) -> None:
    project_id = _create_project(client, "Profile Version Project")
    created = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "qualification",
            "requirement_text": "Provide a current ISO 27001 certificate",
            "bid_profile": {"is_mandatory": False},
        },
    ).json()

    before = client.get(f"/readiness/projects/{project_id}")
    assert before.status_code == 200, before.text
    assert before.json()["counts"]["mandatory"] == 0

    updated = client.patch(
        f"/requirements/{created['id']}",
        json={
            "lock_version": created["lock_version"],
            "bid_profile": {"is_mandatory": True},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["lock_version"] == created["lock_version"] + 1

    after = client.get(f"/readiness/projects/{project_id}")
    assert after.status_code == 200, after.text
    assert after.json()["counts"]["mandatory"] == 1
    assert after.json()["source_fingerprint"] != before.json()["source_fingerprint"]

    stale = client.patch(
        f"/requirements/{created['id']}",
        json={
            "lock_version": created["lock_version"],
            "bid_profile": {"risk_level": "critical"},
        },
    )
    assert stale.status_code == 409


def test_requirement_routes_hide_other_organization_projects(client) -> None:
    db = SessionLocal()
    try:
        org_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        requirement_id = str(uuid.uuid4())
        db.add(Organization(id=org_id, slug=f"other-{org_id[:8]}", name="Other Org"))
        db.add(
            Project(
                id=project_id,
                org_id=org_id,
                slug=f"other-project-{project_id[:8]}",
                name="Other Project",
                scenario_package="bidpilot",
            )
        )
        db.flush()
        db.add(
            RequirementItem(
                id=requirement_id,
                project_id=project_id,
                section_key="secret",
                requirement_text="Other tenant requirement",
            )
        )
        db.commit()
    finally:
        db.close()

    listed = client.get("/requirements", params={"project_id": project_id})
    detail = client.get(f"/requirements/{requirement_id}")
    updated = client.patch(
        f"/requirements/{requirement_id}",
        json={"lock_version": 1, "priority": "high"},
    )

    assert listed.status_code == 404
    assert detail.status_code == 404
    assert updated.status_code == 404


def test_requirement_repository_hides_soft_deleted_projects(
    client,
    default_org_id: str,
) -> None:
    project_id = _create_project(client, "Soft Deleted Requirement Project")
    created = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "scope",
            "requirement_text": "This requirement must remain hidden after deletion.",
        },
    )
    assert created.status_code == 201, created.text
    requirement_id = created.json()["id"]

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        assert project is not None
        project.status = "deleted"
        db.commit()

        assert get_requirement_project_for_org(db, project_id, default_org_id) is None
        assert list_requirements_by_project(db, project_id, default_org_id) == []
        assert get_requirement_for_org_repository(db, requirement_id, default_org_id) is None
    finally:
        db.close()


def test_evidence_link_updates_derived_readiness_state(client, default_user_id: str) -> None:
    project_id = _create_project(client, "Evidence Link Project")
    requirement = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "security",
            "requirement_text": "提供信息安全认证",
            "priority": "high",
            "bid_profile": {"bid_category": "qualification", "is_mandatory": True},
        },
    ).json()

    db = SessionLocal()
    try:
        bundle = Bundle(project_id=project_id, label="Supplier evidence", source_type="upload")
        db.add(bundle)
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key="tests/certificate.pdf",
            mime_type="application/pdf",
            checksum="a" * 64,
            original_filename="certificate.pdf",
        )
        db.add(source)
        db.flush()
        evidence = Evidence(
            project_id=project_id,
            source_document_id=source.id,
            quote_text="ISO 27001 certification",
            locator_json={"page": 1},
            confidence=0.98,
        )
        db.add(evidence)
        db.commit()
        evidence_id = evidence.id
    finally:
        db.close()

    linked = client.post(
        f"/requirements/{requirement['id']}/evidence",
        json={"evidence_id": evidence_id, "relation_type": "supports"},
    )
    assert linked.status_code == 201, linked.text
    link_id = linked.json()["id"]

    detail = client.get(f"/requirements/{requirement['id']}").json()
    assert detail["bid_profile"]["coverage_status"] == "partial"
    assert detail["bid_profile"]["evidence_status"] == "weak"
    assert detail["evidence_links"][0]["quote_text"] == "ISO 27001 certification"
    assert detail["evidence_links"][0]["source_document_name"] == "certificate.pdf"

    verified = client.patch(
        f"/requirements/{requirement['id']}/evidence/{link_id}",
        json={"verification_status": "verified"},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verification_status"] == "verified"

    refreshed = client.get(f"/requirements/{requirement['id']}").json()
    assert refreshed["bid_profile"]["coverage_status"] == "partial"
    assert refreshed["bid_profile"]["evidence_status"] == "sufficient"


def test_admin_can_approve_not_applicable_decision(
    client,
    default_org_id: str,
    default_user_id: str,
) -> None:
    db = SessionLocal()
    try:
        reviewer = User(
            id=str(uuid.uuid4()),
            org_id=default_org_id,
            email=f"reviewer-{uuid.uuid4().hex[:8]}@example.test",
            display_name="Reviewer",
            password_hash="test-only",
            email_verified=True,
        )
        db.add(reviewer)
        db.flush()
        db.add(
            OrganizationMembership(
                org_id=default_org_id,
                user_id=reviewer.id,
                role="member",
            )
        )
        db.commit()
        reviewer_id = reviewer.id
    finally:
        db.close()

    project_id = _create_project(client, "Decision Project")
    db = SessionLocal()
    try:
        db.add(ProjectMember(project_id=project_id, user_id=reviewer_id, role="reviewer"))
        db.commit()
    finally:
        db.close()
    requirement = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "scope",
            "requirement_text": "Optional legacy integration",
            "reviewer_user_id": reviewer_id,
            "bid_profile": {"bid_category": "technical"},
        },
    ).json()

    requested = client.post(
        f"/requirements/{requirement['id']}/decisions",
        json={"decision_type": "not_applicable", "rationale": "Not used by this project"},
    )
    assert requested.status_code == 201, requested.text

    approved = client.post(
        f"/requirements/{requirement['id']}/decisions/{requested.json()['id']}/approve"
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    detail = client.get(f"/requirements/{requirement['id']}").json()
    assert detail["bid_profile"]["coverage_status"] == "not_applicable"
    assert detail["bid_profile"]["evidence_status"] == "not_required"


def test_bulk_assignment_validates_versions_and_organization(
    client,
    default_org_id: str,
    default_user_id: str,
) -> None:
    db = SessionLocal()
    try:
        assignee = User(
            id=str(uuid.uuid4()),
            org_id=default_org_id,
            email=f"assignee-{uuid.uuid4().hex[:8]}@example.test",
            display_name="Assignee",
            password_hash="test-only",
            email_verified=True,
        )
        db.add(assignee)
        db.flush()
        db.add(
            OrganizationMembership(
                org_id=default_org_id,
                user_id=assignee.id,
                role="member",
            )
        )
        db.commit()
        assignee_id = assignee.id
    finally:
        db.close()

    project_id = _create_project(client, "Bulk Assignment Project")
    db = SessionLocal()
    try:
        db.add(ProjectMember(project_id=project_id, user_id=assignee_id, role="contributor"))
        db.commit()
    finally:
        db.close()
    requirements = [
        client.post(
            "/requirements",
            json={
                "project_id": project_id,
                "section_key": f"section-{index}",
                "requirement_text": f"Requirement {index}",
            },
        ).json()
        for index in range(2)
    ]

    assigned = client.post(
        "/requirements/bulk-assign",
        json={
            "requirement_ids": [item["id"] for item in requirements],
            "lock_versions": {item["id"]: item["lock_version"] for item in requirements},
            "owner_user_id": assignee_id,
        },
    )
    assert assigned.status_code == 200, assigned.text
    assert {item["owner_user_id"] for item in assigned.json()} == {assignee_id}
    assert {item["status"] for item in assigned.json()} == {"assigned"}

    stale = client.post(
        "/requirements/bulk-assign",
        json={
            "requirement_ids": [requirements[0]["id"]],
            "lock_versions": {requirements[0]["id"]: requirements[0]["lock_version"]},
            "reviewer_user_id": assignee_id,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == {
        "code": "requirements_changed",
        "requirement_ids": [requirements[0]["id"]],
    }

    unassigned = client.post(
        "/requirements/bulk-assign",
        json={
            "requirement_ids": [item["id"] for item in assigned.json()],
            "lock_versions": {
                item["id"]: item["lock_version"] for item in assigned.json()
            },
            "owner_user_id": None,
        },
    )
    assert unassigned.status_code == 200, unassigned.text
    assert {item["owner_user_id"] for item in unassigned.json()} == {None}
    assert {item["status"] for item in unassigned.json()} == {"untriaged"}


def test_verified_evidence_backed_claim_closes_requirement(
    client,
    default_user_id: str,
) -> None:
    project_id = _create_project(client, "Claim Trace Project")
    requirement = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "security",
            "requirement_text": "敏感信息应加密存储",
            "reviewer_user_id": default_user_id,
            "bid_profile": {
                "bid_category": "technical",
                "is_mandatory": True,
                "risk_level": "high",
            },
        },
    ).json()

    db = SessionLocal()
    try:
        bundle = Bundle(project_id=project_id, label="Security evidence", source_type="upload")
        db.add(bundle)
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key="tests/security.md",
            mime_type="text/markdown",
            checksum="b" * 64,
            original_filename="security.md",
        )
        db.add(source)
        db.flush()
        evidence = Evidence(
            project_id=project_id,
            source_document_id=source.id,
            quote_text="AES-256 encryption at rest is enabled.",
            locator_json={"section": "Security controls"},
            confidence=0.99,
        )
        db.add(evidence)
        db.commit()
        evidence_id = evidence.id
    finally:
        db.close()

    linked = client.post(
        f"/requirements/{requirement['id']}/evidence",
        json={"evidence_id": evidence_id},
    ).json()
    client.patch(
        f"/requirements/{requirement['id']}/evidence/{linked['id']}",
        json={"verification_status": "verified"},
    )

    claim = client.post(
        f"/requirements/{requirement['id']}/claims",
        json={
            "claim_text": "平台对静态敏感数据采用 AES-256 加密。",
            "claim_type": "factual",
            "evidence_ids": [evidence_id],
        },
    )
    assert claim.status_code == 201, claim.text
    assert claim.json()["status"] == "draft"

    verified = client.post(
        f"/requirements/{requirement['id']}/claims/{claim.json()['id']}/verify"
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verified"

    detail = client.get(f"/requirements/{requirement['id']}").json()
    assert detail["bid_profile"]["coverage_status"] == "covered"
    assert detail["bid_profile"]["evidence_status"] == "sufficient"
    assert detail["claims"][0]["claim_text"].startswith("平台对静态")
    assert detail["claims"][0]["evidence_ids"] == [evidence_id]


def test_factual_claim_cannot_be_verified_without_evidence(
    client,
    default_user_id: str,
) -> None:
    project_id = _create_project(client, "Unsupported Claim Project")
    requirement = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "security",
            "requirement_text": "支持国密算法",
            "reviewer_user_id": default_user_id,
            "bid_profile": {"bid_category": "technical", "is_mandatory": True},
        },
    ).json()
    claim = client.post(
        f"/requirements/{requirement['id']}/claims",
        json={"claim_text": "平台全面支持国密算法。", "claim_type": "factual"},
    )
    assert claim.status_code == 201, claim.text

    verified = client.post(
        f"/requirements/{requirement['id']}/claims/{claim.json()['id']}/verify"
    )
    assert verified.status_code == 409
    assert "evidence" in verified.json()["detail"].lower()


def test_multi_requirement_claim_requires_verified_evidence_for_every_requirement(
    client,
    default_user_id: str,
) -> None:
    project_id = _create_project(client, "Shared Claim Verification Project")
    requirement_one = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "security",
            "requirement_text": "Sensitive data must be encrypted at rest.",
            "reviewer_user_id": default_user_id,
            "bid_profile": {"is_mandatory": True},
        },
    ).json()
    requirement_two = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "security",
            "requirement_text": "Stored data must use approved encryption controls.",
            "reviewer_user_id": default_user_id,
            "bid_profile": {"is_mandatory": True},
        },
    ).json()

    db = SessionLocal()
    try:
        bundle = Bundle(project_id=project_id, label="Shared security evidence", source_type="upload")
        db.add(bundle)
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key="tests/shared-security.md",
            mime_type="text/markdown",
            checksum="d" * 64,
            original_filename="shared-security.md",
        )
        db.add(source)
        db.flush()
        evidence = Evidence(
            project_id=project_id,
            source_document_id=source.id,
            quote_text="AES-256 encryption is enabled for all stored data.",
            locator_json={"section": "Encryption"},
        )
        db.add(evidence)
        db.commit()
        evidence_id = evidence.id
    finally:
        db.close()

    link_one = client.post(
        f"/requirements/{requirement_one['id']}/evidence",
        json={"evidence_id": evidence_id},
    ).json()
    link_two = client.post(
        f"/requirements/{requirement_two['id']}/evidence",
        json={"evidence_id": evidence_id},
    ).json()
    first_verified = client.patch(
        f"/requirements/{requirement_one['id']}/evidence/{link_one['id']}",
        json={"verification_status": "verified"},
    )
    assert first_verified.status_code == 200, first_verified.text

    created_claim = client.post(
        f"/requirements/{requirement_one['id']}/claims",
        json={
            "claim_text": "All stored data uses AES-256 encryption.",
            "claim_type": "factual",
            "evidence_ids": [evidence_id],
        },
    )
    assert created_claim.status_code == 201, created_claim.text
    claim_id = created_claim.json()["id"]

    db = SessionLocal()
    try:
        db.add(RequirementClaimLink(requirement_id=requirement_two["id"], claim_id=claim_id))
        db.commit()
    finally:
        db.close()

    premature = client.post(f"/requirements/{requirement_one['id']}/claims/{claim_id}/verify")
    assert premature.status_code == 409
    assert "every linked requirement" in premature.json()["detail"]

    second_verified = client.patch(
        f"/requirements/{requirement_two['id']}/evidence/{link_two['id']}",
        json={"verification_status": "verified"},
    )
    assert second_verified.status_code == 200, second_verified.text
    verified = client.post(f"/requirements/{requirement_one['id']}/claims/{claim_id}/verify")
    assert verified.status_code == 200, verified.text

    for requirement_id in (requirement_one["id"], requirement_two["id"]):
        detail = client.get(f"/requirements/{requirement_id}").json()
        assert detail["bid_profile"]["coverage_status"] == "covered"
        assert detail["claims"][0]["status"] == "verified"
