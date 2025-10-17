#!/usr/bin/env python3
"""
RAG Database Creation Script for PDF Files
-----------------------------------------
This script creates a Retrieval Augmented Generation (RAG) database by:
1. Reading PDF files from the _Cisco_AI_PDFs folder
2. Converting PDFs to text
3. Storing the text in a vector database (ChromaDB)
4. Providing query capabilities against the stored content

Usage:
    To run as a script:
        python a01_RAG_DB_Creation_PDF.py

    To use as a module:
        from a01_RAG_DB_Creation_PDF import create_rag_database_from_pdfs
        create_rag_database_from_pdfs()
"""

import os
import glob
from pypdf import PdfReader
import chromadb
from chromadb.utils import embedding_functions

# Define paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RAG_DIR = os.path.join(PROJECT_DIR, "rag")
PDF_DIR = os.path.join(PROJECT_DIR, "_Cisco_AI_PDFs")
TXT_DIR = os.path.join(PROJECT_DIR, "_Cisco_AI_TXTs")

# --- PDF Processing Functions ---

def convert_pdf_to_text(pdf_path):
    """
    Convert a PDF file to text
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as a string
    """
    try:
        reader = PdfReader(pdf_path)
        text = ""
        
        # Process each page
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"--- Page {page_num + 1} ---\n" + page_text
                
        return text
    
    except Exception as e:
        print(f"Error processing PDF {os.path.basename(pdf_path)}: {str(e)}")
        return ""

def process_pdf_files(pdf_dir, txt_dir):
    """
    Process all PDF files in the PDF directory, convert to text,
    save as text files, and return the processed text
    
    Returns:
        List of dictionaries containing file_name and text content
    """
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    processed_documents = []
    
    print(f"\nFound {len(pdf_files)} PDF files to process.")
    
    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)
        print(f"Processing: {file_name}")
        
        # Extract text from PDF
        text_content = convert_pdf_to_text(pdf_path)
        
        if not text_content:
            print(f"Warning: No text extracted from {file_name}")
            continue
            
        # Save text to file
        txt_path = os.path.join(txt_dir, file_name.replace(".pdf", ".txt"))
        with open(txt_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(text_content)
            
        print(f"  - Saved text to: {os.path.basename(txt_path)}")
        print(f"  - Extracted {len(text_content)} characters")
        
        # Chunk the document for better RAG performance
        chunks = chunk_text(text_content, file_name)
        processed_documents.extend(chunks)
    
    print(f"\nExtracted {len(processed_documents)} text chunks from {len(pdf_files)} PDF files.")
    return processed_documents

def chunk_text(text, file_name, chunk_size=1000, overlap=200):
    """
    Split text into overlapping chunks for better RAG performance
    
    Args:
        text: The text to chunk
        file_name: Source file name for metadata
        chunk_size: Maximum chunk size in characters
        overlap: Overlap between chunks in characters
        
    Returns:
        List of dictionaries with document chunks
    """
    chunks = []
    
    if len(text) <= chunk_size:
        # Text is small enough to be a single chunk
        chunks.append({
            "file_name": file_name,
            "chunk_id": 0,
            "text": text
        })
    else:
        # Split into overlapping chunks
        start = 0
        chunk_id = 0
        
        while start < len(text):
            # Calculate end position with potential sentence boundary alignment
            end = min(start + chunk_size, len(text))
            
            # Try to find a good sentence boundary
            if end < len(text):
                # Look for sentence-ending punctuation followed by space or newline
                for i in range(end, max(start, end - 200), -1):
                    if text[i-1:i+1] in [". ", ".\n", "? ", "?\n", "! ", "!\n"]:
                        end = i
                        break
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append({
                    "file_name": file_name,
                    "chunk_id": chunk_id,
                    "text": chunk_text
                })
                
            # Move start position for next chunk
            start = end - overlap
            chunk_id += 1
            
            # Don't create empty or tiny chunks at the end
            if start >= len(text) - 200:
                break
    
    return chunks

# --- ChromaDB Setup and RAG ---

def setup_chroma_db(rag_dir):
    """
    Initialize ChromaDB with embedding model
    
    Returns:
        Tuple of (chroma_client, collection)
    """
    print("\nInitializing ChromaDB...")
    
    # Initialize Chroma client with persistent storage
    chroma_client = chromadb.PersistentClient(path=rag_dir)
    
    # Define the embedding function using sentence-transformers model
    embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    hf_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_model_name
    )
    
    # Collection name
    collection_name = "cisco_ai_pdf_collection"
    
    # Delete collection if it already exists (to start fresh)
    try:
        chroma_client.delete_collection(name=collection_name)
        print(f"Deleted existing collection: {collection_name}")
    except:
        pass
    
    # Create collection
    collection = chroma_client.create_collection(
        name=collection_name,
        embedding_function=hf_ef
    )
    print(f"Created new collection: {collection_name}")
    
    return chroma_client, collection

