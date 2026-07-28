"""Integration tests for the BidPilot LangGraph agent graph."""

import pytest
from app.graph import builder
from app.graph.builder import graph, invoke_graph
from app.runtime.events import RuntimeCancellationRequested


class TestGraphCompilation:
    def test_graph_compiles_without_error(self):
        """Verify the graph compiles successfully."""
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        """Verify all expected nodes are registered."""
        nodes = list(graph.get_graph().nodes)
        expected = {
            "supervisor",
            "rfp_parser",
            "knowledge_retriever",
            "content_plan",
            "section_drafter",
            "quality_reviewer",
            "persist_result",
        }
        assert expected.issubset(set(nodes))


class TestGraphInvocation:
    def test_knowledge_retrieval_payload_contains_only_safe_numeric_metrics(self):
        payload = builder._node_payload(
            "knowledge_retriever",
            {
                "evidence_chunks": [{"content": "must not leave the node"}],
                "retrieval_candidate_count": 3,
                "retrieval_fused_candidate_count": 7,
                "retrieval_reranked_candidate_count": 4,
                "retrieval_latency_ms": 21,
                "query": "must not become an event field",
            },
        )

        assert payload == {
            "evidence_count": 1,
            "retrieval_candidate_count": 3,
            "retrieval_fused_candidate_count": 7,
            "retrieval_reranked_candidate_count": 4,
            "retrieval_latency_ms": 21,
        }

    def test_instrumented_node_stops_at_the_first_safe_boundary_after_cancellation(self, monkeypatch):
        """A cancellation arriving during a node prevents the next graph transition."""
        cancellation_checks = iter([False, True])
        published = []

        monkeypatch.setattr(
            builder,
            "is_runtime_cancellation_requested",
            lambda _runtime_run_id: next(cancellation_checks),
        )
        monkeypatch.setattr(builder, "publish_node_started", lambda *_args: published.append("started"))
        monkeypatch.setattr(builder, "publish_node_succeeded", lambda *_args: published.append("succeeded"))
        monkeypatch.setattr(builder, "publish_cancellation_detected", lambda *_args: published.append("cancelled"))

        wrapped = builder._instrument_node("section_drafter", lambda _state: {"draft_created": True})

        with pytest.raises(RuntimeCancellationRequested):
            wrapped({"runtime_run_id": "runtime-cancel-boundary"})

        assert published == ["started", "cancelled"]

    def test_invoke_graph_with_defaults(self):
        """Test invoke_graph convenience function creates proper initial state."""
        # This would need full DB mocking to actually run
        # Verify the function exists and accepts the right parameters
        import inspect
        sig = inspect.signature(invoke_graph)
        params = list(sig.parameters.keys())
        assert "project_id" in params
        assert "section_key" in params
        assert "run_id" in params
        assert "provider_config_id" in params
        assert "input_review_feedback" in params
        assert "review_feedback" in params  # backward compat
        assert "max_iterations" in params
