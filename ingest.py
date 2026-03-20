import os
import json
import hashlib
import shutil
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DB_DIR = os.path.join(BASE_DIR, "chroma_db")
STATE_FILE = os.path.join(BASE_DIR, ".ingest_state.json")

def get_directory_hash(directory_path):
    if not os.path.exists(directory_path):
        return None
    
    hasher = hashlib.md5()
    for root, _, files in os.walk(directory_path):
        for file in sorted(files):
            filepath = os.path.join(root, file)
            # Hash the relative path and the modification time
            rel_path = os.path.relpath(filepath, directory_path)
            try:
                mtime = os.path.getmtime(filepath)
                hasher.update(f"{rel_path}:{mtime}".encode('utf-8'))
            except OSError:
                pass
    return hasher.hexdigest()

def ingest_logs():
    print(f"[*] Checking logs/ folder for changes...")
    
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
        print(f"[*] Created logs/ directory. Please add log files and run again.")
        return False
        
    current_hash = get_directory_hash(LOGS_DIR)
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                if state.get("hash") == current_hash and os.path.exists(DB_DIR):
                    print("[*] No changes detected in logs directory. Skipping ingestion.")
                    return True
        except json.JSONDecodeError:
            pass

    print("[*] Changes detected or first run. Starting ingestion process...")
    
    documents = []
    for root, _, files in os.walk(LOGS_DIR):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if content.strip():
                        documents.append(Document(page_content=content, metadata={"source": filepath}))
            except Exception as e:
                print(f"[!] Warning: Could not read {filepath} - {e}")
                
    if not documents:
        print("[!] No log contents found to ingest.")
        return False
        
    print(f"[*] Loaded {len(documents)} log files. Splitting text...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        add_start_index=True
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"[*] Created {len(chunks)} chunks.")
    
    # Prevent appending duplicates to existing collection
    if os.path.exists(DB_DIR):
        print(f"[*] Removing old ChromaDB at {DB_DIR} to prevent duplicates...")
        try:
            shutil.rmtree(DB_DIR)
        except Exception as e:
            print(f"[!] Warning: Could not remove old DB directory: {e}")
            
    # Initialize Local Embeddings Model 
    print(f"[*] Generating local embeddings offline for {len(chunks)} chunks... (This may take a moment but avoids API limits!)")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    try:
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=DB_DIR
        )
        print(f"[*] Successfully ingested {len(chunks)} log chunks into local ChromaDB at {DB_DIR}")
    except Exception as e:
        print(f"\n[!] Error storing vectors locally: {e}")
        print("[!] Cleaning up incomplete database...")
        try:
            shutil.rmtree(DB_DIR)
        except:
            pass
        return False
    
    with open(STATE_FILE, "w") as f:
        json.dump({"hash": current_hash}, f)
        
    return True

if __name__ == "__main__":
    ingest_logs()
