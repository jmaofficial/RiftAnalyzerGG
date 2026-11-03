import httpx

from fastapi import FastAPI

from app.api.players import router as players_router
from app.core.exception_handlers import (
    riot_http_error_handler,
    riot_connection_error_handler,
)


app = FastAPI(
    title="RiftAnalyzerGG API",
    version="0.1.0"
)

app.include_router(players_router)

# Global exception handlers
app.add_exception_handler(
    httpx.HTTPStatusError,
    riot_http_error_handler
)

app.add_exception_handler(
    httpx.RequestError,
    riot_connection_error_handler
)


@app.get("/health")
def health_check():
    return {"status": "ok"}