"""
Universal Gemini-Distill Ingestion Engine
=========================================
Vision-based ingestion pipeline.
Converts documents to images, extracts structured data via Gemini Flash, 
and stores semantic vectors.
"""

import os
import json
import base64
from typing import List, Optional, Dict, Any, Union
from io import BytesIO

# Dependencies (Requires 'pdf2image', 'poppler-utils' installed in env)
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI # For accessing Gemini via LiteLLM/Proxy usually, but vision might need specific handling.
# Actually, for Vision via LiteLLM, we pass image_url or data uri.

from sqlalchemy.orm import Session
from backend.database.models import RuleBookChunk, DocumentChunk
from backend.database.db_init import get_session
from backend.utils.ingestion import get_embedding
from backend.ingest.flavors import get_prompt_for_flavor, IngestFlavor
from backend.tools.glossary import upsert_term
import time

# Initialize Vision LLM (Gemini Flash)
# We assume LiteLLM proxy handles "gemini/gemini-1.5-flash" and image inputs standardly.
vision_llm = ChatOpenAI(
    model="gemini-3-flash-preview", 
    openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
    openai_api_base=os.getenv("LITELLM_URL", "http://litellm:4000/v1"),
    max_tokens=4000
)

class GeminiIngestor:
    # Rate limiting constants
    BATCH_SIZE = 10  # Process N pages before pause
    BATCH_PAUSE_SECONDS = 2  # Pause duration between batches
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5
    
    def __init__(self, session: Session = None):
        self.session = session if session else get_session()
        self.own_session = session is None

    def close(self):
        if self.own_session:
            self.session.close()
    
    def _extract_terms_from_stat_blocks(self, stat_blocks: list, scope: str = "global:trpg") -> int:
        """
        P0 Fix: Auto-populate TermRegistry from extracted stat blocks.
        Returns count of terms added.
        """
        count = 0
        for block in stat_blocks:
            name = block.get("name")
            if not name:
                continue
            
            # Build definition from available fields
            block_type = block.get("type", "entity")
            description = block.get("description", "")
            
            # Include key stats in definition for semantic search
            stats_str = ""
            for key in ["hp", "ac", "cr", "damage", "level"]:
                if key in block:
                    stats_str += f" {key.upper()}: {block[key]},"
            
            definition = f"{block_type.capitalize()}.{stats_str} {description}".strip()
            
            try:
                upsert_term(
                    session=self.session,
                    scope=scope,
                    term=name,
                    definition=definition,
                    aliases=block.get("aliases", [])
                )
                count += 1
            except Exception as e:
                print(f"    Warning: Failed to upsert term '{name}': {e}")
        
        return count

    def _encode_image(self, image) -> str:
        """Convert PIL Image to base64 string."""
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def process_file(self, file_path: str, flavor: str = "generic"):
        """
        Main pipeline:
        1. Convert to images
        2. Gemini Vision Extraction
        3. Save Chunks
        """
        flavor_prompt = get_prompt_for_flavor(flavor)
        
        # 1. Load File
        if file_path.endswith(".pdf"):
            print(f"Converting PDF to images: {file_path}")
            try:
                images = convert_from_path(file_path)
            except Exception as e:
                print(f"PDF Conversion failed (Poppler missing?): {e}")
                return
        else:
             print(f"Unsupported file type for Vision Ingest: {file_path}")
             return

        print(f"Processing {len(images)} pages...")
        
        total_terms_extracted = 0

        for i, image in enumerate(images):
            # P1 Fix: Rate limiting - pause every BATCH_SIZE pages
            if i > 0 and i % self.BATCH_SIZE == 0:
                print(f"  Rate limit pause ({self.BATCH_PAUSE_SECONDS}s)...")
                time.sleep(self.BATCH_PAUSE_SECONDS)
            
            # Retry logic
            for attempt in range(self.MAX_RETRIES):
                try:
                    # 2. Vision Extraction
                    b64_img = self._encode_image(image)
                    image_url = f"data:image/jpeg;base64,{b64_img}"
                    
                    messages = [
                        SystemMessage(content=flavor_prompt + "\n\nCRITICAL: Return ONLY valid JSON. No Markdown fences."),
                        HumanMessage(content=[
                            {"type": "text", "text": "Analyze this page."},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ])
                    ]
                    
                    response = vision_llm.invoke(messages)
                    raw_content = response.content.replace("```json", "").replace("```", "").strip()
                    
                    try:
                        data = json.loads(raw_content)
                    except json.JSONDecodeError:
                        print(f"JSON Parse Error on page {i+1}. Fallback to text.")
                        data = {"content": raw_content, "stat_blocks": []}
                    
                    content_md = data.get("content", "")
                    stat_blocks = data.get("stat_blocks", [])
                    
                    # 3. Embedding and Saving
                    # Embed the semantic content (text)
                    embedding = get_embedding(content_md[:8000]) # Truncate for embedding model limit
                    
                    # Determine Model based on Flavor
                    if flavor == "trpg":
                        chunk = RuleBookChunk(
                            content=content_md,
                            embedding=embedding,
                            stat_block={"items": stat_blocks}, # Wrap list
                            source_metadata={"file": file_path, "page": i+1, "flavor": flavor}
                        )
                        self.session.add(chunk)
                        
                        # P0 Fix: Auto-extract terms for TRPG flavor
                        terms_count = self._extract_terms_from_stat_blocks(stat_blocks, scope="global:trpg")
                        total_terms_extracted += terms_count
                    
                    elif flavor == "research":
                        chunk = DocumentChunk(
                            content=content_md,
                            embedding=embedding,
                            stat_block={"items": stat_blocks},
                            source_metadata={"file": file_path, "page": i+1, "flavor": flavor}
                        )
                        self.session.add(chunk)
                         
                    else:
                        # Default to DocumentChunk for others
                        chunk = DocumentChunk(
                            content=content_md,
                            embedding=embedding,
                            stat_block={"items": stat_blocks},
                            source_metadata={"file": file_path, "page": i+1, "flavor": flavor}
                        )
                        self.session.add(chunk)

                    print(f"  Page {i+1} processed. {len(stat_blocks)} items extracted.")
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if attempt < self.MAX_RETRIES - 1:
                        print(f"  Page {i+1} failed (attempt {attempt+1}/{self.MAX_RETRIES}): {e}")
                        print(f"  Retrying in {self.RETRY_DELAY_SECONDS}s...")
                        time.sleep(self.RETRY_DELAY_SECONDS)
                    else:
                        print(f"  Page {i+1} FAILED after {self.MAX_RETRIES} attempts: {e}")

        self.session.commit()
        print(f"Ingestion Complete. {total_terms_extracted} terms added to TermRegistry.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        ingestor = GeminiIngestor()
        ingestor.process_file(sys.argv[1], flavor=sys.argv[2])
        ingestor.close()
    else:
        print("Usage: python src/ingest/engine.py <file.pdf> <flavor>")
