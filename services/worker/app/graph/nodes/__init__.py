"""BidPilot graph nodes.

Re-exports every node function and routing helper so consumers can do::

    from app.graph.nodes import supervisor_node, section_drafter_node, ...
"""

from .supervisor import (
    supervisor_node,
    route_initial,
    route_after_rfp,
    route_after_retrieval,
    route_after_draft,
    route_after_review,
    route_after_human_approval,
)
from .rfp_parser import rfp_parser_node
from .knowledge_retriever import knowledge_retriever_node
from .section_drafter import section_drafter_node
from .quality_reviewer import quality_reviewer_node
from .human_approval import human_approval_node
from .persist_result import persist_result_node
from ._history import record_agent_call, with_history

__all__ = [
    # Nodes
    "supervisor_node",
    "rfp_parser_node",
    "knowledge_retriever_node",
    "section_drafter_node",
    "quality_reviewer_node",
    "human_approval_node",
    "persist_result_node",
    # Routing helpers
    "route_initial",
    "route_after_rfp",
    "route_after_retrieval",
    "route_after_draft",
    "route_after_review",
    "route_after_human_approval",
    # History utilities
    "record_agent_call",
    "with_history",
]
