"""Structured, provider-neutral vehicle/listing analysis."""

from typing import Any

from autofinder.analysis.models import VehicleAnalysis

__all__ = ["VehicleAnalysis", "VehicleAnalysisResult", "VehicleAnalyzer"]


def __getattr__(name: str) -> Any:
    """Avoid importing AI-facing services when callers need only analysis models."""
    if name in {"VehicleAnalyzer", "VehicleAnalysisResult"}:
        from autofinder.analysis.analyzer import VehicleAnalyzer, VehicleAnalysisResult

        return {"VehicleAnalyzer": VehicleAnalyzer, "VehicleAnalysisResult": VehicleAnalysisResult}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
