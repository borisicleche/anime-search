from fastapi import FastAPI
from pydantic import BaseModel

from app.routers import anime

app = FastAPI(title="anime-search AI service")
app.include_router(anime.router)


class HealthResponse(BaseModel):
    status: str


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
