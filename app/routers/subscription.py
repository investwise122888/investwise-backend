from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.auth import get_current_user_uid, get_current_user_email
from app.services.payment_service import (
    create_payment,
    get_user_subscription,
    check_subscription_active
)
from app.config import settings
import base64
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscription", tags=["subscription"])

PLAN_PRICES = {
    "monthly": 299,
    "yearly": 2999
}

@router.post("/subscribe")
async def subscribe(
    plan: str = Form(...),
    screenshot: UploadFile = File(...),
    user_id: str = Depends(get_current_user_uid)
):
    if plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Invalid plan. Use 'monthly' or 'yearly'")
    contents = await screenshot.read()
    screenshot_base64 = base64.b64encode(contents).decode("utf-8")
    amount = PLAN_PRICES[plan]
    payment_id = create_payment(user_id, amount, screenshot_base64, plan)
    return {
        "message": "Payment pending verification",
        "payment_id": payment_id,
        "plan": plan,
        "amount": amount
    }

@router.get("/my-subscription")
async def my_subscription(
    user_id: str = Depends(get_current_user_uid),
    user_email: str = Depends(get_current_user_email)
):
    logger.info(f"Checking subscription for email: {user_email}")
    
    # Normalize admin emails from environment variables (case-insensitive)
    admin_emails = [email.strip().lower() for email in settings.ADMIN_EMAILS if email.strip()]
    is_admin = user_email.lower() in admin_emails
    
    if is_admin:
        logger.info(f"Admin matched and authorized: {user_email}")
        return {
            "active": True,
            "plan": "admin_premium",
            "start_date": datetime.utcnow().isoformat(),
            "expiry_date": "2099-12-31T23:59:59",
            "admin": True
        }
        
    # Check regular subscription statuses
    active = check_subscription_active(user_id, user_email)
    sub = get_user_subscription(user_id)
    
    # If no Firestore document exists, return a structured Free Tier profile contract
    if not sub:
        return {
            "active": False,
            "plan": "free",
            "start_date": None,
            "expiry_date": None,
            "admin": False
        }
        
    return {
        "active": bool(active),
        "plan": sub.get("plan", "free"),
        "start_date": sub.get("start_date"),
        "expiry_date": sub.get("expiry_date"),
        "admin": False
    }

@router.get("/status")
async def subscription_status(
    user_id: str = Depends(get_current_user_uid),
    user_email: str = Depends(get_current_user_email)
):
    admin_emails = [email.strip().lower() for email in settings.ADMIN_EMAILS if email.strip()]
    is_admin = user_email.lower() in admin_emails
    if is_admin:
        return {"active": True}
    active = check_subscription_active(user_id, user_email)
    return {"active": bool(active)}