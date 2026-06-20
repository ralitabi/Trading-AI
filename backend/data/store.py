"""Prediction history — every fresh prediction is logged to the database.

This is the accountability layer: without a record of what the system said
and when, "accuracy" is unmeasurable. Scoring grades these rows against what
the market actually did next.

The backend is SQLite locally and a durable Turso/libSQL database in production
(see data/db.py) — same schema, same SQL, swapped underneath.
"""
import sqlite3
import time
from threading import Lock

from data import db

_lock = Lock()
_schema_lock = Lock()
_schema_ready = False


def _create_schema(conn) -> None:
    """Idempotent — safe to call on every connect (cheap for SQLite)."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            tf TEXT NOT NULL,
            price REAL NOT NULL,
            tech_bias TEXT NOT NULL,
            tech_confidence INTEGER NOT NULL,
            ai_direction TEXT NOT NULL,
            ai_confidence INTEGER NOT NULL,
            volatility TEXT NOT NULL
        )"""
    )
    # outcome columns, added after the fact — migrate older DBs in place
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(predictions)")}
    for col, typ in (
        ("actual_price", "REAL"),
        ("actual_direction", "TEXT"),
        ("tech_correct", "INTEGER"),
        ("ai_correct", "INTEGER"),
        ("evaluated_at", "INTEGER"),
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE predictions ADD COLUMN {col} {typ}")
    # projected next-candle history — one row per target candle (latest wins)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS forecasts (
            symbol TEXT NOT NULL,
            tf TEXT NOT NULL,
            target_time INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            direction TEXT, made_at INTEGER,
            PRIMARY KEY (symbol, tf, target_time)
        )"""
    )
    # paper-trading book — hypothetical trades auto-opened from directional
    # signals and closed when price hits the ATR stop or target.
    conn.execute(
        """CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            tf TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry REAL NOT NULL,
            stop REAL NOT NULL,
            target REAL NOT NULL,
            rr REAL NOT NULL,
            opened_ts INTEGER NOT NULL,
            status TEXT NOT NULL,
            exit_price REAL,
            exit_ts INTEGER,
            result TEXT,
            r_multiple REAL
        )"""
    )
    conn.commit()


def _conn():
    conn = db.connect()
    if isinstance(conn, sqlite3.Connection):
        _create_schema(conn)  # cheap & idempotent for the local file backend
    else:
        # Remote (libSQL): every CREATE/PRAGMA is an HTTP round-trip, so run the
        # schema exactly once per process instead of on every connect.
        global _schema_ready
        if not _schema_ready:
            with _schema_lock:
                if not _schema_ready:
                    _create_schema(conn)
                    _schema_ready = True
    return conn


def has_open_trade(symbol: str, tf: str) -> bool:
    with _lock:
        conn = _conn()
        try:
            r = conn.execute(
                "SELECT 1 FROM paper_trades WHERE symbol=? AND tf=? AND status='open' LIMIT 1",
                (symbol, tf)).fetchone()
            return r is not None
        finally:
            conn.close()


def open_paper_trade(symbol: str, tf: str, direction: str, entry: float,
                     stop: float, target: float, rr: float) -> None:
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                "INSERT INTO paper_trades (symbol, tf, direction, entry, stop, target, rr,"
                " opened_ts, status) VALUES (?,?,?,?,?,?,?,?,'open')",
                (symbol, tf, direction, entry, stop, target, rr, int(time.time())),
            )
            conn.commit()
        finally:
            conn.close()


def open_trades() -> list[dict]:
    with _lock:
        conn = _conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM paper_trades WHERE status='open'").fetchall()]
        finally:
            conn.close()


def close_paper_trade(trade_id: int, exit_price: float, result: str, r_multiple: float) -> None:
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                "UPDATE paper_trades SET status='closed', exit_price=?, exit_ts=?, result=?,"
                " r_multiple=? WHERE id=?",
                (exit_price, int(time.time()), result, r_multiple, trade_id),
            )
            conn.commit()
        finally:
            conn.close()


def paper_portfolio(symbol: str | None = None, tf: str | None = None) -> dict:
    cond, args = "", []
    if symbol:
        cond += " AND symbol=?"
        args.append(symbol)
    if tf:
        cond += " AND tf=?"
        args.append(tf)
    with _lock:
        conn = _conn()
        try:
            closed = [dict(r) for r in conn.execute(
                f"SELECT * FROM paper_trades WHERE status='closed'{cond}"
                f" ORDER BY exit_ts DESC", args).fetchall()]
            opens = [dict(r) for r in conn.execute(
                f"SELECT * FROM paper_trades WHERE status='open'{cond}"
                f" ORDER BY opened_ts DESC", args).fetchall()]
            wins = sum(1 for t in closed if t["result"] == "win")
            net_r = round(sum(t["r_multiple"] or 0 for t in closed), 2)
            n = len(closed)
            return {
                "closed_count": n,
                "open_count": len(opens),
                "wins": wins,
                "losses": n - wins,
                "win_rate": round(wins / n * 100, 1) if n else None,
                "net_r": net_r,
                "open": opens[:8],
                "recent": closed[:12],
            }
        finally:
            conn.close()


def log_forecast(symbol: str, tf: str, fc: dict) -> None:
    """Upsert the projected next candle, keyed by its target time."""
    if not fc:
        return
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO forecasts"
                " (symbol, tf, target_time, open, high, low, close, direction, made_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (symbol, tf, int(fc["time"]), fc["open"], fc["high"], fc["low"],
                 fc["close"], fc["direction"], int(time.time())),
            )
            conn.commit()
        finally:
            conn.close()


def forecast_history(symbol: str, tf: str, limit: int = 300) -> list[dict]:
    with _lock:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT target_time, open, high, low, close, direction FROM forecasts"
                " WHERE symbol = ? AND tf = ? ORDER BY target_time DESC LIMIT ?",
                (symbol, tf, limit),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()


def log_prediction(symbol: str, tf: str, price: float, technical: dict, ai_view: dict) -> None:
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                "INSERT INTO predictions (ts, symbol, tf, price, tech_bias, tech_confidence,"
                " ai_direction, ai_confidence, volatility) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    int(time.time()), symbol, tf, price,
                    technical["bias"], technical["confidence"],
                    ai_view.get("direction", "neutral"), int(ai_view.get("confidence", 0)),
                    technical.get("volatility", "moderate"),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def unevaluated() -> list[dict]:
    with _lock:
        conn = _conn()
        try:
            rows = conn.execute("SELECT * FROM predictions WHERE evaluated_at IS NULL").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def mark_evaluated(pred_id: int, actual_price: float | None, actual_direction: str,
                   tech_correct: int | None, ai_correct: int | None) -> None:
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                "UPDATE predictions SET actual_price=?, actual_direction=?, tech_correct=?,"
                " ai_correct=?, evaluated_at=? WHERE id=?",
                (actual_price, actual_direction, tech_correct, ai_correct, int(time.time()), pred_id),
            )
            conn.commit()
        finally:
            conn.close()


def report(symbol: str | None = None, tf: str | None = None) -> dict:
    """Aggregate accuracy stats — the honest scoreboard. Optionally filtered."""
    cond, args = "", []
    if symbol:
        cond += " AND symbol = ?"
        args.append(symbol)
    if tf:
        cond += " AND tf = ?"
        args.append(tf)
    with _lock:
        conn = _conn()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) c FROM predictions WHERE 1=1{cond}", args).fetchone()["c"]
            pending = conn.execute(
                f"SELECT COUNT(*) c FROM predictions WHERE evaluated_at IS NULL{cond}", args).fetchone()["c"]
            unknown = conn.execute(
                f"SELECT COUNT(*) c FROM predictions WHERE actual_direction = 'unknown'{cond}", args).fetchone()["c"]
            no_call = conn.execute(
                f"SELECT COUNT(*) c FROM predictions WHERE evaluated_at IS NOT NULL"
                f" AND tech_bias = 'neutral'{cond}", args).fetchone()["c"]

            def acc(col: str) -> dict:
                r = conn.execute(
                    f"SELECT COUNT({col}) n, COALESCE(SUM({col}),0) hits FROM predictions"
                    f" WHERE {col} IS NOT NULL{cond}", args).fetchone()
                n, hits = r["n"], r["hits"]
                return {"calls": n, "hits": hits,
                        "accuracy": round(hits / n * 100, 1) if n else None}

            by_market = []
            for r in conn.execute(
                f"SELECT symbol, tf, COUNT(tech_correct) tech_n, COALESCE(SUM(tech_correct),0) tech_hits,"
                f" COUNT(ai_correct) ai_n, COALESCE(SUM(ai_correct),0) ai_hits"
                f" FROM predictions WHERE evaluated_at IS NOT NULL{cond}"
                f" GROUP BY symbol, tf HAVING tech_n > 0 OR ai_n > 0 ORDER BY symbol, tf", args
            ).fetchall():
                by_market.append({
                    "symbol": r["symbol"], "tf": r["tf"],
                    "tech_calls": r["tech_n"], "tech_hits": r["tech_hits"],
                    "tech_accuracy": round(r["tech_hits"] / r["tech_n"] * 100, 1) if r["tech_n"] else None,
                    "ai_calls": r["ai_n"], "ai_hits": r["ai_hits"],
                    "ai_accuracy": round(r["ai_hits"] / r["ai_n"] * 100, 1) if r["ai_n"] else None,
                })

            recent = [dict(r) for r in conn.execute(
                f"SELECT * FROM predictions WHERE evaluated_at IS NOT NULL{cond}"
                f" ORDER BY ts DESC LIMIT 40", args).fetchall()]

            return {
                "totals": {"logged": total, "pending": pending,
                            "evaluated": total - pending, "unknown": unknown, "no_call": no_call},
                "technical": acc("tech_correct"),
                "ai": acc("ai_correct"),
                "by_market": by_market,
                "recent": recent,
            }
        finally:
            conn.close()


def history(symbol: str, tf: str | None = None, limit: int = 100) -> list[dict]:
    with _lock:
        conn = _conn()
        try:
            q = "SELECT * FROM predictions WHERE symbol = ?"
            args: list = [symbol]
            if tf:
                q += " AND tf = ?"
                args.append(tf)
            q += " ORDER BY ts DESC LIMIT ?"
            args.append(limit)
            rows = conn.execute(q, args).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
