"""A Collaboration Server's released commits, and the download of one into the cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, cast
from urllib.parse import urlparse

import requests

from lca_data_interface.cache import Downloaded, cache_dir, cached, fetch
from lca_data_interface.errors import NotOnServer
from lca_data_interface.fields import field
from lca_data_interface.transport import ensure_ok, json_of, new_session, send

DEFAULT_BASE: Final = "https://www.lcacommons.gov/lca-collaboration"

COMMIT_DIGITS: Final = 12


@dataclass(frozen=True)
class Release:
    """A released commit of a repository, with its version and the time it was released."""

    version: str
    commit: str
    released_at: datetime


class CommonsServer:
    """The public history and downloads of one LCA Collaboration Server."""

    def __init__(self, base: str = DEFAULT_BASE) -> None:
        self.base = base
        self._session = new_session()

    def releases(self, group: str, name: str) -> list[Release]:
        """The released commits of a repository, newest first as the server serves them."""
        call = f"GET /ws/public/history/{group}/{name}"
        response = send(
            self._session, "GET", f"{self.base}/ws/public/history/{group}/{name}", call=call
        )
        _refuse_missing(response, call=call, repository=f"{group}/{name}")
        ensure_ok(response, call=call)
        history = cast(list[dict[str, object]], json_of(response, call=call))
        return [
            Release(
                version=cast(str, field(entry, "releaseInfo.version", call=call)),
                commit=cast(str, field(entry, "id", call=call)),
                released_at=_released_at(cast(int, field(entry, "timestamp", call=call))),
            )
            for entry in history
            if field(entry, "isReleased", call=call) is True
        ]

    def download(self, group: str, name: str, commit: str) -> Downloaded:
        """One released commit's file, from the cache or downloaded into it."""
        directory = (
            cache_dir() / "commons" / _host(self.base) / group / name / commit[:COMMIT_DIGITS]
        )
        held = cached(directory)
        if held is not None:
            return held
        call = f"GET /ws/public/download/json/prepare/{group}/{name}"
        prepared = send(
            self._session,
            "GET",
            f"{self.base}/ws/public/download/json/prepare/{group}/{name}?commitId={commit}",
            call=call,
        )
        _refuse_missing(prepared, call=call, repository=f"{group}/{name}", commit=commit)
        ensure_ok(prepared, call=call)
        token = prepared.text.strip()
        return fetch(
            self._session,
            f"{self.base}/ws/public/download/json/{token}",
            directory,
            call="GET /ws/public/download/json",
        )


def _refuse_missing(
    response: requests.Response,
    *,
    call: str,
    repository: str,
    commit: str | None = None,
) -> None:
    """Raise `NotOnServer` for a 404, with the server's own account of what it lacks."""
    if response.status_code == 404:
        raise NotOnServer(repository, commit, response.text.strip())


def _released_at(milliseconds: int) -> datetime:
    """The UTC instant a count of milliseconds since the epoch names."""
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)


def _host(base: str) -> str:
    """The host of a server's address, which names its directory in the cache."""
    return str(urlparse(base).hostname)
