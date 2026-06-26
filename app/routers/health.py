from fastapi import APIRouter
from typing import Dict


router = APIRouter()

# I need to make it more robust and maybe format better the response


@router.get("/health")
def get_health() -> Dict[str, str]:
    return {"status": "ok"}
