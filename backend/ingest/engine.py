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

# Initialize Vision LLM (Gemini Flash)
# We assume LiteLLM proxy handles "gemini/gemini-1.5-flash" and image inputs standardly.
vision_llm = ChatOpenAI(
    model="gemini-3-flash-preview", 
    openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
    openai_api_base=os.getenv("LITELLM_URL", "http://litellm:4000/v1"),
    max_tokens=4000
)

class GeminiIngestor:
    def __init__(self, session: Session = None):
        self.session = session if session else get_session()
        self.own_session = session is None

    def close(self):
        if self.own_session:
            self.session.close()

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

        for i, image in enumerate(images):
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
                
            except Exception as e:
                print(f"Error processing page {i+1}: {e}")

        self.session.commit()
        print("Ingestion Complete.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        ingestor = GeminiIngestor()
        ingestor.process_file(sys.argv[1], flavor=sys.argv[2])
        ingestor.close()
    else:
        print("Usage: python src/ingest/engine.py <file.pdf> <flavor>")
