import uuid
from datetime import datetime, timedelta, timezone
from firebase_admin import firestore
from app.database import db
from app.models import PAYMENTS_COLLECTION, SUBSCRIPTIONS_COLLECTION
from app.config import settings

def create_payment(user_id: str, amount: float, screenshot_base64: str, plan: str) -> str:
    payment_id = str(uuid.uuid4())
    payment_ref = db.collection(PAYMENTS_COLLECTION).document(payment_id)
    payment_ref.set({
        "payment_id": payment_id,
        "user_id": user_id,
        "amount": amount,
        "plan": plan,
        "screenshot_base64": screenshot_base64,
        "status": "pending",
        "created_at": firestore.SERVER_TIMESTAMP
    })
    return payment_id

def verify_payment(payment_id: str, admin_id: str):
    payment_ref = db.collection(PAYMENTS_COLLECTION).document(payment_id)
    payment = payment_ref.get()
    if not payment.exists:
        raise ValueError("Payment not found")
    data = payment.to_dict()
    if data.get("status") != "pending":
        raise ValueError("Payment already processed")
    user_id = data["user_id"]
    plan = data["plan"]
    payment_ref.update({
        "status": "verified",
        "verified_by_admin_id": admin_id,
        "verified_at": firestore.SERVER_TIMESTAMP
    })
    activate_subscription(user_id, plan)

def reject_payment(payment_id: str, admin_id: str):
    payment_ref = db.collection(PAYMENTS_COLLECTION).document(payment_id)
    payment = payment_ref.get()
    if not payment.exists:
        raise ValueError("Payment not found")
    data = payment.to_dict()
    if data.get("status") != "pending":
        raise ValueError("Payment already processed")
    payment_ref.update({
        "status": "rejected",
        "rejected_by_admin_id": admin_id,
        "rejected_at": firestore.SERVER_TIMESTAMP
    })

def activate_subscription(user_id: str, plan: str):
    now = datetime.now(timezone.utc)
    if plan == "monthly":
        days = 30
    elif plan == "yearly":
        days = 365
    else:
        raise ValueError("Invalid plan")
    expiry = now + timedelta(days=days)
    subs_ref = db.collection(SUBSCRIPTIONS_COLLECTION).document(user_id)
    subs_ref.set({
        "user_id": user_id,
        "plan": plan,
        "start_date": now,
        "expiry_date": expiry,
        "active": True,
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)

def get_user_subscription(user_id: str) -> dict:
    subs_ref = db.collection(SUBSCRIPTIONS_COLLECTION).document(user_id)
    doc = subs_ref.get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    if data.get("start_date") is not None:
        data["start_date"] = data["start_date"].isoformat()
    if data.get("expiry_date") is not None:
        data["expiry_date"] = data["expiry_date"].isoformat()
    return data

def _to_datetime(value):
    """Convert various Firestore date representations to timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        # Ensure it's timezone-aware; if naive, assume UTC
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            return None
    # Firestore Timestamp object
    if hasattr(value, 'timestamp'):
        return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc)
    # dict with _seconds
    if isinstance(value, dict) and '_seconds' in value:
        return datetime.fromtimestamp(value['_seconds'], tz=timezone.utc)
    return None

def check_subscription_active(user_id: str, user_email: str = None) -> bool:
    # Admin override
    if user_email and user_email in settings.ADMIN_EMAILS:
        return True

    subs = get_user_subscription(user_id)
    if not subs:
        return False

    active = subs.get("active", False)
    if not active:
        return False

    expiry_raw = subs.get("expiry_date")
    # If expiry_date is missing/null and active is true → treat as lifetime subscription
    if expiry_raw is None:
        return True

    # expiry_raw may be string from get_user_subscription conversion or original Timestamp
    if isinstance(expiry_raw, str):
        try:
            expiry = datetime.fromisoformat(expiry_raw)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except:
            return False
    else:
        expiry = _to_datetime(expiry_raw)
        if expiry is None:
            # Invalid expiry format, but active is true – fallback to lifetime
            return True

    return expiry > datetime.now(timezone.utc)
