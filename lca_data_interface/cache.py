"""Where files live, the `.part`-then-rename download with its hash, and the cache hit."""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import platformdirs
import requests

from lca_data_interface.errors import (
    CacheUnwritable,
    LcaDataInterfaceError,
    MissingField,
    ServiceError,
    ShortDownload,
)
from lca_data_interface.transport import ensure_ok, send

CHUNK_SIZE: Final = 1024 * 1024
DIGEST_NAME: Final = "sha256.txt"
DIGEST_SEPARATOR: Final = "  "


@dataclass(frozen=True)
class Downloaded:
    """A file in the cache, with the size and digest of the bytes it held when it landed."""

    path: Path
    size: int
    sha256: str


def cache_dir() -> Path:
    """The cache root: the directory `LCA_DATA_INTERFACE_CACHE` names, or the user cache."""
    named = os.environ.get("LCA_DATA_INTERFACE_CACHE")
    return (
        Path(named)
        if named
        else Path(platformdirs.user_cache_dir("lca-data-interface", appauthor=False))
    )


def extended(path: str) -> str:
    """A Windows path in its extended-length form, which the 260-character limit does not bind."""
    if path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def on_disk(path: Path, *, platform: str = sys.platform) -> Path:
    """The path the cache opens: on Windows in its extended-length form, elsewhere as it is."""
    return Path(extended(str(path.absolute()))) if platform == "win32" else path


def cached(directory: Path) -> Downloaded | None:
    """The file `sha256.txt` names, when its bytes hash to the digest written there."""
    folder = on_disk(directory)
    digest_file = folder / DIGEST_NAME
    if not digest_file.is_file():
        return None
    digest, _, recorded = digest_file.read_text(encoding="utf-8").partition(DIGEST_SEPARATOR)
    path = folder / recorded.strip()
    if not path.is_file():
        return None
    size = path.stat().st_size
    read = _digest(path)
    return Downloaded(path, size, read) if read == digest else None


def fetch(
    session: requests.Session,
    url: str,
    directory: Path,
    *,
    call: str,
) -> Downloaded:
    """Stream the body into `directory` under its served name, then record its digest.

    The length is compared here against the `Content-Length` the response announces, so a body
    that stops short is reported with the bytes it reached rather than by urllib3.
    """
    response = send(session, "GET", url, call=call, stream=True)
    ensure_ok(response, call=call)
    name = _served_name(response, call=call)
    announced = response.headers.get("Content-Length")
    response.raw.enforce_content_length = False
    folder = on_disk(directory)
    part = folder / f"{name}.part"
    digest = hashlib.sha256()
    received = 0
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with part.open("wb") as written:
            try:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    written.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
            except requests.RequestException as error:
                raise _interrupted(call, name, announced, received, error) from error
        if announced is not None and received != int(announced):
            raise ShortDownload(name, int(announced), received)
        path = folder / name
        part.replace(path)
        (folder / DIGEST_NAME).write_text(
            f"{digest.hexdigest()}{DIGEST_SEPARATOR}{name}\n", encoding="utf-8"
        )
    except OSError as error:
        unwritable = str(directory / f"{name}.part")
        raise CacheUnwritable(unwritable, len(unwritable), str(error)) from error
    return Downloaded(path, received, digest.hexdigest())


def _digest(path: Path) -> str:
    """The hex SHA-256 of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as read:
        for chunk in iter(lambda: read.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _served_name(response: requests.Response, *, call: str) -> str:
    """The file name `Content-Disposition` serves, taken whole or refused."""
    header = response.headers.get("Content-Disposition")
    if header is None:
        raise MissingField(call, "Content-Disposition")
    _, _, parameter = header.partition("filename=")
    name = parameter.strip().strip('"')
    if Path(name).name != name or not name:
        raise ServiceError(
            call,
            response.status_code,
            f"Content-Disposition serves no file name this cache can hold: {header}",
        )
    return name


def _interrupted(
    call: str,
    name: str,
    announced: str | None,
    received: int,
    error: requests.RequestException,
) -> LcaDataInterfaceError:
    """The error for a body that stopped before the length its response announced."""
    return (
        ServiceError(call, None, str(error))
        if announced is None
        else ShortDownload(name, int(announced), received)
    )
