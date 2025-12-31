"""
Glossary Tool Tests
===================
Verifies the TermRegistry and TermRetriever logic, specifically
scope prioritization and retrieval.
"""

import unittest
from sqlalchemy import delete
from src.database.models import TermRegistry
from src.database.db_init import get_session
from src.tools.glossary import TermRetriever
from src.utils.ingestion import get_embedding

class TestGlossary(unittest.TestCase):
    
    def setUp(self):
        self.session = get_session()
        # Clean up test terms first (safe? using specific test scope prefixes)
        # We'll use scopes that are unlikely to collide with real data
        self.test_scopes = ["test:global", "test:project_alpha", "test:user_1"]
        
        # Clear existing test data
        stmt = delete(TermRegistry).where(TermRegistry.scope.in_(self.test_scopes + ["test:other"]))
        self.session.execute(stmt)
        self.session.commit()
        
        # Seed Data
        self._seed_terms()
        
    def tearDown(self):
        # Cleanup
        stmt = delete(TermRegistry).where(TermRegistry.scope.in_(self.test_scopes + ["test:other"]))
        self.session.execute(stmt)
        self.session.commit()
        self.session.close()
        
    def _seed_terms(self):
        """Seed DB with conflicting definitions."""
        terms = [
            # Global Scope: Standard Definition
            TermRegistry(
                scope="test:global",
                term="Elf",
                definition="A magical humanoid with pointed ears, long-lived.",
                embedding=get_embedding("Elf")
            ),
            TermRegistry(
                scope="test:global",
                term="Orc",
                definition="A brutish green-skinned warrior.",
                embedding=get_embedding("Orc")
            ),
            
            # Project Scope: Overrides Elf, Adds Cyber-Orc
            TermRegistry(
                scope="test:project_alpha",
                term="Elf",
                definition="A cybernetic construct created by the Megacorp.",
                embedding=get_embedding("Elf")
            ),
            TermRegistry(
                scope="test:project_alpha",
                term="Cyber-Orc",
                definition="Mechanized infantry unit.",
                embedding=get_embedding("Cyber-Orc")
            ),
            
            # User Scope: Overrides Orc
            TermRegistry(
                scope="test:user_1",
                term="Orc",
                definition="My friendly neighbor Bob.",
                embedding=get_embedding("Orc")
            )
        ]
        self.session.add_all(terms)
        self.session.commit()

    def test_priority_override(self):
        """Test that later scopes in the list override earlier ones."""
        retriever = TermRetriever(self.session)
        
        # Case 1: Global Only
        terms = retriever.fetch_terms(["test:global"], "Tell me about Elf and Orc")
        self.assertIn("Elf", terms)
        self.assertIn("Orc", terms)
        self.assertIn("magical", terms["Elf"])
        self.assertIn("brutish", terms["Orc"])
        
        # Case 2: Project overrides Global
        # scopes = [Global, Project] -> Project wins
        terms = retriever.fetch_terms(["test:global", "test:project_alpha"], "Describe Elf")
        self.assertIn("Elf", terms)
        self.assertIn("cybernetic", terms["Elf"]) # Should be the project definition
        
        # Case 3: User overrides Global
        terms = retriever.fetch_terms(["test:global", "test:user_1"], "Orc")
        self.assertIn("Orc", terms)
        self.assertIn("Bob", terms["Orc"])
        
    def test_multi_layer_priority(self):
        """Test Global < Project < User chain."""
        retriever = TermRetriever(self.session)
        
        # Scenario: User (Bob) overrides Orc, Project (Cyber) overrides Elf
        # If we pass [Global, Project, User]
        scopes = ["test:global", "test:project_alpha", "test:user_1"]
        terms = retriever.fetch_terms(scopes, "Elf Orcc Cyber") # Typo in query? Embeddings should handle it?
        # Note: Vector search is robust to some drift, but basic logic relies on embedding dist.
        # Let's use clean keywords for first test pass.
        terms = retriever.fetch_terms(scopes, "Elf Orc Cyber-Orc")
        
        # Elf should be Project (Cybernetic) because User didn't define it?
        # Wait, if User didn't define Elf, it falls back to Project?
        # Logic check: We fetch ALL matching terms from ALL scopes.
        # Then we de-dup.
        # Elf is in Global and Project. User has no Elf.
        # Priority: Project (idx 1) > Global (idx 0). User (idx 2) N/A.
        # So Elf -> Cybernetic.
        self.assertIn("cybernetic", terms["Elf"])
        
        # Orc is in Global and User. Project has no Orc.
        # Priority: User (idx 2) > Global (idx 0).
        # So Orc -> Bob.
        self.assertIn("Bob", terms["Orc"])
        
        # Cyber-Orc is only in Project.
        self.assertIn("Cyber-Orc", terms)
        
    def test_prompt_formatting(self):
        retriever = TermRetriever(self.session)
        terms = {"Apples": "Red fruit", "Bananas": "Yellow fruit"}
        prompt = retriever.format_glossary_prompt(terms)
        
        self.assertIn("### TERMINOLOGY CONSTRAINTS", prompt)
        self.assertIn("- **Apples**: Red fruit", prompt)
        self.assertIn("- **Bananas**: Yellow fruit", prompt)

if __name__ == "__main__":
    unittest.main()
