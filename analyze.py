import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "chroma_db")

def analyze_logs():
    print("\n[*] Starting Auto-Analysis of Log Data...")
    
    if not os.path.exists(DB_DIR):
        print("[!] ChromaDB directory not found. Please run ingest first.")
        return
        
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    
    try:
        # ChromaDB `get()` retrieves all documents if no arguments are passed
        all_data = vectorstore.get()
        documents = all_data.get('documents', [])
    except Exception as e:
        print(f"[!] Error retrieving from ChromaDB: {e}")
        return
        
    if not documents:
        print("[!] No documents found in database. Cannot analyze.")
        return
        
    full_context = "\n\n".join(documents)
    print(f"[*] Retrieved {len(documents)} document chunks for analysis.")
    
    # Initialize Gemini 2.5 Flash
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    
    prompt_template = """
You are an expert cybersecurity AI, "Sentinel-Chain AI Core".
You have been provided with log data representing activity on a system.

Analyze the logs thoroughly and produce a structured threat report.
The report MUST contain the following sections exactly as named below (use Markdown):

## Summary
(A brief overview of what the logs contain and major activity)

## Severity
(A classification: LOW, MEDIUM, HIGH, or CRITICAL, with a 1-2 sentence justification)

## Findings
(A bulleted list of anomalies, errors, suspicious patterns, or notable events found in the logs. Mention specific IPs, usernames, or filenames if available.)

## Recommendations
(A bulleted list of actionable steps the user should take based on the findings)

Log Data Context:
{context}

Generate the threat report now.
"""
    
    prompt = PromptTemplate(template=prompt_template, input_variables=["context"])
    chain = prompt | llm
    
    print("[*] Generating threat report with Gemini 1.5 Flash. This may take a moment...")
    try:
        response = chain.invoke({"context": full_context})
        print("\n" + "="*80)
        print(" " * 20 + "SENTINEL-CHAIN AI CORE : THREAT REPORT")
        print("="*80 + "\n")
        print(response.content)
        print("\n" + "="*80 + "\n")
    except Exception as e:
        print(f"[!] Error during Gemini analysis: {e}")

if __name__ == "__main__":
    analyze_logs()
