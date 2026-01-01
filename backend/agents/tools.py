"""
TRPG Tools
==========
Tools for dice rolling, rule lookup, and character state management.
"""

import re
import random
from typing import Optional, Any

from langchain_core.tools import tool
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.database.models import RuleBookChunk, Character
from backend.database.db_init import get_session


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


@tool
def update_character(character_id: int, field: str, value: Any) -> str:
    """
    Update a character's stat (HP, conditions, inventory) in the database.
    Changes persist across sessions.
    
    Args:
        character_id: The ID of the character to update.
        field: The field to update (e.g., "hp", "conditions", "gold").
        value: The new value for the field.
    
    Returns:
        Confirmation message.
    """
    session = get_session()
    try:
        stmt = select(Character).where(Character.id == character_id)
        character = session.execute(stmt).scalar_one_or_none()
        
        if not character:
            return f"Error: Character with ID {character_id} not found."
        
        # Update current_status JSONB
        current_status = dict(character.current_status) if character.current_status else {}
        current_status[field] = value
        character.current_status = current_status
        
        session.commit()
        
        return f"Updated {character.name}'s {field} to {value}."
    except Exception as e:
        return f"Error updating character: {e}"
    finally:
        session.close()


@tool
def lookup_stats(query: str) -> str:
    """
    Look up precise numerical stats (HP, AC, CR, Damage) for monsters or spells.
    Retrieves structured JSON data from the RuleBookChunk table.
    Use this for specific mechanics questions.
    
    Args:
        query: Name of the entity (e.g., "Goblin", "Fireball")
    
    Returns:
        JSON string with the stat block, or "Not found".
    """
    session = get_session()
    try:
        # JSONB search or content ILIKE
        sql = text("""
            SELECT stat_block FROM rulebook_chunks 
            WHERE content ILIKE :q 
            LIMIT 1
        """)
        result = session.execute(sql, {"q": f"%{query}%"}).scalar()
        
        if result:
            return str(result)
        return f"No stats found for '{query}'."
    finally:
        session.close()


def create_rule_lookup(session: Session):
    """
    Factory function to create a rule_lookup tool with database session.
    Uses RuleBookChunk for semantic search on lore/text.
    """
    from backend.utils.ingestion import get_embedding
    
    @tool
    def rule_lookup(query: str) -> str:
        """
        Search the rulebook for lore, rules descriptions, and general game text.
        Use this for "how does X work?" questions.
        
        Args:
            query: Search query for rules (e.g., "how does sneak attack work?")
        
        Returns:
            Relevant rule text from the rulebook.
        """
        # Use semantic search on RuleBookChunk
        query_vec = get_embedding(query)
        
        stmt = select(RuleBookChunk).order_by(
            RuleBookChunk.embedding.cosine_distance(query_vec)
        ).limit(3)
        
        results = session.execute(stmt).scalars().all()
        
        if not results:
            return f"No specific rules found for '{query}'. Use GM discretion."
        
        rule_texts = []
        for chunk in results:
            meta = chunk.source_metadata or {}
            source = meta.get("source_file", "Rulebook")
            page = meta.get("page_num", "?")
            rule_texts.append(f"[{source} p.{page}]\n{chunk.content}")
        
        return "\n\n---\n\n".join(rule_texts)
    
    return rule_lookup
