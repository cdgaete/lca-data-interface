"""The live checks: one release the Commons serves, and BAFU's ecoSpold pack at openLCA Nexus."""

from __future__ import annotations

import os

import pytest

from lca_data_interface import CommonsServer, NexusSession

COMMONS_GROUP = "Federal_LCA_Commons"
COMMONS_NAME = "IPCC_GWP"
COMMONS_COMMIT = "f0f90ef2f056be6e1686df0858a57b66ecfa2a62"
BAFU_ECOSPOLD = "c068d31e-7268-4926-8720-b8f9b4648492"
BAFU_ZOLCA = "c31fbb3c-ff98-4f50-8ceb-737ef690ce90"


@pytest.fixture(autouse=True)
def live() -> None:
    """Fail every test of this module unless the live switch is on."""
    if os.environ.get("LCA_DATA_INTERFACE_LIVE") != "1":
        pytest.fail("LCA_DATA_INTERFACE_LIVE is not 1, and these tests reach the services")


@pytest.mark.live
def test_the_commons_serves_ipcc_gwp_at_its_profile_s_commit() -> None:
    """The released commit the IPCC_GWP profile names, with the archive's size and hash."""
    server = CommonsServer()
    assert any(
        release.version == "1.2026-09.2" and release.commit == COMMONS_COMMIT
        for release in server.releases(COMMONS_GROUP, COMMONS_NAME)
    )
    got = server.download(COMMONS_GROUP, COMMONS_NAME, COMMONS_COMMIT)
    assert (got.size, got.sha256) == (
        4002365,
        "951aaf4bf318a34d54e1b3bf553eac7242f46ca14e96d0ef16b821a4c571b785",
    )


@pytest.mark.live
def test_nexus_serves_bafu_s_ecospold_pack_at_its_measured_hash() -> None:
    """BAFU's licence as a PDF, its ecoSpold pack at its hash, and its zolca pack's version."""
    with NexusSession.from_environment() as nexus:
        pack = nexus.pack(BAFU_ECOSPOLD)
        assert nexus.licence(pack).read_bytes()[:4] == b"%PDF"
        got = nexus.download(pack, version=1, file_format="ecoSpold1", accept_licence=True)
        assert (got.size, got.sha256) == (
            37969395,
            "ebaab56717a6227b5eb271fcb4c86fb9db206115eb937fb0ec0b10d7accf26c7",
        )
        zolca = nexus.pack(BAFU_ZOLCA)
        assert any(
            served.file_format == "openLCA zolca"
            for version in zolca.versions
            if version.number == 2
            for served in version.files
        )
