# lca-data-interface

List and download LCA databases from openLCA Nexus and LCA Collaboration Servers into a hash-checked cache.

```bash
pip install lca-data-interface
```

## LCA Collaboration Server

`CommonsServer` reads one server's public release history and downloads a released commit. It needs no account, and its default server is the Federal LCA Commons at `https://www.lcacommons.gov/lca-collaboration`; `CommonsServer(base)` names another address.

`releases(group, name)` answers that repository's released commits, in the order the server serves them, each a `Release` carrying `version`, `commit` and `released_at`, the last a UTC `datetime` built from the server's millisecond timestamp. `download(group, name, commit)` answers a `Downloaded` carrying the `path` of the file in the cache, its `size` in bytes and its `sha256` digest.

```python
from lca_data_interface import CommonsServer

server = CommonsServer()
releases = server.releases("Federal_LCA_Commons", "IPCC_GWP")
newest = releases[0]
downloaded = server.download("Federal_LCA_Commons", "IPCC_GWP", newest.commit)
print(newest.version, newest.released_at)
print(downloaded.path, downloaded.size, downloaded.sha256)
```

## openLCA Nexus

`NexusSession(account, password, token=None, base="https://nexus.openlca.org")` is a logged-in account, used as a context manager: entering it logs in once, and leaving it logs out. The `token` is the second factor when the account carries one. `NexusSession.from_environment()` takes the account from `NEXUS_USERNAME`, the password from `NEXUS_PASSWORD` and the second factor from `NEXUS_TOKEN`. A session prints as its server and its account, never its password or its token.

- `catalog()` answers every database the account may download, read from the server once per session: a list of `Database` with `name`, `type` and `packs`, each `Pack` with `uuid`, `name`, `licence_file` and `versions`, each `PackVersion` with `number`, `release_note` and `files`, each `PackFile` with `datafile_id` and `file_format`.
- `pack(uuid)` answers the catalog's pack with that uuid; a uuid the catalog lacks is a `NotInCatalog`.
- `licence(pack)` answers the `Path` of the pack's terms file in the cache, downloading it once; a pack that carries no terms is a `NotInCatalog`.
- `download(pack, version=..., file_format=..., accept_licence=False)` answers one file of a pack version at a format as a `Downloaded`; a pack that carries terms needs `accept_licence=True`.

```python
from lca_data_interface import NexusSession

with NexusSession.from_environment() as session:
    for database in session.catalog():
        print(database.name, database.type, len(database.packs))

    pack = session.pack("c068d31e-7268-4926-8720-b8f9b4648492")
    terms = session.licence(pack)
    got = session.download(pack, version=1, file_format="ecoSpold1", accept_licence=True)
    print(terms, got.path, got.size, got.sha256)
```

## The cache

`cache_dir()` answers the cache root: the directory `LCA_DATA_INTERFACE_CACHE` names, or the platform's user cache directory for this package, `~/.cache/lca-data-interface` on Linux. One directory under it holds each kind of download, the file under the name the server serves it with:

```text
commons/<host>/<group>/<name>/<commit>/<file>
nexus/<pack uuid>/licence/<file>
nexus/<pack uuid>/<version>/<format>/<file>
```

A body streams into a `.part` file there and is renamed once its bytes reach the length its answer announces, so a body that stops short is a `ShortDownload` and no file lands under the served name. `sha256.txt` beside it records the digest and the name of the bytes that landed, and a later call answers the cached file only while its bytes still hash to that digest; anything else is downloaded again.

## Errors

Every error derives from `LcaDataInterfaceError`, and each names in its message what a caller can act on.

| Error | Raised when |
| --- | --- |
| `CredentialsMissing(variables)` | `from_environment` finds `NEXUS_USERNAME` or `NEXUS_PASSWORD` unset |
| `LoginRefused(account, status)` | the login answers 401 or 403; the password is never named |
| `TokenRequired` | the login answer asks for a second factor, so `NEXUS_TOKEN` is needed |
| `NotInCatalog(uuid, wanted, available)` | the catalog holds no such pack, version, format or licence file |
| `LicenceNotAccepted(uuid, licence_file)` | a pack carrying terms is downloaded without `accept_licence=True` |
| `NotOnServer(repository, commit, detail)` | a Collaboration Server answers 404 for the repository or the commit |
| `MissingField(call, field)` | an answer lacks a field the client reads, including the served file name of a download |
| `ShortDownload(name, expected, received)` | a body ended before the length its answer announced |
| `ServiceError(call, status, detail)` | a status of 400 or more, an unreachable host, a body that is not JSON, or a served name the cache cannot hold |

## Tests

`uv run pytest` runs the suite against a loopback server and a temporary cache, with no network. The two checks in `tests/test_live.py` reach both services and run only with `LCA_DATA_INTERFACE_LIVE=1` and `-m live`.

## Licence

Apache-2.0. Copyright 2026 Carlos Gaete-Morales; see `LICENSE` and `NOTICE`.
