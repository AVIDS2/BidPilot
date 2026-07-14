"""Offline evaluation primitives for BidPilot quality gates."""

from .metrics import BidBenchMetrics, score_candidate

__all__ = ["BidBenchMetrics", "score_candidate"]
