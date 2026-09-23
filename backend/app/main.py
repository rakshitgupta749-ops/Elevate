from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import endpoints
from app.services.interview_pipeline import init_interview_pipeline
from app.utils.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Kokoro KPipeline and AsyncOpenAI globally ONCE at startup
    logger.info("Pre-warming global AntigravityInterviewPipeline at server startup...")
    try:
        init_interview_pipeline()
        logger.info("Global AntigravityInterviewPipeline pre-warmed successfully.")
    except Exception as exc:
        logger.error(f"Failed to pre-warm pipeline on startup: {exc}")
    yield

app = FastAPI(title="Elevate API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix="/api")

@app.get("/")
def read_root():
    return {"status": "Elevate API is running"}
