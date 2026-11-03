import httpx

from fastapi import Request
from fastapi.responses import JSONResponse


async def riot_http_error_handler(
    request: Request,
    exc: httpx.HTTPStatusError
) -> JSONResponse:

    status_code = exc.response.status_code

    if status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"detail": "Player or match not found"}
        )

    elif status_code == 429:
        return JSONResponse(
            status_code=503,
            content={"detail": "Riot API rate limit exceeded"}
        )

    else:
        return JSONResponse(
            status_code=502,
            content={"detail": "Riot API error"}
        )


async def riot_connection_error_handler(
    request: Request,
    exc: httpx.RequestError
) -> JSONResponse:

    return JSONResponse(
        status_code=503,
        content={"detail": "Unable to connect to Riot API"}
    )