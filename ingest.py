import os
import json
import hashlib
import shutil
import argparse
import datetime
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

def extract_metadata(filepath):
    filename = os.path.basename(filepath)
    lower_path = filepath.lower()
    
    log_type = "unknown"
    if "malware" in lower_path: log_type = "malware"
    elif "intrusion" in lower_path: log_type = "intrusion"
    elif "web" in lower_path: log_type = "web"
    elif "http" in lower_path: log_type = "http"
        
    source_vm = "unknown"
    if "vm1" in lower_path: source_vm = "vm1"
    elif "vm2" in lower_path: source_vm = "vm2"
        
    try:
        timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
    except Exception:
        timestamp = "unknown"
        
    return {
        "source": filepath,
        "filename": filename,
        "log_type": log_type,
        "source_vm": source_vm,
        "timestamp": timestamp
    }

def process_file(filepath):
    documents = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if content.strip():
                metadata = extract_metadata(filepath)
                documents.append(Document(page_content=content, metadata=metadata))
    except Exception as e:
        print(f"[!] Warning: Could not read {filepath} - {e}")
    return documents

def ingest_logs(file_path=None):
    documents = []
    is_single_file = file_path is not None
    
    if is_single_file:
        print(f"[*] Ingesting single file: {file_path}")
        if not os.path.exists(file_path):
            print(f"[!] File not found: {file_path}")
            return False
        documents.extend(process_file(file_path))
    else:
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
        for root, _, files in os.walk(LOGS_DIR):
            for file in files:
                filepath = os.path.join(root, file)
                documents.extend(process_file(filepath))
                
    if not documents:
        print("[!] No log contents found to ingest.")
        return False
        
    print(f"[*] Loaded {len(documents)} log files. Splitting text...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        add_start_index=True
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"[*] Created {len(chunks)} chunks.")
    
    # Prevent appending duplicates to existing collection only if full scan
    if not is_single_file and os.path.exists(DB_DIR):
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
        if not is_single_file:
            print("[!] Cleaning up incomplete database...")
            try:
                shutil.rmtree(DB_DIR)
            except:
                pass
        return False
    
    if not is_single_file:
        with open(STATE_FILE, "w") as f:
            json.dump({"hash": current_hash}, f)
        
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinel-Chain Log Ingestion")
    parser.add_argument("--file", "-f", type=str, help="Path to a specific log file to ingest", default=None)
    args = parser.parse_args()
    
    ingest_logs(file_path=args.file)
