import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    
    @classmethod
    def get_firebase_credentials(cls):
        # First, try to read from environment variable
        cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            try:
                return json.loads(cred_json)
            except json.JSONDecodeError:
                print("Error: FIREBASE_CREDENTIALS_JSON is not valid JSON")
                # Fall through to file check
        
        # Fallback: look for JSON file in backend folder
        for file in cls.PROJECT_ROOT.glob("*.json"):
            if "firebase" in file.name.lower() or "serviceaccount" in file.name.lower():
                with open(file, 'r') as f:
                    return json.load(f)
        
        raise FileNotFoundError("No Firebase credentials found in environment variable or JSON file")
    
    ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "").split(",")

settings = Settings()