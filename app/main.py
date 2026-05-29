import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_db
from app.routers import stocks, news, lessons, subscription, admin
from app.services.scheduler import start_scheduler, stop_scheduler, manual_refresh
from app.services.stock_service import get_latest_predictions_from_firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up InvestWise API")
    try:
        db = get_db()
        db.collection("_test").document("ping").set({"ts": "startup"})
        logger.info("Firestore connection verified")
    except Exception as e:
        logger.error(f"Firestore connection failed: {e}")
    try:
        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")
    try:
        predictions = get_latest_predictions_from_firestore()
        if not predictions or all(p.get("price") is None for p in predictions):
            logger.info("No predictions found, running initial refresh")
            manual_refresh()
    except Exception as e:
        logger.error(f"Initial refresh failed: {e}")
    yield
    logger.info("Shutting down InvestWise API")
    stop_scheduler()

app = FastAPI(title="InvestWise API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        os.getenv("FRONTEND_URL", "http://localhost:3000")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
app.include_router(news.router)
app.include_router(lessons.router)
app.include_router(subscription.router)
app.include_router(admin.router)

@app.get("/")
def root():
    return {"message": "InvestWise API running"}

@app.get("/health")
def health():
    try:
        db = get_db()
        db.collection("_test").document("ping").get()
        return {"status": "healthy", "firestore": "ok"}
    except Exception as e:
        return {"status": "unhealthy", "firestore": str(e)}
