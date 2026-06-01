import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging early
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Log startup immediately
logger.info("Starting InvestWise API...")

# Import dependencies after logging setup to catch import errors
try:
    from app.database import get_db
    from app.routers import stocks, news, lessons, subscription, admin, ai_research, backtest
    from app.services.scheduler import start_scheduler, stop_scheduler, manual_refresh
    from app.services.stock_service import get_latest_predictions_from_firestore
    logger.info("All modules imported successfully")
except Exception as e:
    logger.error(f"Import error: {e}", exc_info=True)
    sys.exit(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up InvestWise API")
    try:
        db = get_db()
        db.collection("_test").document("ping").set({"ts": "startup"})
        logger.info("Firestore connection verified")
    except Exception as e:
        logger.error(f"Firestore connection failed: {e}", exc_info=True)
    try:
        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}", exc_info=True)
    try:
        predictions = get_latest_predictions_from_firestore()
        if not predictions or all(p.get("price") is None for p in predictions):
            logger.info("No predictions found, running initial refresh")
            manual_refresh()
    except Exception as e:
        logger.error(f"Initial refresh failed: {e}", exc_info=True)
    yield
    logger.info("Shutting down InvestWise API")
    stop_scheduler()

# FastAPI with redirect_slashes=False to prevent CORS loss on redirects
app = FastAPI(title="InvestWise API", lifespan=lifespan, redirect_slashes=False)

# CORS – allow both local development and live frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://dumakulem300.github.io",           # live frontend
        os.getenv("FRONTEND_URL", "")
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stocks.router)
app.include_router(news.router)
app.include_router(lessons.router)
app.include_router(subscription.router)
app.include_router(admin.router)
app.include_router(ai_research.router)
app.include_router(backtest.router)   # Phase H

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
