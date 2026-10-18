from __future__ import annotations

import lca_data_interface
from lca_data_interface.errors import (
    CredentialsMissing,
    LcaDataInterfaceError,
    LicenceNotAccepted,
    LoginRefused,
    MissingField,
    NotInCatalog,
    NotOnServer,
    ServiceError,
    ShortDownload,
    TokenRequired,
)


def test_every_error_is_one_of_the_package_s_own():
    for error in (
        CredentialsMissing(("NEXUS_USERNAME",)),
        LoginRefused("someone", 401),
        TokenRequired(),
        NotInCatalog("u-1", "version 3, format ecoSpold1", ("version 1: ecoSpold1",)),
        LicenceNotAccepted("u-1", 101),
        NotOnServer("g/n", "c0ffee", "not found"),
        MissingField("GET /ws/user/downloads", "packs"),
        ShortDownload("a.zip", 10, 4),
        ServiceError("GET /x", 500, "boom"),
    ):
        assert isinstance(error, LcaDataInterfaceError)


def test_a_refused_login_names_the_account_and_its_status():
    message = str(LoginRefused("someone@example.org", 401))
    assert "someone@example.org" in message and "401" in message


def test_a_missing_token_names_the_variable_that_carries_it():
    assert "NEXUS_TOKEN" in str(TokenRequired())


def test_a_pack_entry_the_catalog_lacks_names_what_was_asked_and_what_the_pack_has():
    message = str(
        NotInCatalog(
            "u-1", "version 3, format ecoSpold1", ("version 1: ecoSpold1", "version 2: excel")
        )
    )
    assert (
        "u-1" in message
        and "version 3, format ecoSpold1" in message
        and "version 2: excel" in message
    )


def test_a_short_download_names_the_file_and_both_lengths():
    message = str(ShortDownload("a.zip", 10, 4))
    assert "a.zip" in message and "10" in message and "4" in message


def test_the_version_is_the_package_s():
    assert lca_data_interface.__version__ == "0.1.0"
