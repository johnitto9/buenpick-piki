from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse


def _asset(name: str) -> str:
    return files("piki.web.static").joinpath(name).read_text(encoding="utf-8")


def create_console_router() -> APIRouter:
    router = APIRouter(include_in_schema=False)

    @router.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse("/console", status_code=307)

    @router.get("/console", response_class=HTMLResponse)
    async def console() -> str:
        return _asset("index.html")

    @router.get("/console/assets/app.css", response_class=PlainTextResponse)
    async def styles() -> PlainTextResponse:
        return PlainTextResponse(_asset("app.css"), media_type="text/css")

    @router.get("/console/assets/app.js", response_class=PlainTextResponse)
    async def script() -> PlainTextResponse:
        return PlainTextResponse(
            _asset("app.js"), media_type="application/javascript"
        )

    return router
