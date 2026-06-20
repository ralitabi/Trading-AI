"""Database backend — local SQLite by default, durable Turso/libSQL when configured.

On serverless (Vercel sets VERCEL=1) the SQLite file lives in /tmp, which is
wiped on every cold start — so the accuracy report and the paper-trading track
record reset constantly. That self-scoring record is the product's whole point,
so it needs to survive.

Set both of these env vars to a free Turso / libSQL database and the exact same
schema + SQL persist durably across cold starts:

    TURSO_DATABASE_URL=libsql://your-db-name.turso.io
    TURSO_AUTH_TOKEN=...

(LIBSQL_URL / LIBSQL_AUTH_TOKEN are accepted as aliases.) Without those vars —
or if the libsql client can't be imported/reached — it transparently falls back
to a local SQLite file, so local dev and CI need nothing.

libSQL speaks the SQLite dialect, so store.py's queries are unchanged; this
module only swaps the connection underneath. The remote adapter exposes the
exact slice of the sqlite3 connection API that store.py uses
(``execute``/``commit``/``close`` + dict rows), so callers can't tell them apart.
"""
import os
import sqlite3
import tempfile
from threading import Lock

_REMOTE_URL = os.environ.get("TURSO_DATABASE_URL") or os.environ.get("LIBSQL_URL")
_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("LIBSQL_AUTH_TOKEN")


def is_remote() -> bool:
    """True when a durable libSQL endpoint is configured (URL is enough; a token
    is only needed for hosted Turso, not for a local sqld)."""
    return bool(_REMOTE_URL)


def _local_path() -> str:
    if os.environ.get("PREDICTIONS_DB"):
        return os.environ["PREDICTIONS_DB"]
    if os.environ.get("VERCEL"):
        return os.path.join(tempfile.gettempdir(), "predictions.db")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "predictions.db")


def _dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


# --- Remote (libSQL/Turso) adapter -----------------------------------------
# A thin shim presenting just the parts of the sqlite3 connection API store.py
# relies on. Hrana-over-HTTP autocommits each statement, so commit() is a no-op
# and the shared client is kept alive across calls (close() is a no-op too).
class _RemoteCursor:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class _RemoteConn:
    row_factory = None  # accepted then ignored — rows are always dicts

    def __init__(self, client):
        self._client = client

    def execute(self, sql: str, params=()) -> _RemoteCursor:
        rs = self._client.execute(sql, list(params))
        cols = rs.columns
        return _RemoteCursor([dict(zip(cols, row)) for row in rs.rows])

    def commit(self):
        pass

    def close(self):
        pass


_remote_client = None
_remote_lock = Lock()


def _get_remote() -> _RemoteConn:
    global _remote_client
    if _remote_client is None:
        with _remote_lock:
            if _remote_client is None:
                import libsql_client

                _remote_client = libsql_client.create_client_sync(
                    url=_REMOTE_URL, auth_token=_AUTH_TOKEN
                )
    return _RemoteConn(_remote_client)


def connect():
    """Return a connection exposing the slice of the sqlite3 API store.py needs.

    Durable Turso/libSQL when configured AND reachable; otherwise a local SQLite
    file. The fallback means a misconfigured or unreachable remote never takes
    the app down — it just loses durability until fixed.
    """
    if is_remote():
        try:
            return _get_remote()
        except Exception:
            pass  # libsql_client missing / unreachable → local file fallback
    # timeout: wait up to 5s for a lock instead of instantly raising
    # "database is locked" when concurrent writes collide.
    conn = sqlite3.connect(_local_path(), timeout=5)
    conn.row_factory = _dict_factory
    return conn
