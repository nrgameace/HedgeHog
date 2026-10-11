import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analyze import router as analyze_router

load_dotenv()

ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]

app = FastAPI(title="Hedgehog API")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST"])
app.include_router(analyze_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
