"""Módulo de interactividad tipo Photomath para IntegralLab."""

from integrallab.ui.photomath.region_detector import RegionDetector  # noqa: F401
from integrallab.ui.photomath.step_extractor import StepExtractor  # noqa: F401
from integrallab.ui.photomath.click_handler import PhotomathClickHandler  # noqa: F401

__all__ = [
    "RegionDetector",
    "StepExtractor",
    "PhotomathClickHandler",
]