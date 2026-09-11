from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from .auth import NotAuthenticated


def install(app: FastAPI) -> None:
    @app.exception_handler(NotAuthenticated)
    async def redirect_to_login(request: Request, exc: NotAuthenticated):
        return RedirectResponse("/login", status_code=303)
