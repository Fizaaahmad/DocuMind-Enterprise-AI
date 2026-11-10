from fastapi import HTTPException
from starlette.responses import JSONResponse


class UploadLimitMiddleware:
    """Bound multipart bodies even when Content-Length is missing or dishonest."""

    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit + 64 * 1024

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not scope["path"].rstrip("/").endswith("/documents")
        ):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, 400)(
                scope, receive, send
            )
        if declared > self.limit:
            return await JSONResponse({"detail": "Upload exceeds the request limit"}, 413)(
                scope, receive, send
            )
        total = 0
        exceeded = False
        replaced = False

        async def bounded_receive():
            nonlocal total, exceeded
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.limit:
                exceeded = True
                raise HTTPException(413, "Upload exceeds the request limit")
            return message

        async def bounded_send(message):
            nonlocal replaced
            # BaseHTTPMiddleware can wrap receive errors into a parser HTTP 400.
            # Preserve the true failure status at the outer ASGI boundary.
            if exceeded:
                if not replaced:
                    replaced = True
                    await JSONResponse({"detail": "Upload exceeds the request limit"}, 413)(
                        scope, receive, send
                    )
                return
            await send(message)

        await self.app(scope, bounded_receive, bounded_send)
