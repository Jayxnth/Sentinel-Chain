import os
from dotenv import load_dotenv
import ingest
import analyze
import chat

def run_pipeline():
    print("""
    ================================================
    Sentinel-Chain AI Core - Threat Analysis System
    ================================================
    """)
    
    # Ensure environment variables are loaded
    load_dotenv()
    
    if not os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY") == "your_gemini_api_key_here":
        print("[!] Warning: GOOGLE_API_KEY is not set in the environment.")
        print("[!] Please edit the .env file and add your valid Gemini API key.")
        return

    # Step 1: Ingest logs into ChromaDB
    print("[1] Log Ingestion Phase")
    success = ingest.ingest_logs()
    
    if not success:
        print("[!] Pipeline halted. Ensure logs are present in the 'logs/' folder and API key is set.")
        return
        
    # Step 2: Automated Threat Analysis
    print("\n[2] Automated Threat Analysis Phase")
    analyze.analyze_logs()
        
    # Step 3: Interactive chat loop
    print("\n[3] Interactive Chat Phase")
    chat.start_chat()

if __name__ == "__main__":
    run_pipeline()
