"""Parametric, printable gecko-hide generator."""

from .config import GeckoHideConfig
from .contour import AppearanceSettings, ContourDesign, ContourLevel, load_design, save_design, scale_design
from .generator import generate_contour_gecko_hide, generate_gecko_hide, generate_profile_gecko_hide
from .profile import ProfileDesign, load_profile, save_profile

__all__ = [
    "ContourDesign",
    "AppearanceSettings",
    "ContourLevel",
    "GeckoHideConfig",
    "ProfileDesign",
    "generate_contour_gecko_hide",
    "generate_gecko_hide",
    "generate_profile_gecko_hide",
    "load_design",
    "load_profile",
    "save_design",
    "scale_design",
    "save_profile",
]
