# lca-data-interface

List and download LCA databases from openLCA Nexus and LCA Collaboration
Servers into a hash-checked cache.

```bash
pip install lca-data-interface
```

## LCA Collaboration Server

`CommonsServer` reads a server's public history and downloads a released commit.
It needs no account; its default server is the Federal LCA Commons.

```python
from lca_data_interface import CommonsServer

server = CommonsServer()
releases = server.releases("Federal_LCA_Commons", "IPCC_GWP")
newest = releases[0]
downloaded = server.download("Federal_LCA_Commons", "IPCC_GWP", newest.commit)
print(newest.version, downloaded.path, downloaded.size, downloaded.sha256)
```

## openLCA Nexus

`NexusSession` logs in with an openLCA Nexus account, reads its catalog and
downloads a pack's files, once the pack's licence is accepted.

```python
from lca_data_interface import NexusSession

session = NexusSession.from_environment()
for database in session.catalog():
    print(database)
```

`from_environment` reads the account from `NEXUS_USERNAME` and
`NEXUS_PASSWORD`, and `NEXUS_TOKEN` for an account with a second factor;
`NexusSession(account, password, token=...)` takes them directly. A session
never shows its password or its token.

## The cache

Each download lands in the cache once, with its size and its SHA-256, and is
served from there afterwards. The cache is the directory
`LCA_DATA_INTERFACE_CACHE` names, or the user cache directory of the platform.

## Licence

Apache-2.0. Copyright 2026 Kimel Tech SpA; see `LICENSE` and `NOTICE`.
