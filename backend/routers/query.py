import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.dependencies import verify_api_key

REPO_ROOT = str(Path(__file__).resolve().parents[2])

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    source_vm: Optional[str] = None
    log_type: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None


def _build_history_str(history: List[Dict[str, str]] | None) -> str:
    if not history:
        return ""
    recent = history[-6:]
    parts = []
    for msg in recent:
        role = "User" if msg.get("role") == "user" else "Assistant"
        parts.append(f"{role}: {msg.get('content', '')}")
    return "\n".join(parts)


def _run_query(question: str, metadata_filter: dict | None, history_str: str) -> tuple[str, list]:
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_google_genai import ChatGoogleGenerativeAI

    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from chat import extract_filters

    db_dir = os.path.join(REPO_ROOT, "chroma_db")
    if not os.path.exists(db_dir):
        raise FileNotFoundError("chroma_db not found")

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma(persist_directory=db_dir, embedding_function=embeddings)

    # Build filter: explicit request params take priority, else auto-detect
    if metadata_filter is None:
        metadata_filter = extract_filters(question)

    search_kwargs = {"k": 10}
    if metadata_filter:
        search_kwargs["filter"] = metadata_filter

    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
    docs = retriever.invoke(question)

    # Build citations and context
    citations = []
    context_pieces = []
    for idx, doc in enumerate(docs):
        fn = doc.metadata.get("filename", "unknown")
        lt = doc.metadata.get("log_type", "unknown")
        ts = doc.metadata.get("timestamp", "unknown")
        context_pieces.append(f"[Source {idx+1} | File: {fn} | Type: {lt} | Time: {ts}]\n{doc.page_content}")
        citations.append({
            "batch_id": None,
            "source_vm": doc.metadata.get("source_vm"),
            "log_line": doc.page_content[:200],
            "ts": ts,
        })

    context = "\n\n".join(context_pieces)

    prompt = (
        "You are Sentinel-Chain AI Core, an expert cybersecurity assistant.\n"
        "Use the following pieces of retrieved log context to answer the user's question.\n"
        "If you don't know the answer or the context doesn't contain it, just say that you don't know based on the logs.\n"
        "CRITICAL: You MUST include source citations in your answer. For every finding, append the source reference used (e.g., [Source 1]).\n"
        "At the end of your answer, list the unique source files you referenced.\n"
        "Be concise, analytical, and reference specific log details when possible.\n\n"
        f"Context Logs:\n{context}\n\n"
    )
    if history_str:
        prompt += f"Recent Chat History:\n{history_str}\n\n"
    prompt += f"User Query: {question}"

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
    response = llm.invoke(prompt)
    return response.content, citations


@router.post("", dependencies=[Depends(verify_api_key)])
async def query(
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    db_dir = os.path.join(REPO_ROOT, "chroma_db")
    if not os.path.exists(db_dir):
        return {"answer": "No logs have been ingested yet.", "citations": []}

    # Build explicit filter from request params
    metadata_filter = None
    if payload.source_vm:
        metadata_filter = {"source_vm": payload.source_vm}
    if payload.log_type:
        metadata_filter = metadata_filter or {}
        metadata_filter["log_type"] = payload.log_type

    history_str = _build_history_str(payload.history)

    try:
        answer, citations = await asyncio.wait_for(
            asyncio.to_thread(_run_query, payload.question, metadata_filter, history_str),
            timeout=30,
        )
    except FileNotFoundError:
        return JSONResponse(status_code=503, content={"error": "No logs have been ingested yet"})
    except Exception:
        return JSONResponse(status_code=500, content={"error": "AI query failed"})

    return {"answer": answer, "citations": citations}
