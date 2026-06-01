import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from firebase_admin import auth
from app.auth import get_current_user_uid
from app.services.payment_service import verify_payment, reject_payment
from app.database import db
from app.models import PAYMENTS_COLLECTION, SUBSCRIPTIONS_COLLECTION
from app.services.scheduler import manual_refresh
from app.services.ai_research_service import refresh_ai_research

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

class PaymentVerifyRequest(BaseModel):
    payment_id: str

class PaymentRejectRequest(BaseModel):
    payment_id: str

def get_admin_user(current_uid: str = Depends(get_current_user_uid)):
    user = auth.get_user(current_uid)
    user_email = user.email
    admin_emails_str = os.getenv("ADMIN_EMAILS", "")
    admin_emails = [email.strip() for email in admin_emails_str.split(",") if email.strip()]
    if user_email not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_uid

@router.get("")
async def admin_root(admin_id: str = Depends(get_admin_user)):
    return {"message": "Admin API"}

@router.get("/payments")
async def list_pending_payments(admin_id: str = Depends(get_admin_user)):
    payments_ref = db.collection(PAYMENTS_COLLECTION).where("status", "==", "pending")
    docs = payments_ref.stream()
    result = []
    for doc in docs:
        data = doc.to_dict()
        user_id = data.get("user_id")
        try:
            user = auth.get_user(user_id)
            email = user.email
        except Exception as e:
            logger.warning(f"Could not fetch user {user_id}: {e}")
            email = "unknown"
        result.append({
            "payment_id": doc.id,
            "user_id": user_id,
            "user_email": email,
            "amount": data.get("amount"),
            "plan": data.get("plan"),
            "screenshot_base64": data.get("screenshot_base64"),
            "created_at": data.get("created_at").isoformat() if data.get("created_at") else None
        })
    return {"payments": result}

@router.post("/verify-payment")
async def verify_payment_endpoint(req: PaymentVerifyRequest, admin_id: str = Depends(get_admin_user)):
    try:
        verify_payment(req.payment_id, admin_id)
        return {"status": "success", "message": "Payment verified and subscription activated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reject-payment")
async def reject_payment_endpoint(req: PaymentRejectRequest, admin_id: str = Depends(get_admin_user)):
    try:
        reject_payment(req.payment_id, admin_id)
        return {"status": "success", "message": "Payment rejected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/users")
async def list_users_with_subscription(admin_id: str = Depends(get_admin_user)):
    subs_ref = db.collection(SUBSCRIPTIONS_COLLECTION).stream()
    subscriptions = []
    for doc in subs_ref:
        data = doc.to_dict()
        user_id = doc.id
        try:
            user = auth.get_user(user_id)
            email = user.email
        except Exception as e:
            logger.warning(f"Could not fetch user {user_id}: {e}")
            email = "unknown"
        subscriptions.append({
            "user_id": user_id,
            "email": email,
            "plan": data.get("plan"),
            "active": data.get("active"),
            "expiry_date": data.get("expiry_date").isoformat() if data.get("expiry_date") else None
        })
    return {"users": subscriptions}

@router.post("/refresh-data")
async def manual_refresh_data(admin_id: str = Depends(get_admin_user)):
    try:
        manual_refresh()
        return {"status": "success", "message": "Weekly signal refresh triggered."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Fixed: added await before refresh_ai_research()
@router.post("/refresh-ai")
async def manual_refresh_ai(admin_id: str = Depends(get_admin_user)):
    try:
        await refresh_ai_research()
        return {"status": "success", "message": "AI research refreshed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
