"""Local-only HTTP host and asynchronous model scheduler for Hearth.

Run from the repository root: .venv/bin/python -m village.server
"""
from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
import os
from pathlib import Path
import signal
import threading
import time
import uuid
from urllib.parse import urlparse

from .engine import Simulation
from .providers import ModelGateway

ROOT = Path(__file__).resolve().parent


class RequestError(ValueError):
    pass


class VillageApp:
    def __init__(self, *, seed=42, demo=False, restore=True, save_path=None, gateway=None):
        self.lock = threading.RLock()
        self.gateway = gateway or ModelGateway()
        self.save_path = Path(save_path or ROOT / "data" / "village.json")
        self.sim = Simulation(seed=seed)
        self.notice = "Select a villager, then press play to bring the village to life."
        if restore and self.save_path.exists():
            try:
                saved = json.loads(self.save_path.read_text())
                self.sim = Simulation.from_state(saved.get("simulation", saved))
                self.notice = "Your saved village has been restored."
            except (ValueError, KeyError, TypeError, AttributeError):
                self.notice = "The saved village could not be restored; a fresh village is ready."
        self.running = False
        self.speed = 1
        self.mode = "demo" if demo or not self.live_ready() else "live"
        self.generation = 0
        self.oracle_epoch = 0
        self.server_instance = uuid.uuid4().hex
        self.revision = 0
        self.inflight = set()
        self.failures = 0
        self.provider_failures = {"jev": 0, "luna": 0, "other": 0}
        self.next_actor = 0
        self.oracle_busy = False
        self.last_error = None
        self.last_save = None
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hearth-model")
        self.stop_event = threading.Event()
        self.calls = deque()
        self.narrative_calls = deque()
        self.session_calls = 0
        self.jev_rpm = self._env_int("VILLAGE_JEV_RPM", 60, 1, 600)
        self.luna_rpm = self._env_int("VILLAGE_LUNA_RPM", 12, 1, 120)
        self.call_limit = self._env_int("VILLAGE_SESSION_CALL_LIMIT", 3000, 1, 100000)
        self.scheduler = threading.Thread(target=self._loop, name="hearth-clock", daemon=True)

    @staticmethod
    def _env_int(key, default, low, high):
        try:
            return max(low, min(high, int(os.getenv(key, default))))
        except ValueError:
            return default

    def live_ready(self):
        status = self.gateway.status()
        return bool(status.get("jev", {}).get("configured") and status.get("luna", {}).get("configured"))

    def snapshot(self):
        with self.lock:
            self.revision += 1
            state = self.sim.snapshot()
            state.update(running=self.running, speed=self.speed, mode=self.mode,
                         revision=self.revision, server_instance=self.server_instance,
                         providers=self.gateway.status(), notice=self.notice,
                         last_error=self.last_error, oracle_busy=self.oracle_busy,
                         last_save=self.last_save)
            state["metrics"] = copy.deepcopy(self.gateway.metrics)
            state["metrics"].update(inflight=len(self.inflight), session_calls=self.session_calls,
                                    session_call_limit=self.call_limit, jev_rpm_limit=self.jev_rpm,
                                    luna_rpm_limit=self.luna_rpm)
            return state

    def start(self):
        self.scheduler.start()

    def close(self):
        self.stop_event.set()
        if self.scheduler.is_alive():
            self.scheduler.join(timeout=2)
        with self.lock:
            self.running = False
            self.generation += 1
            self.oracle_epoch += 1
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.save()
        if hasattr(self.gateway, "close"):
            self.gateway.close()

    def save(self):
        with self.lock:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"format": "hearth-v1", "simulation": self.sim.snapshot()}
            temporary = self.save_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False))
            temporary.replace(self.save_path)
            self.last_save = time.time()

    def control(self, body):
        with self.lock:
            if "mode" in body:
                if body["mode"] not in ("demo", "live"):
                    raise RequestError("Choose demo or live mode.")
                if body["mode"] == "live" and not self.live_ready():
                    raise RequestError("Live mode needs Cloudflare and OpenAI credentials in the project .env.")
            if "speed" in body and (type(body["speed"]) is not int or body["speed"] not in (1, 2, 5, 10)):
                raise RequestError("Speed must be 1, 2, 5, or 10.")
            for key in ("running", "step"):
                if key in body and type(body[key]) is not bool:
                    raise RequestError(f"{key} must be true or false.")
            if body.get("mode", self.mode) != self.mode:
                self.mode = body["mode"]
                self.generation += 1
                self.oracle_epoch += 1
                self.inflight.clear()
                self.failures = 0
                self.provider_failures = {"jev": 0, "luna": 0, "other": 0}
                self.last_error = None
                self.notice = "Live model decisions enabled." if self.mode == "live" else "Demo mode uses local rules and scripted dialogue."
            if "speed" in body:
                self.speed = body["speed"]
            if "running" in body:
                self.running = body["running"]
                if not self.running:
                    self.generation += 1
                    self.inflight.clear()
                else:
                    self.last_error = None
            if body.get("step"):
                self._tick(minutes=5)
                self._schedule_decision(force=True)
        return self.snapshot()

    def reset(self, body):
        seed = body.get("seed", 42)
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise RequestError("Seed must be an integer from 0 to 4294967295.")
        with self.lock:
            self.generation += 1
            self.oracle_epoch += 1
            self.inflight.clear()
            self.sim = Simulation(seed=seed)
            self.running = False
            self.next_actor = 0
            self.last_error = None
            self.failures = 0
            self.provider_failures = {"jev": 0, "luna": 0, "other": 0}
            self.notice = "A new morning in Hearth."
        self.save()
        return self.snapshot()

    def _active_context(self, context_id):
        if not any(c["id"] == context_id for c in self.sim.state["contexts"]):
            raise RequestError("That scenario has already ended or no longer exists.")

    def _invalidate_decisions(self):
        # Requests already on the wire may finish, but cannot publish an old world view.
        self.generation += 1
        self.inflight.clear()

    def _oracle_request_current(self, epoch, context_id):
        target_exists = context_id is None or any(c["id"] == context_id for c in self.sim.state["contexts"])
        if epoch != self.oracle_epoch or not target_exists:
            raise RequestError("The village or scenario changed while the oracle was working. Submit the event again.")

    def _tick(self, minutes):
        active_before = {c["id"] for c in self.sim.state["contexts"]}
        self.sim.tick(minutes=minutes)
        if active_before != {c["id"] for c in self.sim.state["contexts"]}:
            self._invalidate_decisions()

    def dismiss_oracle(self, context_id, body):
        reason = body.get("reason", "")
        if not isinstance(reason, str) or len(reason.strip()) > 500:
            raise RequestError("The reason must be text of at most 500 characters.")
        with self.lock:
            self._active_context(context_id)
            self.sim.dismiss_context(context_id, reason.strip())
            self._invalidate_decisions()
            self.notice = "Scenario ended. The village knows its influence has passed."
            self.save()
        return self.snapshot()

    def oracle(self, body, context_id=None):
        text = body.get("text")
        if not isinstance(text, str) or not 3 <= len(text.strip()) <= 1200:
            raise RequestError("Describe an event using 3–1200 characters.")
        intensity = self._number(body.get("intensity", 60), 0, 100, "Intensity")
        duration = self._number(body.get("duration_hours", 24), 1, 168, "Duration")
        with self.lock:
            if context_id is not None:
                self._active_context(context_id)
            if self.oracle_busy:
                raise RequestError("The oracle is still shaping the previous event.")
            mode, epoch = self.mode, self.oracle_epoch
            if mode == "live" and not self._reserve_call(narrative=True, oracle=True):
                raise RequestError("Luna call limit reached. Wait a minute or use demo mode.")
            self.oracle_busy = True
        try:
            if mode == "live":
                event = self.gateway.interpret_oracle(text.strip(), intensity=intensity, duration_hours=duration)
            else:
                event = self._demo_oracle(text.strip(), intensity, duration)
            with self.lock:
                self._oracle_request_current(epoch, context_id)
                if context_id is None:
                    self.sim.apply_oracle(event)
                else:
                    self._active_context(context_id)
                    self.sim.replace_context(context_id, event)
                self._invalidate_decisions()
                self.provider_failures["luna"] = 0
                self.notice = "Scenario updated. The village feels the change." if context_id else "The village feels your intervention."
                self.last_error = None
                self.save()
        except RequestError:
            raise
        except Exception as exc:
            with self.lock:
                self._oracle_request_current(epoch, context_id)
                self._model_error(exc)
                raise RequestError(self.last_error) from None
        finally:
            with self.lock:
                self.oracle_busy = False
        return self.snapshot()

    @staticmethod
    def _number(value, low, high, label):
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise RequestError(f"{label} must be between {low} and {high}.")
        return value

    @staticmethod
    def _demo_oracle(text, intensity, duration):
        lower = text.lower()
        kind, effects = "atmosphere", {"dread": intensity * .25}
        if any(word in lower for word in ("godzilla", "creature", "monster", "invasion", "attack")):
            kind, effects = "threat", {"dread": intensity * .7, "tension": intensity * .3}
        elif any(word in lower for word in ("doom", "taking over", "ai ", "unease")):
            effects = {"dread": intensity * .6, "tension": intensity * .2}
        elif any(word in lower for word in ("famine", "drought", "scarcity", "shortage")):
            kind, effects = "scarcity", {"food": -intensity * 2, "tension": intensity * .3}
        elif any(word in lower for word in ("harvest", "abundance", "rich", "plentiful")):
            kind, effects = "abundance", {"food": intensity * 3, "prosperity": intensity * .25, "dread": -intensity * .3}
        elif any(word in lower for word in ("festival", "celebrate", "celebration", "feast")):
            kind, effects = "celebration", {"tension": -intensity * .5, "dread": -intensity * .4}
        elif any(word in lower for word in ("rain", "storm", "snow", "sunny")):
            kind, effects = "weather", {"weather": "storm" if "storm" in lower else "rain" if "rain" in lower else "snow" if "snow" in lower else "sunny"}
        elif any(word in lower for word in ("tax", "mayor", "revolt", "election")):
            kind, effects = "politics", {"tension": intensity * .6}
        return dict(text=text, kind=kind, effects=effects if intensity else {}, intensity=intensity, duration_hours=duration, source="demo")

    def nudge(self, villager_id, body):
        action = body.get("action")
        if action not in ("think", "talk", "go_home"):
            raise RequestError("Choose think, talk, or go_home.")
        with self.lock:
            if not any(v["id"] == villager_id for v in self.sim.state["villagers"]):
                raise RequestError("That villager does not exist.")
            if villager_id in self.inflight:
                raise RequestError("That villager is already making a decision.")
            self._schedule_decision(force=True, villager_id=villager_id, nudge=action)
        return self.snapshot()

    def _reserve_call(self, narrative=False, oracle=False):
        now = time.monotonic()
        queue = self.narrative_calls if narrative else self.calls
        while queue and now - queue[0] >= 60:
            queue.popleft()
        limit = self.luna_rpm if narrative else self.jev_rpm
        if narrative and not oracle:
            # Keep room for the observer while autonomous dialogue is busy.
            limit = max(1, limit - 2)
        if len(queue) >= limit:
            return False
        if self.session_calls >= self.call_limit:
            self.running = False
            self.notice = "Session model-call limit reached. Restart the server to begin a new session or switch to demo."
            return False
        queue.append(now)
        self.session_calls += 1
        return True

    def _schedule_decision(self, force=False, villager_id=None, nudge=None):
        # Caller owns lock. No network work occurs here.
        if len(self.inflight) >= 4:
            if nudge:
                raise RequestError("Four villagers are deciding right now. Try again in a moment.")
            return
        people = self.sim.state["villagers"]
        actor = None
        if villager_id:
            actor = next(v for v in people if v["id"] == villager_id)
        else:
            for _ in people:
                candidate = people[self.next_actor % len(people)]
                self.next_actor += 1
                if candidate["id"] not in self.inflight and not candidate.get("pending_action") and not candidate.get("destination"):
                    actor = candidate
                    break
        if actor is None:
            return
        context = self.sim.decision_context(actor["id"])
        actions = self.sim.available_actions(actor["id"])
        if not actions:
            return
        if nudge:
            allowed = {"think": ("think", "reflect"), "talk": ("talk", "chat", "greet"), "go_home": ("go_home", "rest", "sleep")}[nudge]
            choices = [a for a in actions if a["id"] in allowed]
            if not choices:
                raise RequestError("That action is not available for this villager right now.")
            actions = choices
            context["oracle_nudge"] = f"The observer invites you to {nudge.replace('_', ' ')}."
        if self.mode == "live" and not self._reserve_call():
            if nudge:
                raise RequestError("Model call limit reached. Wait a minute or use demo mode.")
            return
        vid, mode, generation = actor["id"], self.mode, self.generation
        self.inflight.add(vid)
        self.pool.submit(self._decide, vid, context, actions, mode, generation, nudge)

    def _decide(self, vid, context, actions, mode, generation, nudge):
        try:
            with self.lock:
                if generation != self.generation:
                    return
            decision = (self.gateway.decide if mode == "live" else self.gateway.demo_decide)(context, actions)
            if nudge == "think":
                decision["think"] = True
            elif nudge == "talk":
                decision["speak"] = True
            with self.lock:
                if generation != self.generation:
                    return
                self.provider_failures["jev"] = 0
                try:
                    self.sim.apply_decision(vid, decision)
                except ValueError:
                    # Another villager or a clock tick can change eligibility
                    # while inference is in flight. Reconsider on the next pass.
                    return
                wants_narrative = decision.get("think") or decision.get("speak")
                allowed = wants_narrative and (mode == "demo" or self._reserve_call(narrative=True))
                # Get fresh context so Luna observes the actual consequences/queued action.
                narrative_context = self.sim.decision_context(vid)
            if allowed:
                with self.lock:
                    if generation != self.generation:
                        return
                narrative = (self.gateway.narrate if mode == "live" else self.gateway.demo_narrate)(narrative_context, decision)
                with self.lock:
                    if generation == self.generation:
                        self.sim.apply_narrative(vid, narrative)
                        self.provider_failures["luna"] = 0
            with self.lock:
                if generation == self.generation and not any(self.provider_failures.values()):
                    self.failures = 0
                    self.last_error = None
        except Exception as exc:
            with self.lock:
                if generation == self.generation:
                    self._model_error(exc)
        finally:
            with self.lock:
                if generation == self.generation:
                    self.inflight.discard(vid)

    def _model_error(self, exc):
        # Provider exceptions are sanitized at their source. Never expose request/response headers.
        with self.lock:
            safe = str(exc) if type(exc).__module__ == "village.providers" else "The model request failed. Check server connectivity and provider status."
            self.last_error = safe[:300]
            self.failures += 1
            provider = "luna" if safe.lower().startswith("luna:") else "jev" if safe.lower().startswith("jev:") else "other"
            self.provider_failures[provider] += 1
            if self.provider_failures[provider] >= 3:
                self.running = False
                self.notice = "Paused after repeated model errors. Resolve the provider issue or select demo mode."

    def _loop(self):
        last_tick = last_decision = last_save = time.monotonic()
        while not self.stop_event.wait(.1):
            now = time.monotonic()
            try:
                with self.lock:
                    if self.running and now - last_tick >= .5:
                        self._tick(minutes=2 * self.speed)
                        last_tick = now
                    interval = max(.5, 60 / self.jev_rpm) if self.mode == "live" else .25
                    if self.running and now - last_decision >= interval:
                        self._schedule_decision()
                        last_decision = now
                if now - last_save > 30:
                    self.save()
                    last_save = now
            except Exception as exc:
                with self.lock:
                    self.running = False
                    self.last_error = f"Simulation paused after {type(exc).__name__}; your last save is preserved."


