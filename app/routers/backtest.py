from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import get_current_user_uid, get_current_user_email
from app.services.backtest_service import compute_backtest_stats

router = APIRouter(prefix="/backtest", tags=["backtest"])

@router.get("/stats")
async def get_backtest_stats(
    weeks: int = Query(4, ge=1, le=52, description="Holding period in weeks"),
    user_id: str = Depends(get_current_user_uid),
    user_email: str = Depends(get_current_user_email)
):
    try:
        stats = await compute_backtest_stats(weeks)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))