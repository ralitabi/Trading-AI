from engine import broadcast, chartimg


def _analysis():
    return {
        "trend_strength": "strong", "adx": 26.1, "volatility": "low",
        "votes": {"up": 10, "down": 2, "neutral": 2},
        "support": 99.0, "resistance": 110.0, "price": 100.0,
    }


def test_build_message_long_is_plain_and_complete():
    scored = {"bias": "up", "confidence": 81}
    plan = {"direction": "long", "entry": 100.0, "stop": 97.0, "target": 105.0, "rr": 1.67}
    fc = {"open": 100.0, "close": 100.4, "body_pct": 0.4}
    msg = broadcast.build_message("Bitcoin", "1h", scored, _analysis(), plan,
                                  fc, None, None, None, 1_700_000_000, 3600)
    assert "BUY" in msg and "going UP" in msg
    assert "81%" in msg
    assert "BUY now" in msg and "Stop loss" in msg and "Take profit" in msg
    assert "Next candle" in msg
    assert "ENTER NOW" in msg
    # multi-country clocks in AM/PM
    assert "USA" in msg and "Pakistan" in msg and "India" in msg
    assert "AM" in msg or "PM" in msg


def test_build_message_short_with_horizon_avgline_window():
    scored = {"bias": "down", "confidence": 84}
    plan = {"direction": "short", "entry": 100.0, "stop": 103.0, "target": 95.0, "rr": 1.67}
    tcast = {"horizons": [{"label": "6h", "direction": "down", "target": 94.0,
                           "confidence": 60, "move_pct": -6, "bars": 6}]}
    bw = {"start_utc": 13, "end_utc": 17, "intensity": 1.4}
    avg_proj = {"direction": "falling", "to": 96.5}
    msg = broadcast.build_message("Gold", "1h", scored, _analysis(), plan,
                                  None, tcast, bw, avg_proj, 1_700_000_000, 3600)
    assert "SELL" in msg and "going DOWN" in msg
    assert "Best hours to trade: 13:00" in msg
    assert "Average line: falling" in msg
    assert "6h" in msg


def test_avg_projection_direction():
    pts = [{"seg": "trend", "value": 100.0}, {"seg": "trend", "value": 100.5},
           {"seg": "proj", "value": 101.0}, {"seg": "proj", "value": 101.6}]
    proj = broadcast._avg_projection(pts)
    assert proj and proj["direction"] == "rising" and proj["to"] >= 101.0


def test_chart_render_returns_png(make_candles):
    png = chartimg.render(
        make_candles(120),
        {"entry": 100.0, "stop": 97.0, "target": 105.0, "rr": 1.7},
        None, "BTC 1h UP", "confidence 80%",
    )
    assert isinstance(png, bytes) and len(png) > 1000
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic number
