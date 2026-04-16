from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.dependencies import verify_api_key

router = APIRouter()


@router.post("", dependencies=[Depends(verify_api_key)])
async def upload(
    file: UploadFile = File(...),
    source_vm: str = Form(...),
    log_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    return {"message": "not implemented yet"}
