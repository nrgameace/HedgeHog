from fastapi import FastAPI

from app.routes.submissions import router as submissions_router

app = FastAPI(title="Hedgehog API")
app.include_router(submissions_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
