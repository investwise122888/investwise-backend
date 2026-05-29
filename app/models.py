# Firestore collection names
USERS_COLLECTION = "users"
STOCKS_COLLECTION = "stocks"
PREDICTIONS_COLLECTION = "predictions"
LESSONS_COLLECTION = "lessons"
USER_LESSONS_COLLECTION = "user_lessons"
SUBSCRIPTIONS_COLLECTION = "subscriptions"
PAYMENTS_COLLECTION = "payments"

def doc_to_dict(doc):
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data
