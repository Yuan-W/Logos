"""
TRPG Tools
==========
Tools for dice rolling and rule lookup in TRPG games.
"""

import re
import random
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Rulebook


@tool
def dice_roller(expression: str) -> dict:
    """
    Roll dice using standard RPG notation.
    
    Args:
        expression: Dice expression like "2d6+3", "1d20", "3d8-2"
    
    Returns:
        Dictionary with rolls, modifier, and total
    
    Examples:
        dice_roller("2d6+3") -> {"rolls": [4, 2], "modifier": 3, "total": 9}
        dice_roller("1d20") -> {"rolls": [17], "modifier": 0, "total": 17}
    """
    expression = expression.lower().replace(" ", "")
    
    # Parse expression: NdM+/-K
    pattern = r"^(\d+)d(\d+)([+-]\d+)?$"
    match = re.match(pattern, expression)
    
    if not match:
        return {"error": f"Invalid dice expression: {expression}", "total": 0}
    
    num_dice = int(match.group(1))
    die_size = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0
    
    # Roll the dice
    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    total = sum(rolls) + modifier
    
    return {
        "expression": expression,
        "rolls": rolls,
        "modifier": modifier,
        "total": total
    }


def create_rule_lookup(session: Session):
    """
    Factory function to create a rule_lookup tool with database session.
    
    In production, this would use pgvector similarity search.
    For now, uses basic text matching.
    """
    @tool
    def rule_lookup(query: str) -> str:
        """
        Search the rulebook for relevant rules.
        
        Args:
            query: Search query for rules (e.g., "combat", "stealth check")
        
        Returns:
            Relevant rule text from the rulebook
        """
        # In production: Use pgvector similarity search
        # For now: Basic ILIKE search
        stmt = select(Rulebook).where(
            Rulebook.content.ilike(f"%{query}%")
        ).limit(3)
        
        results = session.execute(stmt).scalars().all()
        
        if not results:
            return f"No specific rules found for '{query}'. Use GM discretion."
        
        rule_texts = []
        for rule in results:
            system = rule.meta.get("system", "generic") if rule.meta else "generic"
            rule_texts.append(f"[{system}] {rule.content}")
        
        return "\n\n".join(rule_texts)
    
    return rule_lookup
