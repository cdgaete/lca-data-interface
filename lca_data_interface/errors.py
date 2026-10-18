"""The errors this package raises, each naming what a caller can act on."""

from __future__ import annotations


class LcaDataInterfaceError(Exception):
    """The base of every error this package raises."""


class CredentialsMissing(LcaDataInterfaceError):
    """An environment variable a source needs is absent."""

    def __init__(self, variables: tuple[str, ...]) -> None:
        self.variables = variables
        verb = "is" if len(variables) == 1 else "are"
        super().__init__(f"{' and '.join(variables)} {verb} not set")


class LoginRefused(LcaDataInterfaceError):
    """openLCA Nexus refused the account's login; the password is never named."""

    def __init__(self, account: str, status: int) -> None:
        self.account = account
        self.status = status
        super().__init__(f"openLCA Nexus refused the login of {account} with status {status}")


class TokenRequired(LcaDataInterfaceError):
    """openLCA Nexus asks for a second factor and the token variable is absent."""

    def __init__(self) -> None:
        super().__init__("openLCA Nexus asks for a second factor; set NEXUS_TOKEN")


class NotInCatalog(LcaDataInterfaceError):
    """A pack, version, format or licence file the catalog does not hold."""

    def __init__(self, uuid: str, wanted: str, available: tuple[str, ...]) -> None:
        self.uuid = uuid
        self.wanted = wanted
        self.available = available
        held = ", ".join(available) if available else "none"
        super().__init__(f"pack {uuid} has no {wanted}; it carries {held}")


class LicenceNotAccepted(LcaDataInterfaceError):
    """A pack whose terms must be accepted before its file is downloaded."""

    def __init__(self, uuid: str, licence_file: int) -> None:
        self.uuid = uuid
        self.licence_file = licence_file
        super().__init__(
            f"pack {uuid} carries terms in licence file {licence_file}; "
            f"pass accept_licence=True to download it"
        )


class NotOnServer(LcaDataInterfaceError):
    """A repository or commit a Collaboration Server does not hold."""

    def __init__(self, repository: str, commit: str | None, detail: str) -> None:
        self.repository = repository
        self.commit = commit
        self.detail = detail
        subject = f"{repository} at commit {commit}" if commit else repository
        super().__init__(f"the server does not have {subject}: {detail}")


class MissingField(LcaDataInterfaceError):
    """A response lacks a field the client reads."""

    def __init__(self, call: str, field: str) -> None:
        self.call = call
        self.field = field
        super().__init__(f"{call} carries no {field}")


class ShortDownload(LcaDataInterfaceError):
    """A body that ended before the length its response announced."""

    def __init__(self, name: str, expected: int, received: int) -> None:
        self.name = name
        self.expected = expected
        self.received = received
        super().__init__(f"{name} ended after {received} of {expected} bytes")


class ServiceError(LcaDataInterfaceError):
    """A refused status, an unreachable host, or a malformed answer."""

    def __init__(self, call: str, status: int | None, detail: str) -> None:
        self.call = call
        self.status = status
        self.detail = detail
        failure = f"status {status}" if status is not None else "an unreachable host"
        super().__init__(f"{call} failed with {failure}: {detail}")
