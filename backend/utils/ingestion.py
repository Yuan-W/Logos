"""
PDF Ingestion Utility
=====================
Handles uploading and ingesting PDFs into the vector database.
"""

import os
from typing import List
from pypdf import PdfReader
from langchain_core.documents import Document as LangChainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.orm import Session
from pgvector.sqlalchemy import Vector

from backend.database.models import Document
from backend.database.db_init import get_session


# Get embedding model
embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
    openai_api_base=os.getenv("LITELLM_URL", "http://litellm:4000/v1"),
    dimensions=768  # Request 768 dimensions from model directly
)


def get_embedding(text: str) -> List[float]:
    """Generate embedding for text using configured model."""
    return embedding_model.embed_query(text)


def ingest_pdf(file_path: str, session: Session = None):
    """
    Ingest a PDF file into the database.
    
    1. Read PDF
    2. Split text into chunks
    3. Generate embeddings
    4. Save to database
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    print(f"Reading PDF: {file_path}...")
    reader = PdfReader(file_path)
    
    full_text = ""
    page_map = []  # [(start_char_index, page_num), ...]
    
    current_index = 0
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        full_text += text
        page_map.append((current_index, i + 1))
        current_index += len(text)
    
    # Split text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = text_splitter.split_text(full_text)
    print(f"Generated {len(chunks)} chunks.")
    
    # Create DB session if not provided
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
        
    try:
        # Process chunks
        for i, chunk_text in enumerate(chunks):
            # Find source page (approximate)
            chunk_start = full_text.find(chunk_text)
            page_num = 1
            for idx, p_num in reversed(page_map):
                if chunk_start >= idx:
                    page_num = p_num
                    break
            
            # Generate embedding
            embedding = get_embedding(chunk_text)
            
            # Create Document record
            doc = Document(
                title=os.path.basename(file_path),
                chunk_content=chunk_text,
                embedding=embedding,
                source_page=page_num,
                source_url=file_path,
                meta={"chunk_index": i}
            )
            session.add(doc)
            
        session.commit()
        print(f"Successfully ingested {len(chunks)} chunks into database.")
        
    finally:
        if close_session:
            session.close()

# Additional imports for Code Ingestion
import json
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain_openai import ChatOpenAI
from backend.database.models import CodeSnippet

# Initialize LLM for Ingestion (if needed for smart splitting)
ingestion_llm = ChatOpenAI(
    model="gemini-2.0-flash-exp", # Fast model for extraction
    openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
    openai_api_base=os.getenv("LITELLM_URL", "http://litellm:4000/v1")
)


def ingest_code_file(file_path: str, session: Session = None):
    """
    Ingest a Source Code file into the CodeSnippet table.
    Uses Gemini to strictly split by Logical Blocks (Functions/Classes).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    print(f"Reading Code File: {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        code_content = f.read()
        
    # Smart Extraction via LLM
    # We ask LLM to return a JSON list of blocks
    
    system_template = """You are a Code Parser. 
Extract all top-level classes and functions from the provided source code.
Return a JSON object with a key "blocks" containing a list of objects.
Each object must have:
- "name": Name of class/function
- "type": "class" or "function"
- "code": The EXACT code block (including decorators and docstrings)
- "description": A concise summary of what it does (for semantic search).

JSON Output Only."""

    human_template = "{code}"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", human_template)
    ])
    
    # Run Extraction
    try:
        response = ingestion_llm.invoke(prompt.format_messages(code=code_content))
        # Clean markdown code fences if present
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        data = json.loads(content)
        blocks = data.get("blocks", [])
        print(f"Extracted {len(blocks)} logical blocks.")
        
    except Exception as e:
        print(f"LLM Extraction failed: {e}. Fallback to whole file.")
        # Fallback: Treat whole file as one snippet
        blocks = [{
            "name": os.path.basename(file_path),
            "type": "file",
            "code": code_content,
            "description": "Entire file content"
        }]
    
    # Create DB session
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
        
    try:
        for block in blocks:
            code_block = block["code"]
            desc = block["description"]
            
            # Composite embedding: Description + Function Signature
            # Truncate code for embedding if too long, but keep full code in DB
            signature = code_block.split("\n")[0]
            embed_text = f"{block['name']} ({block['type']}): {desc}\nSignature: {signature}"
            
            embedding = get_embedding(embed_text)
            
            # Detect language extension
            ext = os.path.splitext(file_path)[1][1:] # .py -> py
            
            snippet = CodeSnippet(
                language=ext or "text",
                code_block=code_block,
                embedding=embedding,
                description=desc,
                source_file=file_path,
                meta={"name": block["name"], "type": block["type"]}
            )
            session.add(snippet)
            
        session.commit()
        print(f"Successfully ingested {len(blocks)} code snippets.")
        
    finally:
        if close_session:
            session.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        cmd = sys.argv[1]
        target = sys.argv[2]
        if cmd == "pdf":
            ingest_pdf(target)
        elif cmd == "code":
            ingest_code_file(target)
    elif len(sys.argv) > 1:
        # Legacy default
        ingest_pdf(sys.argv[1])
    else:
        print("Usage:")
        print("  python src/utils/ingestion.py pdf <file.pdf>")
        print("  python src/utils/ingestion.py code <file.py>")
