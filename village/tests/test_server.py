"""Integration checks for local HTTP boundaries, persistence and async scheduling."""
import copy
from http.server import ThreadingHTTPServer
import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from village.server import Handler, RequestError, VillageApp
from village.providers import ProviderError


class FakeGateway:
    metrics = {}

    def status(self):
        return {"jev": {"configured": True}, "luna": {"configured": True}}

    def decide(self, context, actions):
        return self.demo_decide(context, actions)

    def demo_decide(self, context, actions):
        action = next((a for a in actions if a["id"] in ("rest", "think", "reflect")), actions[0])
        return dict(action=action["id"], target_id=None, think=False, speak=False,
                    confidence=.8, probabilities={action["id"]: 1}, source="demo")


@pytest.fixture
def app(tmp_path):
    application = VillageApp(demo=True, restore=False, save_path=tmp_path / "state.json", gateway=FakeGateway())
    yield application
    application.close()


def test_controls_validate_before_mutation(app):
    before = app.snapshot()
    with pytest.raises(RequestError):
        app.control({"mode": "live", "speed": 7})
    assert app.mode == before["mode"]
    with pytest.raises(RequestError):
        app.control({"running": "false"})
    with pytest.raises(RequestError):
        app.control({"speed": True})
    assert app.running is False


def test_oracle_changes_context_and_world(app):
    before = app.snapshot()
    result = app.oracle({"text": "A Godzilla-like creature is approaching the village", "intensity": 80})
    assert len(result["contexts"]) > len(before["contexts"])
    assert result["world"]["dread"] > before["world"]["dread"]
    assert result["contexts"][-1 if len(result["contexts"]) == 1 else 0]["text"]
    assert result["oracle_busy"] is False
    with pytest.raises(RequestError):
        app.oracle({"text": "hello", "intensity": float("nan")})


def test_scenario_edit_and_end_preserve_history_and_save(app):
    created = app.oracle({"text": "A Godzilla-like creature approaches", "intensity": 80})
    old_id = created["contexts"][0]["id"]
    updated = app.oracle({"text": "A gentle rain settles over the village", "intensity": 25,
                          "duration_hours": 6}, context_id=old_id)
    new_id = updated["contexts"][0]["id"]
    assert old_id != new_id
    assert updated["scenario_history"][0]["status"] == "replaced"
    ended = app.dismiss_oracle(new_id, {"reason": "The skies clear."})
    assert ended["contexts"] == []
    assert ended["scenario_history"][0]["status"] == "dismissed"
    assert ended["scenario_history"][0]["reason"] == "The skies clear."
    saved = json.loads(app.save_path.read_text())["simulation"]
    assert saved["contexts"] == []
    assert saved["scenario_history"] == ended["scenario_history"]


def test_unknown_scenario_and_bad_edits_do_not_charge_or_mutate(app):
    app.mode = "live"
    with pytest.raises(RequestError, match="already ended"):
        app.oracle({"text": "Another approaching creature"}, context_id="missing")
    with pytest.raises(RequestError, match="already ended"):
        app.dismiss_oracle("missing", {})
    assert app.session_calls == 0
    app.mode = "demo"
    created = app.oracle({"text": "A creature approaches"})
    context_id = created["contexts"][0]["id"]
    with pytest.raises(RequestError):
        app.oracle({"text": "x"}, context_id=context_id)
    with pytest.raises(RequestError):
        app.dismiss_oracle(context_id, {"reason": 123})
    assert app.snapshot()["contexts"] == created["contexts"]


def test_withdrawn_scenario_cannot_publish_inflight_narrative(app):
    created = app.oracle({"text": "Godzilla is approaching"})
    context_id = created["contexts"][0]["id"]
    actor = app.sim.state["villagers"][0]
    vid = actor["id"]
    started, release = threading.Event(), threading.Event()

    def decide(context, actions):
        return {"action": "think", "think": True, "speak": False, "source": "demo"}

    def narrate(context, decision):
        started.set()
        release.wait(3)
        return {"thought": "Godzilla is still approaching right now.", "speech": "", "source": "demo"}

    app.gateway.demo_decide = decide
    app.gateway.demo_narrate = narrate
    future = app.pool.submit(app._decide, vid, app.sim.decision_context(vid),
                             app.sim.available_actions(vid), "demo", app.generation, None)
    try:
        assert started.wait(2)
        ended = app.dismiss_oracle(context_id, {})
        expected = next(v["thought"] for v in ended["villagers"] if v["id"] == vid)
    finally:
        release.set()
    future.result(timeout=3)
    assert actor["thought"] == expected
    assert actor["thought"] != "Godzilla is still approaching right now."


def test_dismiss_during_oracle_edit_discards_delayed_interpretation(app):
    created = app.oracle({"text": "Godzilla is approaching"})
    context_id = created["contexts"][0]["id"]
    started, release = threading.Event(), threading.Event()

    def interpret(text, intensity, duration_hours):
        started.set()
        release.wait(3)
        return app._demo_oracle(text, intensity, duration_hours)

    app.mode = "live"
    app.gateway.interpret_oracle = interpret
    future = app.pool.submit(app.oracle, {"text": "Godzilla is even closer"}, context_id)
    try:
        assert started.wait(2)
        app.dismiss_oracle(context_id, {})
    finally:
        release.set()
    with pytest.raises(RequestError, match="changed"):
        future.result(timeout=3)
    assert app.snapshot()["contexts"] == []
    assert not app.oracle_busy
    assert app.last_error is None


def test_expiry_invalidates_decisions_and_revisions_order_same_tick(app):
    created = app.oracle({"text": "A distant creature approaches", "duration_hours": 1})
    generation = app.generation
    app._tick(minutes=61)
    assert app.generation > generation
    assert app.snapshot()["contexts"] == []
    snapshot = app.snapshot()
    assert snapshot["revision"] > created["revision"]
    assert snapshot["server_instance"] == created["server_instance"]


