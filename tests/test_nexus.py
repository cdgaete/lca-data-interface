from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lca_data_interface import Database, NexusSession, Pack, PackFile, PackVersion
from lca_data_interface.errors import (
    CredentialsMissing,
    LicenceNotAccepted,
    LoginRefused,
    MissingField,
    NotInCatalog,
    ServiceError,
    TokenRequired,
)
from tests.stub import StubServer

COOKIE = "JSESSIONID=t-1"
JSON_HEADERS = {"Content-Type": "application/json"}
LICENCE = b"%PDF-1.4 invented terms of use here."
PDF_HEADERS = {"Content-Type": "application/pdf", "Content-Length": str(len(LICENCE))}
LICENCE_NAME = "Test-DB-Terms.pdf"
ECOSPOLD = b"PK-invented-ecospold-pack"
ECOSPOLD_NAME = "Test DB - ecoSpold v1.zip"
ZOLCA = b"PK-invented-zolca-pack"
ZOLCA_NAME = "Test DB - openLCA v2.zolca"
EXCEL = b"PK-invented-excel-pack"
EXCEL_NAME = "Test DB - excel v2.zip"

LOGIN_REPLY: dict[str, object] = {
    "admin": False,
    "analyticsOptOut": False,
    "billAddressee1": "SENTINEL-BILL",
    "billAddressee2": None,
    "billCity": "Santiago",
    "billCountry": "Chile",
    "billEmail": "billing@example.org",
    "billState": "RM",
    "billStreet1": "SENTINEL-BILL",
    "billStreet2": None,
    "billZipCode": "8320000",
    "city": "SENTINEL-CITY",
    "country": "Chile",
    "department": None,
    "email": "SENTINEL@example.org",
    "emailValid": True,
    "euVatId": None,
    "fax": None,
    "firstname": "Invented",
    "fullName": "Invented Person",
    "hasOrdered": True,
    "hasShoppingCart": False,
    "id": 1,
    "impersonatedUserId": None,
    "includeCompanyInAddress": False,
    "internal": False,
    "invoiceDueDays": 30,
    "lastLogin": 1791921525000,
    "manager": None,
    "name": "someone@example.org",
    "noEuVatId": False,
    "notifyMaintenance": False,
    "organization": "Invented Org",
    "phone": None,
    "referenceNumber": None,
    "separateBillingAddress": False,
    "state": "RM",
    "street1": "SENTINEL-STREET",
    "street2": None,
    "surname": "Person",
    "zipCode": "8320000",
}

ITEM_11: dict[str, object] = {
    "datafileId": 11,
    "format": {"active": True, "applyLicensor": False, "name": "ecoSpold1", "position": 30},
}
ITEM_12: dict[str, object] = {
    "datafileId": 12,
    "format": {"active": True, "applyLicensor": False, "name": "openLCA zolca", "position": 10},
}
ITEM_21: dict[str, object] = {
    "datafileId": 21,
    "format": {"active": True, "applyLicensor": False, "name": "excel", "position": 0},
}
LICENSE_FILE: dict[str, object] = {
    "belongsTo": None,
    "contentType": "application/pdf",
    "id": 101,
    "name": LICENCE_NAME,
    "publicAccess": True,
}
PACK_1_JSON: dict[str, object] = {
    "licenseFile": LICENSE_FILE,
    "name": "Test DB - ecoSpold",
    "uuid": "p-1",
    "versions": [
        {"items": [ITEM_11], "orderInfos": [], "releaseNote": "First release", "version": 1},
        {"items": [ITEM_12], "orderInfos": [], "releaseNote": None, "version": 2},
    ],
}
PACK_2_JSON: dict[str, object] = {
    "licenseFile": None,
    "name": "Test DB - excel",
    "uuid": "p-2",
    "versions": [{"items": [ITEM_21], "orderInfos": [], "releaseNote": None, "version": 2}],
}
CATALOG: list[dict[str, object]] = [
    {"name": "Test DB", "packs": [PACK_1_JSON, PACK_2_JSON], "type": "FREE_DATABASE"}
]

