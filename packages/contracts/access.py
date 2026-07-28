"""Shared project-role capability policy for API and Worker enforcement."""

from __future__ import annotations


PROJECT_CAPABILITIES = frozenset(
    {
        "project.read",
        "project.manage",
        "project.delete",
        "project.members.manage",
        "requirements.write",
        "requirements.assign",
        "requirements.review",
        "bundles.write",
        "memory.read",
        "memory.propose",
        "memory.approve",
        "workflow.run",
        "review.write",
        "deliverables.export",
    }
)


ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "owner": PROJECT_CAPABILITIES,
    "manager": frozenset(
        {
            "project.read",
            "project.manage",
            "requirements.write",
            "requirements.assign",
            "requirements.review",
            "bundles.write",
            "memory.read",
            "memory.propose",
            "memory.approve",
            "workflow.run",
            "review.write",
            "deliverables.export",
        }
    ),
    "contributor": frozenset(
        {
            "project.read",
            "requirements.write",
            "bundles.write",
            "memory.read",
            "memory.propose",
            "workflow.run",
        }
    ),
    "reviewer": frozenset(
        {
            "project.read",
            "memory.read",
            "requirements.review",
            "review.write",
            "deliverables.export",
        }
    ),
    "viewer": frozenset({"project.read", "memory.read"}),
}


def project_role_has_capability(role: str, capability: str) -> bool:
    """Return whether one persisted project role grants a known capability."""
    if capability not in PROJECT_CAPABILITIES:
        raise ValueError(f"Unknown project capability: {capability}")
    return capability in ROLE_CAPABILITIES.get(role, frozenset())


__all__ = ["PROJECT_CAPABILITIES", "ROLE_CAPABILITIES", "project_role_has_capability"]
