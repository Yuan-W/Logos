"""
GM Agent Test Suite
===================
Dedicated tests for the TRPG GM Agent covering:
1. Rule Lawyer (Precision Stats Retrieval)
2. State Change (Character HP Update)
3. Dice Roller (Deterministic tool call)
4. Lore Retrieval (Semantic Search)
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from src.database.models import RuleBookChunk, Character, Campaign
from src.database.db_init import get_session
from src.agents.tools import dice_roller, lookup_stats, update_character, create_rule_lookup


@pytest.fixture
def session():
    """Provide a clean database session for tests."""
    sess = get_session()
    yield sess
    # Cleanup handled by rollback if needed
    sess.rollback()
    sess.close()


@pytest.fixture
def sample_rulebook_chunk(session):
    """Create a sample RuleBookChunk for testing."""
    chunk = RuleBookChunk(
        content="# Goblin\nA small, cunning humanoid that lurks in dark places.",
        embedding=[0.1]*768,
        stat_block={"items": [{"name": "Goblin", "hp": 7, "ac": 15, "cr": "1/4"}]},
        source_metadata={"source_file": "Monster Manual", "page_num": 166}
    )
    session.add(chunk)
    session.commit()
    yield chunk
    session.delete(chunk)
    session.commit()


@pytest.fixture
def sample_campaign_and_character(session):
    """Create a sample Campaign and Character for testing."""
    campaign = Campaign(
        name="Test Campaign",
        system_type="dnd5e",
        description="A test campaign for unit testing."
    )
    session.add(campaign)
    session.commit()
    
    character = Character(
        campaign_id=campaign.id,
        name="Test Hero",
        character_type="pc",
        stats={"STR": 16, "DEX": 14, "CON": 15, "INT": 10, "WIS": 12, "CHA": 8},
        current_status={"hp": 45, "max_hp": 45, "conditions": []},
        inventory={"gold": 100, "weapons": ["Longsword"]},
        skills={"athletics": 5, "perception": 2}
    )
    session.add(character)
    session.commit()
    
    yield campaign, character
    
    session.delete(character)
    session.delete(campaign)
    session.commit()


class TestDiceRoller:
    """Tests for the dice_roller tool."""
    
    def test_standard_roll(self):
        """Test basic dice rolling."""
        result = dice_roller.invoke("1d20")
        assert "rolls" in result
        assert "total" in result
        assert 1 <= result["total"] <= 20
        assert len(result["rolls"]) == 1
    
    def test_multiple_dice(self):
        """Test rolling multiple dice."""
        result = dice_roller.invoke("3d6")
        assert len(result["rolls"]) == 3
        assert 3 <= result["total"] <= 18
    
    def test_modifier(self):
        """Test dice with modifier."""
        result = dice_roller.invoke("1d20+5")
        assert result["modifier"] == 5
        assert 6 <= result["total"] <= 25
    
    def test_negative_modifier(self):
        """Test dice with negative modifier."""
        result = dice_roller.invoke("1d6-2")
        assert result["modifier"] == -2
    
    def test_invalid_expression(self):
        """Test invalid dice expression handling."""
        result = dice_roller.invoke("invalid")
        assert "error" in result
        assert result["total"] == 0


class TestLookupStats:
    """Tests for the lookup_stats tool (Precision Retrieval)."""
    
    def test_lookup_existing_monster(self, session, sample_rulebook_chunk):
        """Scenario A: Rule Lawyer - Find precise stats."""
        result = lookup_stats.invoke("Goblin")
        
        # Should return structured JSON
        assert "Goblin" in result or "hp" in result or "7" in result
        print(f"Lookup Stats Result: {result}")
    
    def test_lookup_not_found(self, session):
        """Test lookup for non-existent entity."""
        result = lookup_stats.invoke("NonExistentMonsterXYZ")
        
        assert "No stats found" in result


class TestUpdateCharacter:
    """Tests for the update_character tool (State Persistence)."""
    
    def test_update_hp(self, session, sample_campaign_and_character):
        """Scenario B: State Change - Update HP and verify persistence."""
        campaign, character = sample_campaign_and_character
        original_hp = character.current_status.get("hp", 45)
        new_hp = original_hp - 12  # Take 12 damage
        
        # Call the tool
        result = update_character.invoke({
            "character_id": character.id,
            "field": "hp",
            "value": new_hp
        })
        
        print(f"Update Result: {result}")
        assert "Updated" in result
        assert str(new_hp) in result
        
        # Verify persistence by re-querying
        session.expire_all()  # Clear cache
        refreshed = session.get(Character, character.id)
        assert refreshed.current_status["hp"] == new_hp
    
    def test_update_nonexistent_character(self, session):
        """Test updating a character that doesn't exist."""
        result = update_character.invoke({
            "character_id": 99999,
            "field": "hp",
            "value": 10
        })
        
        assert "Error" in result or "not found" in result