class Handler(BaseHTTPRequestHandler):
    server_version = "Hearth/1.0"

    @property
    def app(self):
        return self.server.app

    def log_message(self, fmt, *args):
        if args and str(args[0]).startswith("GET /api/state"):
            return
        super().log_message(fmt, *args)

    def _send(self, status, body, content_type="application/json", *, download=False):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="hearth-village.json"')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _trusted_host(self):
        parsed = urlparse("http://" + self.headers.get("Host", ""))
        return parsed.hostname in ("127.0.0.1", "localhost", "::1")

    def do_GET(self):
        if not self._trusted_host():
            return self._send(403, {"error": "Hearth accepts local requests only."})
        path = urlparse(self.path).path
        if path == "/api/state":
            return self._send(200, self.app.snapshot())
        if path == "/api/events":
            return self._send(200, {"events": self.app.snapshot()["events"]})
        if path == "/api/export":
            return self._send(200, self.app.snapshot(), download=True)
        if path == "/api/health":
            return self._send(200, {"ok": True})
        static = ROOT / "static"
        requested = (static / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        if not requested.is_relative_to(static) or not requested.is_file():
            return self._send(404, {"error": "Not found."})
        return self._send(200, requested.read_bytes(), mimetypes.guess_type(requested.name)[0] or "application/octet-stream")

    def do_POST(self):
        origin = self.headers.get("Origin")
        if not self._trusted_host() or (origin and origin != f"http://{self.headers.get('Host')}") or self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self._send(403, {"error": "Cross-origin changes are not allowed."})
        if self.headers.get_content_type() != "application/json":
            return self._send(415, {"error": "Send application/json."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 16384:
                raise RequestError("Request body must be 1–16384 bytes.")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise RequestError("Expected a JSON object.")
            path = urlparse(self.path).path
            if path == "/api/control":
                result = self.app.control(body)
            elif path == "/api/oracle":
                result = self.app.oracle(body)
            elif path.startswith("/api/oracle/") and len(path.split("/")) == 5:
                _, _, _, context_id, action = path.split("/")
                if action == "dismiss":
                    result = self.app.dismiss_oracle(context_id, body)
                elif action == "update":
                    result = self.app.oracle(body, context_id=context_id)
                else:
                    return self._send(404, {"error": "Not found."})
            elif path == "/api/reset":
                result = self.app.reset(body)
            elif path == "/api/save":
                self.app.save()
                result = self.app.snapshot()
            elif path.startswith("/api/villagers/") and path.endswith("/nudge") and len(path.split("/")) == 5:
                result = self.app.nudge(path.split("/")[3], body)
            else:
                return self._send(404, {"error": "Not found."})
            self._send(200, result)
        except (RequestError, ValueError, TypeError) as exc:
            self._send(400, {"error": str(exc)[:300] if isinstance(exc, RequestError) else "Invalid request."})
        except Exception:
            self._send(500, {"error": "The village could not process that request."})


def main():
    parser = argparse.ArgumentParser(description="Hearth — a living village with Jev and Luna")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--demo", action="store_true", help="Use local rules; make no model calls")
    parser.add_argument("--fresh", action="store_true", help="Start a new village instead of restoring autosave")
    args = parser.parse_args()
    app = VillageApp(seed=args.seed, demo=args.demo, restore=not args.fresh)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.app = app
    def stop(signum, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    app.start()
    print(f"Hearth is ready at http://127.0.0.1:{args.port} ({app.mode}, paused).", flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()
