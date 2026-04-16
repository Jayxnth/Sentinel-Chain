from typing import List, Optional, Dict
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.dependencies import verify_api_key

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    source_vm: Optional[str] = None
    log_type: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None


@router.post("", dependencies=[Depends(verify_api_key)])
async def query(
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    return {"message": "not implemented yet"}
