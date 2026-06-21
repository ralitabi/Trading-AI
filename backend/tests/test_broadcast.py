from engine import broadcast, chartimg


def _analysis():
    return {
        "trend_strength": "strong", "adx": 26.1, "volatility": "low",
        "votes": {"up": 10, "down": 2, "neutral": 2},
        "support": 99.0, "resistance": 110.0, "price": 100.0,
    }


def test_build_message_long_has_core_fields():
    scored = {"bias": "up", "confidence": 81}
    plan = {"direction": "long", "entry": 100.0, "stop": 97.0, "target": 105.0, "rr": 1.67}
    msg = broadcast.build_message("Bitcoin", "1h", scored, _analysis(), plan,
                                  None, None, None, 1_700_000_000, 3600)
    assert "LONG" in msg and "UP" in msg
    assert "81%" in msg
    assert "WHICH" in msg and "WHEN" in msg
    assert "Entry" in msg and "Stop" in msg and "Target" in msg
    assert "UTC" in msg


def test_build_message_short_with_horizon_and_window():
    scored = {"bias": "down", "confidence": 78}
    plan = {"direction": "short", "entry": 100.0, "stop": 103.0, "target": 95.0, "rr": 1.67}
    tcast = {"horizons": [{"label": "6h", "direction": "down", "target": 94.0,
                           "confidence": 60, "move_pct": -6, "bars": 6}]}
    bw = {"start_utc": 13, "end_utc": 17, "intensity": 1.4}
    msg = broadcast.build_message("Gold", "1h", scored, _analysis(), plan,
                                  None, tcast, bw, 1_700_000_000, 3600)
    assert "SHORT" in msg and "DOWN" in msg
    assert "best hours 13:00" in msg
    assert "6h" in msg and "HOW LONG" in msg


def test_chart_render_returns_png(make_candles):
    png = chartimg.render(
        make_candles(120),
        {"entry": 100.0, "stop": 97.0, "target": 105.0, "rr": 1.7},
        None, "BTC 1h UP", "confidence 80%",
    )
    assert isinstance(png, bytes) and len(png) > 1000
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic number