PACK_1 = Pack(
    "p-1",
    "Test DB - ecoSpold",
    101,
    (
        PackVersion(1, "First release", (PackFile(11, "ecoSpold1"),)),
        PackVersion(2, None, (PackFile(12, "openLCA zolca"),)),
    ),
)
PACK_2 = Pack("p-2", "Test DB - excel", None, (PackVersion(2, None, (PackFile(21, "excel"),)),))


def route_file(stub: StubServer, datafile_id: int, body: bytes, name: str) -> None:
    """Answer the download of one datafile with `body` served under `name`."""
    stub.route(
        "GET",
        f"/ws/user/downloads/download?datafileId={datafile_id}",
        200,
        body,
        {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(body)),
            "Content-Disposition": f"attachment; filename={name}",
        },
        cookie=COOKIE,
    )


def register_catalog(
    stub: StubServer,
    *,
    reply: dict[str, object] | None = None,
    catalog: list[dict[str, object]] | None = None,
) -> None:
    """Answer the login, the logout, the catalog and every file the catalog names."""
    stub.route(
        "POST",
        "/ws/session/login",
        200,
        json.dumps(LOGIN_REPLY if reply is None else reply).encode(),
        {**JSON_HEADERS, "Set-Cookie": f"{COOKIE}; Path=/"},
    )
    stub.route("POST", "/ws/session/logout", 200, b"", {}, cookie=COOKIE)
    stub.route(
        "GET",
        "/ws/user/downloads",
        200,
        json.dumps(CATALOG if catalog is None else catalog).encode(),
        JSON_HEADERS,
        cookie=COOKIE,
    )
    stub.route(
        "GET",
        "/ws/files/101",
        200,
        LICENCE,
        {**PDF_HEADERS, "Content-Disposition": f"attachment; filename={LICENCE_NAME}"},
        cookie=COOKIE,
    )
    route_file(stub, 11, ECOSPOLD, ECOSPOLD_NAME)
    route_file(stub, 12, ZOLCA, ZOLCA_NAME)
    route_file(stub, 21, EXCEL, EXCEL_NAME)


def test_missing_credentials_name_the_variables_that_are_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NEXUS_USERNAME", raising=False)
    monkeypatch.delenv("NEXUS_PASSWORD", raising=False)
    with pytest.raises(CredentialsMissing) as raised:
        NexusSession.from_environment()
    assert raised.value.variables == ("NEXUS_USERNAME", "NEXUS_PASSWORD")
    monkeypatch.setenv("NEXUS_PASSWORD", "not-a-password")
    with pytest.raises(CredentialsMissing) as raised:
        NexusSession.from_environment()
    assert raised.value.variables == ("NEXUS_USERNAME",)


@pytest.mark.usefixtures("credentials")
def test_a_session_logs_in_once_and_out_on_leaving(stub: StubServer, cache: Path) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        nexus.catalog()
        nexus.licence(nexus.pack("p-1"))
        nexus.download(nexus.pack("p-2"), version=2, file_format="excel")
    calls = [(request.method, request.path) for request in stub.requests]
    assert calls.count(("POST", "/ws/session/login")) == 1
    assert calls[-1] == ("POST", "/ws/session/logout")
    assert all(COOKIE in request.headers.get("Cookie", "") for request in stub.requests[1:])


@pytest.mark.usefixtures("credentials")
def test_a_logout_the_server_refuses_is_a_service_error(stub: StubServer, cache: Path) -> None:
    register_catalog(stub)
    stub.route("POST", "/ws/session/logout", 500, b"boom", {}, cookie=COOKIE)
    with pytest.raises(ServiceError) as raised:
        with NexusSession.from_environment(base=stub.base):
            pass
    assert (raised.value.call, raised.value.status) == ("POST /ws/session/logout", 500)
    assert "boom" in raised.value.detail


