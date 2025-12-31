"""
Gemini Ingestion Flavors
========================
Defines the extraction prompts and logic for different content types.
Used by the GeminiIngestor to prompt the Vision Model.
"""

from typing import Dict, Any
from enum import Enum

class IngestFlavor(Enum):
    TRPG = "trpg"
    RESEARCH = "research"
    NOVEL = "novel"
    GENERIC = "generic"


# =============================================================================
# Extraction Prompts
# =============================================================================

TRPG_PROMPT = """
You are a RPG System Expert.
Analyze this page from a rulebook. 
If you see a Monster Stat Block, Spell, Item, or Class Feature, extract it into structured JSON.
If there are multiple items, extract all of them.

JSON Structure:
{
  "content": "Full markdown text of the page, including tables converted to markdown.",
  "stat_blocks": [
    {
       "name": "Goblin",
       "type": "monster",
       "stats": { "hp": 7, "ac": 15, "cr": "1/4", "actions": [...] }
    }
  ]
}

If no specific stat block found, return empty "stat_blocks" list and just the markdown "content".
"""

RESEARCH_PROMPT = """
You are a Data Analyst.
Analyze this page from a research paper or document.
Extract any Charts, Graphs, or Data Tables into structured JSON.
Also provide the full text in Markdown.

JSON Structure:
{
  "content": "Full markdown text of the page.",
  "stat_blocks": [
    {
       "label": "Figure 1: Growth Rates",
       "type": "chart",
       "data": { "x_axis": [...], "y_axis": [...] },
       "insight": "Brief summary of what this chart proves."
    }
  ]
}
"""

NOVEL_PROMPT = """
You are a World Builder.
Analyze this page from a world setting book or novel bible.
Extract Character Bios, Location Descriptions, or Lore Events.

JSON Structure:
{
  "content": "Full markdown text.",
  "stat_blocks": [
    {
       "name": "Count Dracula",
       "type": "character",
       "bio": "...",
       "relationships": ["Van Helsing (Enemy)"]
    }
  ]
}
"""

GENERIC_PROMPT = """
Analyze this page.
Convert everything to Markdown text.
If you see structured tables, try to represent them as JSON in stat_blocks.

JSON Structure:
{
  "content": "Markdown text...",
  "stat_blocks": []
}
"""

# =============================================================================
# Registry
# =============================================================================

PROMPT_MAP: Dict[IngestFlavor, str] = {
    IngestFlavor.TRPG: TRPG_PROMPT,
    IngestFlavor.RESEARCH: RESEARCH_PROMPT,
    IngestFlavor.NOVEL: NOVEL_PROMPT,
    IngestFlavor.GENERIC: GENERIC_PROMPT
}

def get_prompt_for_flavor(flavor: str) -> str:
    try:
        enum_val = IngestFlavor(flavor.lower())
        return PROMPT_MAP[enum_val]
    except ValueError:
        return GENERIC_PROMPT
