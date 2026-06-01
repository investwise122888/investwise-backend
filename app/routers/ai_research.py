from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user_uid, get_current_user_email
from app.services.ai_research_service import get_latest_ai_research

router = APIRouter(prefix="/ai-research", tags=["ai_research"])

@router.get("")
async def get_ai_research(
    user_id: str = Depends(get_current_user_uid),
    user_email: str = Depends(get_current_user_email)
):
    """Return the latest AI research rankings (protected)."""
    research = get_latest_ai_research()
    if not research:
        raise HTTPException(status_code=404, detail="No AI research data available. Please try again later.")
    return research