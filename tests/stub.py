"""A loopback HTTP server answering registered routes, so no test reaches the network."""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


@dataclass(frozen=True)
class Recorded:
    """One request the stub served."""

    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Answer:
    """The status, body and headers the stub holds for one route."""

    status: int
    body: bytes
    headers: dict[str, str]


class StubServer:
    """Answers registered routes on 127.0.0.1 and records every request it serves."""

    def __init__(self) -> None:
        self.requests: list[Recorded] = []
        self._answers: dict[tuple[str, str], Answer] = {}
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(self))
        self._server.daemon_threads = True
        self.base = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def route(
        self,
        method: str,
        path: str,
        status: int,
        body: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Answer `method` on `path`, with its query, with `status`, `body` and `headers`."""
        self._answers[(method, path)] = Answer(status, body, headers or {})

    def close(self) -> None:
        """Stop serving and release the port."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    def serve(self, method: str, path: str, headers: dict[str, str], body: bytes) -> Answer:
        """Record the request and answer it, with 404 for a route nobody registered."""
        self.requests.append(Recorded(method, path, headers, body))
        return self._answers.get((method, path), Answer(404, f"no route for {path}".encode(), {}))


def _handler(stub: StubServer) -> type[BaseHTTPRequestHandler]:
    """A request handler that answers every verb the package sends from `stub`."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.answer()

        def do_POST(self) -> None:
            self.answer()

        def answer(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            answer = stub.serve(self.command, self.path, dict(self.headers.items()), body)
            self.send_response(answer.status)
            for name, value in answer.headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(answer.body)

        def log_message(self, _format: str, *_args: object) -> None:
            """Silence the base handler's per-request logging."""

    return Handler
