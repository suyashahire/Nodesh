from collections import defaultdict
import time

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nodesh_api.config import get_settings
from nodesh_api.routers.analyze import router as analyze_router
from nodesh_api.routers.concepts import router as concepts_router
from nodesh_api.routers.documents import router as documents_router
from nodesh_api.routers.graph import router as graph_router
from nodesh_api.routers.relationships import router as relationships_router
from nodesh_api.routers.workspaces import router as workspaces_router


app = FastAPI(title="Nodesh API", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(workspaces_router)
app.include_router(documents_router)
app.include_router(concepts_router)
app.include_router(relationships_router)
app.include_router(graph_router)
app.include_router(analyze_router)

# In-memory sliding window rate limiting
_request_history: dict[str, list[float]] = defaultdict(list)
_upload_history: dict[str, list[float]] = defaultdict(list)
_analyze_history: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    # 1. Request body size check for non-multipart requests (1MB cap)
    content_length = request.headers.get("content-length")
    content_type = request.headers.get("content-type", "")
    if content_length and "multipart/form-data" not in content_type:
        try:
            if int(content_length) > 1024 * 1024:
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Request body exceeds maximum allowed size of 1MB"},
                )
        except ValueError:
            pass

    # 2. Sliding window rate limiter
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    path = request.url.path
    method = request.method

    # Clean history older than 60 seconds
    cutoff = now - 60.0
    _request_history[client_ip] = [t for t in _request_history[client_ip] if t > cutoff]

    if len(_request_history[client_ip]) >= 300:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Maximum 300 requests per minute."},
            headers={"Retry-After": "60"},
        )
    _request_history[client_ip].append(now)

    # Route-specific rate limits for expensive operations
    if method == "POST" and "/documents" in path:
        _upload_history[client_ip] = [t for t in _upload_history[client_ip] if t > cutoff]
        if len(_upload_history[client_ip]) >= 60:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Upload rate limit exceeded. Maximum 60 uploads per minute."},
                headers={"Retry-After": "60"},
            )
        _upload_history[client_ip].append(now)

    elif method == "POST" and "/analyze" in path:
        _analyze_history[client_ip] = [t for t in _analyze_history[client_ip] if t > cutoff]
        if len(_analyze_history[client_ip]) >= 40:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Analysis rate limit exceeded. Maximum 40 analyses per minute."},
                headers={"Retry-After": "60"},
            )
        _analyze_history[client_ip].append(now)

    # Execute request
    response = await call_next(request)

    # 3. Security headers
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; frame-ancestors 'none'; object-src 'none';",
    )
    return response


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return process health without requiring external dependencies."""
    return {"status": "ok", "service": "nodesh-api"}