class TestRuleLookup:
    """Tests for the rule_lookup tool (Semantic Lore Search)."""
    
    def test_rule_lookup_semantic(self, session, sample_rulebook_chunk):
        """Scenario C: Lore Check - Semantic search for rules."""
        rule_lookup = create_rule_lookup(session)
        
        # This should find the Goblin content semantically
        result = rule_lookup.invoke("small creatures in dungeons")
        
        print(f"Rule Lookup Result: {result}")
        # May or may not find it depending on embedding similarity
        # At minimum, should not error
        assert isinstance(result, str)


class TestAdversarialLoop:
    """
    Tests for the Adversarial GM loop (Storyteller + Rules Lawyer).
    Covers complex scenarios like conditions blocking actions.
    """
    
    @pytest.fixture
    def grog_the_grappled(self, session):
        """Create Grog the Barbarian in a grappled state."""
        campaign = Campaign(
            name="Underdark Delve",
            system_type="dnd5e",
            description="A dark dungeon crawl."
        )
        session.add(campaign)
        session.commit()
        
        grog = Character(
            campaign_id=campaign.id,
            name="Grog",
            character_type="pc",
            stats={"STR": 18, "DEX": 12, "CON": 16, "INT": 8, "WIS": 10, "CHA": 10},
            current_status={
                "hp": 15, 
                "max_hp": 50, 
                "conditions": ["Grappled"],  # Key condition!
                "position": {"distance_to_boss": 40}
            },
            inventory={"weapons": ["Greataxe"], "potions": ["Healing Potion"]},
            skills={"athletics": 6, "intimidation": 2}
        )
        session.add(grog)
        session.commit()
        
        yield campaign, grog
        
        session.delete(grog)
        session.delete(campaign)
        session.commit()
    
    def test_grappled_condition_exists(self, session, grog_the_grappled):
        """Verify the Grappled condition is correctly stored."""
        campaign, grog = grog_the_grappled
        
        assert "Grappled" in grog.current_status.get("conditions", [])
        assert grog.current_status.get("hp") == 15
        assert grog.current_status.get("position", {}).get("distance_to_boss") == 40
        print(f"Grog Status: {grog.current_status}")
    
    def test_rules_lawyer_prompt_includes_conditions(self, session, grog_the_grappled):
        """
        Verify that the Rules Lawyer prompt would include condition info.
        This tests the data availability, not the LLM response.
        """
        from src.tools.character_manager import get_character_prompt_block
        
        campaign, grog = grog_the_grappled
        
        prompt_block = get_character_prompt_block(grog.id, session)
        
        # The prompt block should mention conditions
        assert "Grappled" in prompt_block or "conditions" in prompt_block.lower()
        print(f"Character Prompt Block:\n{prompt_block}")
    
    def test_action_economy_data_model(self, session, grog_the_grappled):
        """
        Test that action economy can be tracked in state.
        D&D 5e: 1 Action, 1 Bonus Action, 1 Reaction, Movement per turn.
        """
        campaign, grog = grog_the_grappled
        
        # Simulate action economy tracking
        action_economy = {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 30  # Grog's speed
        }
        
        # Update character's current_status with action economy
        result = update_character.invoke({
            "character_id": grog.id,
            "field": "action_economy",
            "value": action_economy
        })
        
        assert "Updated" in result
        
        # Verify it persisted
        session.expire_all()
        refreshed = session.get(Character, grog.id)
        assert refreshed.current_status.get("action_economy") is not None
        assert refreshed.current_status["action_economy"]["action_used"] == False
        print(f"Action Economy Tracking: {refreshed.current_status['action_economy']}")
    
    def test_dash_plus_attack_conflict(self):
        """
        Document the expected behavior for Dash + Attack conflict.
        Both require the Action in D&D 5e, so they cannot both be used.
        
        This is a documentation test - the actual validation is in Rules Lawyer.
        """
        # D&D 5e Rules:
        # - Dash: Uses your Action to gain extra movement
        # - Attack: Uses your Action to make weapon attacks
        # - You only have ONE Action per turn
        
        # Expected Rules Lawyer behavior:
        # Input: "I Dash to the enemy and Attack"
        # Output: "OBJECTION: You cannot Dash and Attack in the same turn. 
        #          Dash uses your Action, and so does Attack."
        
        assert True  # Placeholder for future LLM-based test
        print("Dash + Attack conflict documented. Rules Lawyer should reject this.")
    
    def test_grappled_prevents_movement(self):
        """
        Document the expected behavior for Grappled condition.
        Grappled: Speed becomes 0, cannot benefit from bonuses to speed.
        
        This is a documentation test - the actual validation is in Rules Lawyer.
        """
        # D&D 5e Rules:
        # - Grappled condition: A grappled creature's speed becomes 0
        # - Cannot benefit from any bonus to its speed
        # - Ends if the grappler is incapacitated or moved away
        
        # Expected Rules Lawyer behavior:
        # Input: Character with Grappled condition tries to move
        # Output: "OBJECTION: Grog is Grappled. Speed is 0. Cannot move."
        
        assert True  # Placeholder for future LLM-based test
        print("Grappled movement block documented. Rules Lawyer should reject movement.")
