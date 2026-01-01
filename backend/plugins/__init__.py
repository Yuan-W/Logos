"""
TRPG Plugins Package
"""

from backend.plugins.trpg_base import TRPGSystemPlugin, MechanicsResult, ActionResultType
from backend.plugins.coc_plugin import CallOfCthulhuPlugin
from backend.plugins.bitd_plugin import BladesInTheDarkPlugin

__all__ = [
    "TRPGSystemPlugin",
    "MechanicsResult",
    "ActionResultType",
    "CallOfCthulhuPlugin",
    "BladesInTheDarkPlugin",
]