@pytest.mark.usefixtures("credentials")
def test_a_refused_logout_does_not_hide_the_error_leaving_the_block(
    stub: StubServer, cache: Path
) -> None:
    register_catalog(stub)
    stub.route("POST", "/ws/session/logout", 500, b"boom", {}, cookie=COOKIE)
    with pytest.raises(NotInCatalog) as raised:
        with NexusSession.from_environment(base=stub.base) as nexus:
            nexus.pack("p-9")
    assert raised.value.uuid == "p-9"


def test_the_login_sends_the_token_when_one_is_set(
    stub: StubServer, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    register_catalog(stub)
    monkeypatch.setenv("NEXUS_USERNAME", "someone@example.org")
    monkeypatch.setenv("NEXUS_PASSWORD", "not-a-password")
    monkeypatch.setenv("NEXUS_TOKEN", "123456")
    with NexusSession.from_environment(base=stub.base):
        pass
    monkeypatch.delenv("NEXUS_TOKEN")
    with NexusSession.from_environment(base=stub.base):
        pass
    logins = [request for request in stub.requests if request.path == "/ws/session/login"]
    assert [json.loads(request.body)["token"] for request in logins] == ["123456", ""]


@pytest.mark.usefixtures("credentials")
def test_an_account_with_a_second_factor_and_no_token_is_refused_by_name(
    stub: StubServer, cache: Path
) -> None:
    register_catalog(stub, reply={**LOGIN_REPLY, "tokenRequired": True})
    with pytest.raises(TokenRequired) as raised:
        with NexusSession.from_environment(base=stub.base):
            pass
    assert "NEXUS_TOKEN" in str(raised.value)


@pytest.mark.usefixtures("credentials")
def test_a_refused_login_names_the_account_never_the_password(
    stub: StubServer, cache: Path
) -> None:
    stub.route("POST", "/ws/session/login", 401, b"", {})
    with pytest.raises(LoginRefused) as raised:
        with NexusSession.from_environment(base=stub.base):
            pass
    assert "someone@example.org" in str(raised.value) and "not-a-password" not in str(raised.value)
    assert raised.value.status == 401


@pytest.mark.usefixtures("credentials")
def test_the_login_reply_leaves_no_trace(
    stub: StubServer, cache: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        nexus.catalog()
        nexus.licence(nexus.pack("p-1"))
        nexus.download(nexus.pack("p-2"), version=2, file_format="excel")
        rendered = repr(nexus)
        attributes = repr(vars(nexus))
    captured = capsys.readouterr()
    assert "SENTINEL" not in rendered
    assert "SENTINEL" not in attributes
    assert "SENTINEL" not in captured.out + captured.err
    assert not [
        path for path in cache.rglob("*") if path.is_file() and b"SENTINEL" in path.read_bytes()
    ]


@pytest.mark.usefixtures("credentials")
def test_the_catalog_is_typed_records(stub: StubServer, cache: Path) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        databases = nexus.catalog()
    assert databases == [Database("Test DB", "FREE_DATABASE", (PACK_1, PACK_2))]
    assert databases[0].packs[0] == PACK_1


@pytest.mark.usefixtures("credentials")
def test_a_catalog_entry_without_a_field_names_the_call_and_the_field(
    stub: StubServer, cache: Path
) -> None:
    without_uuid = {key: value for key, value in PACK_1_JSON.items() if key != "uuid"}
    register_catalog(
        stub,
        catalog=[{"name": "Test DB", "packs": [without_uuid], "type": "FREE_DATABASE"}],
    )
    with pytest.raises(MissingField) as raised:
        with NexusSession.from_environment(base=stub.base) as nexus:
            nexus.catalog()
    assert (raised.value.call, raised.value.field) == ("GET /ws/user/downloads", "packs[].uuid")
    without_id = {**PACK_1_JSON, "licenseFile": {"contentType": "application/pdf"}}
    register_catalog(
        stub,
        catalog=[{"name": "Test DB", "packs": [without_id], "type": "FREE_DATABASE"}],
    )
    with pytest.raises(MissingField) as raised:
        with NexusSession.from_environment(base=stub.base) as nexus:
            nexus.catalog()
    assert (raised.value.call, raised.value.field) == (
        "GET /ws/user/downloads",
        "packs[].licenseFile.id",
    )


@pytest.mark.usefixtures("credentials")
def test_a_pack_the_catalog_lacks_is_not_in_the_catalog(stub: StubServer, cache: Path) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        with pytest.raises(NotInCatalog) as raised:
            nexus.pack("p-9")
    assert raised.value.uuid == "p-9"
    assert raised.value.available == ("p-1", "p-2")
    assert str(raised.value) == "the catalog has no entry for pack p-9; it holds p-1, p-2"


@pytest.mark.usefixtures("credentials")
def test_a_version_or_format_the_pack_lacks_names_what_the_pack_has(
    stub: StubServer, cache: Path
) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        with pytest.raises(NotInCatalog) as raised:
            nexus.download(
                nexus.pack("p-1"), version=3, file_format="ecoSpold1", accept_licence=True
            )
    assert raised.value.available == ("version 1: ecoSpold1", "version 2: openLCA zolca")
    assert not [request for request in stub.requests if "/download?" in request.path]


@pytest.mark.usefixtures("credentials")
def test_a_pack_with_a_licence_downloads_only_once_it_is_accepted(
    stub: StubServer, cache: Path
) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        pack = nexus.pack("p-1")
        with pytest.raises(LicenceNotAccepted) as raised:
            nexus.download(pack, version=1, file_format="ecoSpold1")
        assert (raised.value.uuid, raised.value.licence_file) == ("p-1", 101)
        assert not [request for request in stub.requests if "/download?" in request.path]
        got = nexus.download(pack, version=1, file_format="ecoSpold1", accept_licence=True)
    assert got.path == cache / "nexus" / "p-1" / "1" / "ecoSpold1" / ECOSPOLD_NAME
    assert (got.size, got.sha256) == (len(ECOSPOLD), hashlib.sha256(ECOSPOLD).hexdigest())


@pytest.mark.usefixtures("credentials")
def test_a_pack_without_a_licence_downloads_without_acceptance(
    stub: StubServer, cache: Path
) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        got = nexus.download(nexus.pack("p-2"), version=2, file_format="excel")
    assert got.path == cache / "nexus" / "p-2" / "2" / "excel" / EXCEL_NAME


@pytest.mark.usefixtures("credentials")
def test_the_licence_file_lands_in_the_pack_s_cache(stub: StubServer, cache: Path) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        pack = nexus.pack("p-1")
        got = nexus.licence(pack)
        assert nexus.licence(pack) == got
    assert got == cache / "nexus" / "p-1" / "licence" / LICENCE_NAME
    assert len([request for request in stub.requests if request.path == "/ws/files/101"]) == 1


@pytest.mark.usefixtures("credentials")
def test_a_pack_without_a_licence_file_has_none_to_fetch(stub: StubServer, cache: Path) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        with pytest.raises(NotInCatalog) as raised:
            nexus.licence(nexus.pack("p-2"))
    assert (raised.value.uuid, raised.value.wanted, raised.value.available) == (
        "p-2",
        "licence file",
        (),
    )
    assert str(raised.value) == "the catalog has no licence file for pack p-2; it holds nothing"
    assert not [request for request in stub.requests if request.path.startswith("/ws/files")]


@pytest.mark.usefixtures("credentials")
def test_a_second_download_of_a_pack_file_makes_no_download_request(
    stub: StubServer, cache: Path
) -> None:
    register_catalog(stub)
    with NexusSession.from_environment(base=stub.base) as nexus:
        pack = nexus.pack("p-2")
        first = nexus.download(pack, version=2, file_format="excel")
        assert nexus.download(pack, version=2, file_format="excel") == first
    assert len([request for request in stub.requests if "/download?" in request.path]) == 1
