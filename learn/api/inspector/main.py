"""HTTP surface of the inspector. Internal-only: reachable from learn-web over the internal network, never
published to the host. No interactive docs or OpenAPI schema are served, and errors never echo configuration."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import service
from .rpc import RpcError

log = logging.getLogger("inspector")
app = FastAPI(title="defi-sec-lab inspector", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/v1/inspection")
def inspection(source: str = Query("fork", pattern="^(fork|live)$")) -> dict:
    try:
        return service.get(source)
    except service.NotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except RpcError as exc:  # message is already URL-free
        raise HTTPException(status_code=502, detail=str(exc)) from None


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled %s", type(exc).__name__)  # type only: never the exception text
    return JSONResponse(status_code=500, content={"detail": "internal error"})
