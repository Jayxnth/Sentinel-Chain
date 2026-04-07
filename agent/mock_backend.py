"""Throwaway mock backend for local M3 development and demo. Not production code."""
from fastapi import FastAPI, Header
import uvicorn

app = FastAPI()
counter = {"id": 0}


@app.post("/ingest")
async def ingest(body: dict, x_api_key: str = Header()):
    counter["id"] += 1
    print(f"Batch #{counter['id']} from {body['source_vm']} ({body['log_type']}) — {len(body['content'])} bytes — VERIFIED")
    return {"batch_id": counter["id"], "integrity_status": "VERIFIED"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
