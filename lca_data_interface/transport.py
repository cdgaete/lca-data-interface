"""The HTTP session a source sends through, and the translation of `requests`' failures."""

from __future__ import annotations

import requests

import lca_data_interface
from lca_data_interface.errors import ServiceError


def new_session() -> requests.Session:
    """A session whose User-Agent names this package and its version."""
    session = requests.Session()
    session.headers["User-Agent"] = f"lca-data-interface/{lca_data_interface.__version__}"
    return session


def send(
    session: requests.Session,
    method: str,
    url: str,
    *,
    call: str,
    body: dict[str, str] | None = None,
    stream: bool = False,
) -> requests.Response:
    """Send one request, its body as JSON, and return the response whatever its status."""
    try:
        return session.request(method, url, json=body, stream=stream)
    except requests.RequestException as error:
        raise ServiceError(call, None, str(error)) from error


def json_of(response: requests.Response, *, call: str) -> object:
    """The body decoded as JSON; a body that is not JSON is a `ServiceError` naming the call."""
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as error:
        raise ServiceError(
            call,
            response.status_code,
            f"the answer is not JSON: {response.text[:200]}",
        ) from error


def ensure_ok(response: requests.Response, *, call: str) -> None:
    """Raise `ServiceError` for a status of 400 or more, naming the call and the answer."""
    if response.status_code >= 400:
        raise ServiceError(call, response.status_code, response.text[:200])
