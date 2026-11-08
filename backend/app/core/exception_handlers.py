import httpx

from fastapi import Request, status
from fastapi.responses import JSONResponse


async def riot_http_error_handler(
    request: Request,
    exc: httpx.HTTPStatusError
) -> JSONResponse:
    """Handle HTTP errors returned by the Riot Games API."""

    riot_status = exc.response.status_code

    if riot_status == 404:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Player or match not found"}
        )

    if riot_status == 429:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Riot API rate limit exceeded. Try again later."},
            headers={"Retry-After": exc.response.headers["Retry-After"]}
            if "Retry-After" in exc.response.headers else None,
        )

    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": "An error occurred while communicating with Riot Games API"}
    )


async def riot_connection_error_handler(
    request: Request,
    exc: httpx.RequestError
) -> JSONResponse:
    """Handle connection errors and timeouts."""

    if isinstance(exc, httpx.TimeoutException):
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "Riot Games API did not respond in time"}
        )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Unable to connect to Riot Games API"}
    )