@pytest.mark.parametrize("editing", [False, True])
def test_unrelated_expiry_does_not_discard_paid_oracle_interpretation(app, editing):
    created = app.oracle({"text": "A creature approaches", "duration_hours": 6})
    context_id = created["contexts"][0]["id"] if editing else None
    app.oracle({"text": "A brief festival begins", "duration_hours": 1})
    started, release = threading.Event(), threading.Event()

    def interpret(text, intensity, duration_hours):
        started.set()
        release.wait(3)
        return app._demo_oracle(text, intensity, duration_hours)

    app.mode = "live"
    app.gateway.interpret_oracle = interpret
    future = app.pool.submit(app.oracle, {"text": "A warm rain arrives"}, context_id)
    try:
        assert started.wait(2)
        app._tick(minutes=61)
    finally:
        release.set()
    result = future.result(timeout=3)
    assert result["contexts"][0]["text"] == "A warm rain arrives"
    assert len(result["contexts"]) == (1 if editing else 2)


def test_superseded_oracle_failure_does_not_poison_current_world(app):
    created = app.oracle({"text": "Godzilla is approaching"})
    context_id = created["contexts"][0]["id"]
    started, release = threading.Event(), threading.Event()

    def interpret(*args, **kwargs):
        started.set()
        release.wait(3)
        raise ProviderError("Luna: a stale request failed")

    app.mode = "live"
    app.gateway.interpret_oracle = interpret
    future = app.pool.submit(app.oracle, {"text": "Godzilla comes closer"}, context_id)
    try:
        assert started.wait(2)
        app.dismiss_oracle(context_id, {})
    finally:
        release.set()
    with pytest.raises(RequestError, match="changed"):
        future.result(timeout=3)
    assert app.last_error is None
    assert app.provider_failures["luna"] == 0


def test_save_and_restore_people_memories_and_clock(app):
    app.sim.tick(minutes=20)
    app.oracle({"text": "A magnificent harvest fills the granary.", "intensity": 70})
    app.save()
    restored = VillageApp(demo=True, save_path=app.save_path, gateway=FakeGateway())
    try:
        snapshot = restored.snapshot()
        assert snapshot["minute"] == app.snapshot()["minute"]
        assert snapshot["villagers"] == app.snapshot()["villagers"]
        assert snapshot["contexts"] == app.snapshot()["contexts"]
        assert restored.running is False
    finally:
        restored.close()


def test_reset_invalidates_model_response(app):
    started, release = threading.Event(), threading.Event()
    original = app.gateway.demo_decide
    def blocked(context, actions):
        started.set()
        release.wait(3)
        return original(context, actions)
    app.gateway.demo_decide = blocked
    app.control({"step": True})
    assert started.wait(2)
    app.reset({"seed": 123})
    release.set()
    time.sleep(.1)
    assert all(v.get("decision") is None for v in app.snapshot()["villagers"])


def test_rate_limits_do_not_rise_with_speed(app):
    app.jev_rpm = 2
    assert app._reserve_call()
    assert app._reserve_call()
    assert not app._reserve_call()
    app.control({"speed": 10})
    assert not app._reserve_call()
    app.luna_rpm = 1
    assert app._reserve_call(narrative=True)
    assert not app._reserve_call(narrative=True)


def test_autonomous_dialogue_leaves_capacity_for_scenario_changes(app):
    app.luna_rpm = 12
    for _ in range(10):
        assert app._reserve_call(narrative=True)
    assert not app._reserve_call(narrative=True)
    assert app._reserve_call(narrative=True, oracle=True)
    assert app._reserve_call(narrative=True, oracle=True)
    assert not app._reserve_call(narrative=True, oracle=True)


def test_superseded_job_does_not_call_provider(app):
    def unexpected(*args):
        raise AssertionError("A cancelled job must not call the model")
    app.gateway.demo_decide = unexpected
    app._decide("v01", {}, [], "demo", app.generation - 1, None)
    assert app.last_error is None


def test_repeated_luna_failure_pauses_even_when_jev_succeeds(app):
    app.running = True
    for _ in range(3):
        app.provider_failures["jev"] = 0
        app._model_error(ProviderError("Luna: rate or spending limit reached"))
    assert not app.running
    assert "Luna" in app.last_error


def test_http_serves_state_and_rejects_foreign_mutation(app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.app = app
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/api/state") as response:
            state = json.load(response)
            assert len(state["villagers"]) == 20
            assert "API_KEY" not in json.dumps(state)
        request = Request(base + "/api/control", data=b'{"running":true}', headers={"Content-Type": "application/json", "Origin": "https://example.org"})
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 403
        assert not app.running
        request = Request(base + "/api/control", data=b'{"running":true}', headers={"Content-Type": "application/json", "Origin": base})
        with urlopen(request) as response:
            assert json.load(response)["running"] is True
        with urlopen(base + "/api/export") as response:
            assert "attachment" in response.headers["Content-Disposition"]
        def post(path, payload):
            request = Request(base + path, data=json.dumps(payload).encode(),
                              headers={"Content-Type": "application/json", "Origin": base})
            with urlopen(request) as response:
                return json.load(response)
        created = post("/api/oracle", {"text": "A creature approaches the river"})
        updated = post(f"/api/oracle/{created['contexts'][0]['id']}/update",
                       {"text": "A village celebration begins"})
        ended = post(f"/api/oracle/{updated['contexts'][0]['id']}/dismiss", {})
        assert not ended["contexts"]
        assert len(ended["scenario_history"]) == 2
    finally:
        server.shutdown()
        server.server_close()
