import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..db import Store
from . import passwords
from .dependencies import singleton
from .sessions import Sessions
from .templating import templates

log = logging.getLogger(__name__)


class NotAuthenticated(Exception):
    pass


def ensure_admin_password(store: Store) -> None:
    if passwords.env_password():
        log.info(
            "admin password taken from environment",
            extra={"env_var": passwords.ENV_VAR},
        )
        return
    if store.auth.credentials() is not None:
        return
    password = passwords.generate()
    store.auth.set_password(*passwords.hash_password(password))
    passwords.announce(password)


def check_password(store: Store, password: str) -> bool:
    env = passwords.env_password()
    if env is not None:
        return hmac.compare_digest(password.encode(), env.encode())
    credentials = store.auth.credentials()
    if credentials is None:
        return False
    return passwords.verify(password, credentials.password_hash, credentials.salt)


def get_router(store: Store, sessions: Sessions) -> APIRouter:
    provide_store = singleton(store)
    provide_sessions = singleton(sessions)
    router = APIRouter()

    @router.get("/login", response_class=HTMLResponse)
    async def login_form(request: Request):
        return templates.TemplateResponse(request, "login.html", {})

    @router.post("/login")
    async def login(
        store: Annotated[Store, Depends(provide_store)],
        sessions: Annotated[Sessions, Depends(provide_sessions)],
        password: Annotated[str, Form()],
    ):
        if not check_password(store, password):
            return RedirectResponse("/login?error=1", status_code=303)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("session", sessions.issue(), httponly=True, samesite="lax")
        return response

    return router