def add_documents_to_chroma(collection, documents):
    """
    Add documents to ChromaDB collection
    
    Args:
        collection: ChromaDB collection
        documents: List of document dictionaries
    """
    if not documents:
        print("No documents to add to ChromaDB.")
        return
    
    print(f"\nAdding {len(documents)} document chunks to ChromaDB...")
    
    # Prepare data for ChromaDB
    texts = [doc["text"] for doc in documents]
    ids = [f"{doc['file_name']}_{doc['chunk_id']}" for doc in documents]
    metadatas = [{"file_name": doc["file_name"], "chunk_id": doc["chunk_id"]} for doc in documents]
    
    # Add documents in batches to avoid memory issues
    batch_size = 50
    for i in range(0, len(texts), batch_size):
        end_idx = min(i + batch_size, len(texts))
        print(f"  Adding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}...")
        
        collection.add(
            documents=texts[i:end_idx],
            ids=ids[i:end_idx],
            metadatas=metadatas[i:end_idx]
        )
    
    print(f"Successfully added {len(texts)} document chunks to ChromaDB.")

def test_query(collection):
    """
    Run a test query against the ChromaDB collection
    
    Args:
        collection: ChromaDB collection
    """
    if collection.count() == 0:
        print("\nChromaDB collection is empty, cannot perform a query.")
        return
    
    query_text = "What are Cisco's AI principles?"
    print(f"\nRunning test query: '{query_text}'")
    
    results = collection.query(
        query_texts=[query_text],
        n_results=3  # Get top 3 results
    )
    
    print("\nQuery Results:")
    if results and 'documents' in results and results['documents']:
        for i, doc_list in enumerate(results['documents']):
            print(f"\nResults for query '{query_text}':")
            for j, doc in enumerate(doc_list):
                print(f"\n  Result {j+1}:")
                print(f"    Document: {results.get('metadatas', [[]])[i][j].get('file_name', 'Unknown')}")
                print(f"    Chunk ID: {results.get('metadatas', [[]])[i][j].get('chunk_id', 'Unknown')}")
                
                # Display distance as similarity (if available)
                if 'distances' in results and results['distances'] and i < len(results['distances']):
                    distance = results['distances'][i][j]
                    similarity = distance if distance > 0 else 1.0 + distance
                    print(f"    Relevance: {abs(similarity):.2%}")
                
                # Display a preview of the text (first 300 characters)
                preview = doc[:300].replace("\n", " ").strip()
                print(f"    Preview: {preview}...")
    else:
        print("No documents found matching the query.")

def create_rag_database_from_pdfs():
    """Main function to run the RAG database creation process"""
    print("="*80)
    print("Cisco AI PDF RAG Database Creator")
    print("="*80)

    # Create directories if they don't exist
    os.makedirs(RAG_DIR, exist_ok=True)
    os.makedirs(TXT_DIR, exist_ok=True)
    
    # Process PDF files
    documents = process_pdf_files(PDF_DIR, TXT_DIR)
    
    # Setup ChromaDB
    chroma_client, collection = setup_chroma_db(RAG_DIR)
    
    # Add documents to ChromaDB
    add_documents_to_chroma(collection, documents)
    
    # Test query
    test_query(collection)
    
    print("\nRAG database creation complete!")
    print(f"- PDF text files saved to: {TXT_DIR}")
    print(f"- RAG database saved to: {RAG_DIR}")
    print("="*80)

if __name__ == "__main__":
    create_rag_database_from_pdfs()
