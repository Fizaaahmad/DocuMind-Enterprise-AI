from starlette.responses import JSONResponse


class BodyLimit:
    """Bound non-upload bodies before parsing, including missing/dishonest lengths."""

    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] in {"GET", "HEAD", "OPTIONS"}
            or (scope["method"] == "POST" and scope["path"].rstrip("/").endswith("/documents"))
        ):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            size = int(headers.get(b"content-length", b"0"))
        except ValueError:
            size = self.limit + 1
        if size < 0 or size > self.limit:
            return await JSONResponse({"detail": "Request exceeds the body limit"}, 413)(
                scope, receive, send
            )
        # Buffer at most limit bytes; bounded JSON payloads are small. This avoids
        # parser middleware converting a receive exception into an unrelated 400.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                return await JSONResponse({"detail": "Request exceeds the body limit"}, 413)(
                    scope, receive, send
                )
            if not message.get("more_body", False):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
