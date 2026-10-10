from fastapi import FastAPI

from app.routes.analyze import router as analyze_router

app = FastAPI(title="Hedgehog API")
app.include_router(analyze_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
