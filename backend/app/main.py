import httpx

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.players import router as players_router
from app.api.matches import router as matches_router
from app.api.analysis import router as analysis_router
from app.services.match_service import InvalidMatchData
from app.core.exception_handlers import (
    riot_http_error_handler,
    riot_connection_error_handler,
)


app = FastAPI(
    title="RiftAnalyzerGG API",
    version="0.1.0"
)

app.include_router(players_router)
app.include_router(matches_router)
app.include_router(analysis_router)


@app.exception_handler(InvalidMatchData)
async def invalid_match_handler(request: Request, exc: InvalidMatchData):
    return JSONResponse(status_code=502, content={"detail": str(exc)})

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
