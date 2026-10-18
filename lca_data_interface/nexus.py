"""openLCA Nexus: one login a session, its catalog as records, and a pack's files in the cache."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Final, cast

from lca_data_interface.cache import Downloaded, cache_dir, cached, fetch
from lca_data_interface.errors import (
    CredentialsMissing,
    LicenceNotAccepted,
    LoginRefused,
    NotInCatalog,
    TokenRequired,
)
from lca_data_interface.fields import field
from lca_data_interface.transport import ensure_ok, json_of, new_session, send

DEFAULT_BASE: Final = "https://nexus.openlca.org"
CATALOG_CALL: Final = "GET /ws/user/downloads"
CREDENTIAL_VARIABLES: Final = ("NEXUS_USERNAME", "NEXUS_PASSWORD")


@dataclass(frozen=True)
class PackFile:
    """One downloadable file of a pack version, by its datafile id and its format's name."""

    datafile_id: int
    file_format: str


@dataclass(frozen=True)
class PackVersion:
    """One version of a pack, with its release note and the files it carries."""

    number: int
    release_note: str | None
    files: tuple[PackFile, ...]


@dataclass(frozen=True)
class Pack:
    """A downloadable pack: its uuid, its name, its licence file's id and its versions."""

    uuid: str
    name: str
    licence_file: int | None
    versions: tuple[PackVersion, ...]


@dataclass(frozen=True)
class Database:
    """A database in the catalog, with its type and its packs."""

    name: str
    type: str
    packs: tuple[Pack, ...]


class NexusSession:
    """A logged-in openLCA Nexus account: one login, the catalog it reads once, and its files."""

    def __init__(
        self,
        account: str,
        password: str,
        *,
        token: str | None = None,
        base: str = DEFAULT_BASE,
    ) -> None:
        self.base = base
        self._account = account
        self._password = password
        self._token = token
        self._session = new_session()
        self._catalog: list[Database] | None = None

    @classmethod
    def from_environment(cls, *, base: str = DEFAULT_BASE) -> NexusSession:
        """A session whose account, password and token the `NEXUS_*` variables name."""
        absent = tuple(name for name in CREDENTIAL_VARIABLES if not os.environ.get(name))
        if absent:
            raise CredentialsMissing(absent)
        return cls(
            os.environ["NEXUS_USERNAME"],
            os.environ["NEXUS_PASSWORD"],
            token=os.environ.get("NEXUS_TOKEN"),
            base=base,
        )

    def __repr__(self) -> str:
        """Name the server and the account, never the password or the token."""
        return f"NexusSession(base={self.base!r}, account={self._account!r})"

    def __enter__(self) -> NexusSession:
        """Log in once; a refusal names the reason and the reply itself is dropped."""
        call = "POST /ws/session/login"
        response = send(
            self._session,
            "POST",
            f"{self.base}/ws/session/login",
            call=call,
            body={"name": self._account, "password": self._password, "token": self._token or ""},
        )
        if response.status_code in (401, 403):
            raise LoginRefused(self._account, response.status_code)
        ensure_ok(response, call=call)
        reply = cast(dict[str, object], json_of(response, call=call))
        if reply.get("tokenRequired") is True:
            raise TokenRequired()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Log out."""
        send(
            self._session,
            "POST",
            f"{self.base}/ws/session/logout",
            call="POST /ws/session/logout",
        )

    def catalog(self) -> list[Database]:
        """Every database the account may download, read from the server once per session."""
        held = self._catalog
        if held is None:
            response = send(
                self._session, "GET", f"{self.base}/ws/user/downloads", call=CATALOG_CALL
            )
            ensure_ok(response, call=CATALOG_CALL)
            entries = cast(list[dict[str, object]], json_of(response, call=CATALOG_CALL))
            held = [_database(entry, call=CATALOG_CALL) for entry in entries]
            self._catalog = held
        return held

    def pack(self, uuid: str) -> Pack:
        """The catalog's pack with `uuid`; a uuid it lacks is refused, never replaced."""
        packs = tuple(pack for database in self.catalog() for pack in database.packs)
        matched = [pack for pack in packs if pack.uuid == uuid]
        if not matched:
            raise NotInCatalog(uuid, "such pack", tuple(pack.uuid for pack in packs))
        return matched[0]

    def licence(self, pack: Pack) -> Path:
        """The pack's licence file, from the cache or downloaded into it."""
        if pack.licence_file is None:
            raise NotInCatalog(pack.uuid, "licence file", ())
        directory = cache_dir() / "nexus" / pack.uuid / "licence"
        held = cached(directory)
        if held is not None:
            return held.path
        call = f"GET /ws/files/{pack.licence_file}"
        return fetch(
            self._session, f"{self.base}/ws/files/{pack.licence_file}", directory, call=call
        ).path

    def download(
        self,
        pack: Pack,
        *,
        version: int,
        file_format: str,
        accept_licence: bool = False,
    ) -> Downloaded:
        """One file of a pack version, from the cache or downloaded once its licence is accepted."""
        wanted = _wanted_file(pack, version=version, file_format=file_format)
        if pack.licence_file is not None and not accept_licence:
            raise LicenceNotAccepted(pack.uuid, pack.licence_file)
        directory = cache_dir() / "nexus" / pack.uuid / str(version) / file_format
        held = cached(directory)
        if held is not None:
            return held
        call = f"GET /ws/user/downloads/download?datafileId={wanted.datafile_id}"
        return fetch(
            self._session,
            f"{self.base}/ws/user/downloads/download?datafileId={wanted.datafile_id}",
            directory,
            call=call,
        )


