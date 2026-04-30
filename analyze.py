import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "chroma_db")

class ThreatReport(BaseModel):
    summary: str = Field(description="Brief overview of what the logs contain and major activity")
    severity: str = Field(description="Classification: LOW, MEDIUM, HIGH, or CRITICAL, with justification")
    findings: list[str] = Field(description="List of anomalies, errors, suspicious patterns, or notable events found in the logs")
    recommendations: list[str] = Field(description="List of actionable steps the user should take based on the findings")

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30))
def generate_report_with_backoff(llm, prompt_text):
    print("[*] Contacting Gemini API (with exponential backoff for rate limits if needed)...")
    structured_llm = llm.with_structured_output(ThreatReport)
    return structured_llm.invoke(prompt_text)

def analyze_logs():
    print("\n[*] Starting Auto-Analysis of Log Data...")

    if not os.path.exists(DB_DIR):
        print("[!] ChromaDB directory not found. Please run ingest first.")
        return None

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)

    try:
        # Retrieve top 15 chunks using a broad security query instead of all docs
        retriever = vectorstore.as_retriever(search_kwargs={"k": 15})
        docs = retriever.invoke("security incidents errors anomalies threats malicious connection failure")

        if not docs:
            print("[!] No documents found in database. Cannot analyze.")
            return None

        full_context = "\n\n".join([doc.page_content for doc in docs])
        print(f"[*] Retrieved top {len(docs)} document chunks for analysis.")

    except Exception as e:
        print(f"[!] Error retrieving from ChromaDB: {e}")
        return None

    # Initialize Gemini 1.5 Flash
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0.2)

    prompt_template = """
You are a security analyst, "Sentinel-Chain AI Core".
Analyze the provided log context and produce a structured threat report.

Log Data Context:
{context}

Generate the structural threat report now based only on the context above.
If there are no apparent threats, indicate that in the summary with a LOW severity.
"""

    prompt = PromptTemplate(template=prompt_template, input_variables=["context"])
    prompt_text = prompt.format(context=full_context)

    print("[*] Generating threat report with Gemini-1.5-Flash...")
    try:
        report = generate_report_with_backoff(llm, prompt_text)

        # Convert Pydantic object to native dict
        report_dict = report.dict()

        print("\n" + "="*80)
        print(" " * 20 + "SENTINEL-CHAIN AI CORE : THREAT REPORT")
        print("="*80 + "\n")
        print(f"SUMMARY: {report_dict['summary']}\n")
        print(f"SEVERITY: {report_dict['severity']}\n")

        print("FINDINGS:")
        for f in report_dict['findings']:
            print(f" - {f}")

        print("\nRECOMMENDATIONS:")
        for r in report_dict['recommendations']:
            print(f" - {r}")

        print("\n" + "="*80 + "\n")

        return report_dict
    except Exception as e:
        print(f"[!] Error during Gemini analysis: {e}")
        return None

if __name__ == "__main__":
    analyze_logs()
