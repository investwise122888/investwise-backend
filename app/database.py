from app.config import settings
import firebase_admin
from firebase_admin import credentials, firestore

# Get credentials as a dictionary (either from env var or from file)
cred_dict = settings.get_firebase_credentials()
cred = credentials.Certificate(cred_dict)

# Initialize Firebase app
firebase_admin.initialize_app(cred)
db = firestore.client()

def get_db():
    return db