def _database(record: dict[str, object], *, call: str) -> Database:
    """A catalog entry as a database record."""
    return Database(
        name=cast(str, field(record, "name", call=call)),
        type=cast(str, field(record, "type", call=call)),
        packs=tuple(
            _pack(pack, call=call)
            for pack in cast(list[dict[str, object]], field(record, "packs", call=call))
        ),
    )


def _pack(record: dict[str, object], *, call: str) -> Pack:
    """A catalog pack as a record, its licence file by the id the record nests."""
    licence = field(record, "packs[].licenseFile", call=call)
    return Pack(
        uuid=cast(str, field(record, "packs[].uuid", call=call)),
        name=cast(str, field(record, "packs[].name", call=call)),
        licence_file=(
            None
            if licence is None
            else cast(int, field(record, "packs[].licenseFile.id", call=call))
        ),
        versions=tuple(
            _version(version, call=call)
            for version in cast(
                list[dict[str, object]], field(record, "packs[].versions", call=call)
            )
        ),
    )


def _version(record: dict[str, object], *, call: str) -> PackVersion:
    """A pack version as a record, with its release note and its files."""
    return PackVersion(
        number=cast(int, field(record, "packs[].versions[].version", call=call)),
        release_note=cast(str | None, field(record, "packs[].versions[].releaseNote", call=call)),
        files=tuple(
            _file(item, call=call)
            for item in cast(
                list[dict[str, object]], field(record, "packs[].versions[].items", call=call)
            )
        ),
    )


def _file(record: dict[str, object], *, call: str) -> PackFile:
    """One file of a pack version as a record, by its datafile id and its format's name."""
    return PackFile(
        datafile_id=cast(int, field(record, "packs[].versions[].items[].datafileId", call=call)),
        file_format=cast(str, field(record, "packs[].versions[].items[].format.name", call=call)),
    )


def _wanted_file(pack: Pack, *, version: int, file_format: str) -> PackFile:
    """The pack's file at a version and a format, refused with what the pack carries when absent."""
    available = tuple(
        f"version {held.number}: {candidate.file_format}"
        for held in pack.versions
        for candidate in held.files
    )
    matched = [
        candidate
        for held in pack.versions
        if held.number == version
        for candidate in held.files
        if candidate.file_format == file_format
    ]
    if not matched:
        raise NotInCatalog(pack.uuid, f"version {version}, format {file_format}", available)
    return matched[0]
