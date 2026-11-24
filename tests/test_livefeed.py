from hub_service_public import livefeed, net, services


def test_snapshot_partial_failures(monkeypatch):
    def fake_get_json(url, params=None, **kw):
        if "datasets" in url and params.get("page_size") == 8:
            raise net.HttpError(503, "indisponible", url)
        if "reuses" in url:
            raise net.HttpError(500, "boom", url)
        if params.get("page_size") == 1:
            return {"total": 42}
        return {"data": []}
    monkeypatch.setattr(net, "get_json", fake_get_json)
    monkeypatch.setattr(services, "check_all", lambda: [{"id": "x", "ok": True}])
    snap = livefeed.snapshot(force=True)
    assert snap["totals"]["datasets"] == 42 and snap["totals"]["reuses"] is None
    assert "reuses" in snap["errors"] and "latest" in snap["errors"]
    assert snap["services"] == [{"id": "x", "ok": True}]


def test_snapshot_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(net, "get_json", lambda *a, **k: calls.append(1) or {"total": 1, "data": []})
    monkeypatch.setattr(services, "check_all", lambda: [])
    livefeed.snapshot(force=True)
    n = len(calls)
    livefeed.snapshot()
    assert len(calls) == n
