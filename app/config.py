import os
import json
from dotenv import load_dotenv

load_dotenv()

class Settings:
    @staticmethod
    def get_firebase_credentials():
        """Load Firebase credentials from FIREBASE_CREDENTIALS_JSON env var only."""
        cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if not cred_json:
            raise ValueError("FIREBASE_CREDENTIALS_JSON environment variable not set")
        try:
            return json.loads(cred_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"FIREBASE_CREDENTIALS_JSON is not valid JSON: {e}")

    ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "").split(",")

settings = Settings()
