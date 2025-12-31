"""
TRPG Plugins Package
"""

from src.plugins.trpg_base import TRPGSystemPlugin, MechanicsResult, ActionResultType
from src.plugins.coc_plugin import CallOfCthulhuPlugin
from src.plugins.bitd_plugin import BladesInTheDarkPlugin

__all__ = [
    "TRPGSystemPlugin",
    "MechanicsResult",
    "ActionResultType",
    "CallOfCthulhuPlugin",
    "BladesInTheDarkPlugin",
]
