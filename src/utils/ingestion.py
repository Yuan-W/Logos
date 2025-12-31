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

from src.database.models import Document
from src.database.db_init import get_session


# Get embedding model
embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
    openai_api_base=os.getenv("OPENAI_API_BASE_URL", "http://localhost:4000/v1")
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
            embedding = embedding_model.embed_query(chunk_text)
            
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

if __name__ == "__main__":
    # Test ingestion
    import sys
    if len(sys.argv) > 1:
        ingest_pdf(sys.argv[1])
    else:
        print("Usage: python src/utils/ingestion.py <path_to_pdf>")
