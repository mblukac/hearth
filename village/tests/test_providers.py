"""Provider boundary tests: no real network requests or model spending."""

import copy
import json
import unittest
from unittest.mock import patch

import httpx

from village.providers import LUNA_MODEL, ModelGateway, ProviderError


CONTEXT = {
    "seed": 42,
    "actor": {"id": "ada", "name": "Ada Miller", "age": 32, "x": 1, "y": 1,
              "goal": "Keep the bakery open.", "needs": {"hunger": 15, "social": 20, "energy": 80},
              "memories": [], "relationships": {}},
    "nearby": [{"id": "ben", "name": "Ben Ash", "age": 35, "x": 2, "y": 1,
                "thought": "This is private.", "memories": [{"text": "Private secret"}]}],
    "world": {"dread": 10, "tension": 10}, "contexts": [], "locations": [],
    "clock": {"day": 1, "minute": 650, "total_minutes": 650},
}
ACTIONS = [
    {"id": "eat", "label": "Eat", "description": "Eat a meal", "requires_target": False},
    {"id": "talk", "label": "Talk", "description": "Talk to a neighbor", "requires_target": True,
     "eligible_targets": ["ben", "remote_person", "ada"]},
]


def choice(selected, options):
    return {"type": "choice", "choice": selected, "confidence": 0.8,
            "probabilities": {key: 0.9 if key == selected else 0.1 / (len(options) - 1) for key in options}}


def jev_response():
    return {"success": True, "result": {"state": "Completed", "result": {
        "model": "jev-1.13.0", "usage": {"input_tokens": 250, "output_tokens": 50},
        "answers": {"action": choice("option_001", ["option_000", "option_001"]),
                    "think": choice("yes", ["yes", "no"]), "speak": choice("no", ["yes", "no"])},
    }}}


def luna_response(value, *, status="completed"):
    return {"status": status, "usage": {"input_tokens": 90, "output_tokens": 20},
            "output": [{"type": "reasoning", "summary": []},
                       {"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}]}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict("os.environ", {"CLOUDFLARE_ACCOUNT_ID": "test-account",
                                                   "CLOUDFLARE_API_TOKEN": "secret-cf-token",
                                                   "OPENAI_API_KEY": "secret-openai-token"})
        self.environment.start()
        self.requests = []
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.environment.stop()

    def gateway(self, body=None, status=200, handler=None):
        def respond(request):
            self.requests.append(request)
            return handler(request) if handler else httpx.Response(status, json=body)
        client = httpx.Client(transport=httpx.MockTransport(respond))
        self.clients.append(client)
        return ModelGateway(client=client, load_env=False)

    def test_joint_choice_cannot_select_remote_or_self_target(self):
        gateway = self.gateway(jev_response())
        decision = gateway.decide(CONTEXT, ACTIONS)
        self.assertEqual(decision["action"], "talk")
        self.assertEqual(decision["target_id"], "ben")
        self.assertTrue(decision["think"])
        self.assertFalse(decision["speak"])
        self.assertEqual(decision["source"], "jev")
        payload = json.loads(self.requests[0].content)
        self.assertEqual(self.requests[0].url.path, "/client/v4/accounts/test-account/ai/run")
        self.assertEqual(payload["model"], "typesafe/jev")
        self.assertEqual(len(payload["input"]["questions"]["action"]["criteria"]), 2)
        self.assertNotIn("remote_person", json.dumps(payload))
        self.assertAlmostEqual(sum(decision["probabilities"].values()), 1)
        self.assertEqual(gateway.metrics["jev"]["calls"], 1)
        self.assertEqual(gateway.metrics["total_tokens"], 300)

    def test_choice_budget_keeps_all_actions_and_nearest_targets(self):
        context = copy.deepcopy(CONTEXT)
        context["nearby"] = [{"id": f"v{i:02}", "x": i, "y": 1, "name": f"Person {i}"} for i in range(20)]
        actions = [{"id": f"action_{i}", "label": f"Action {i}", "requires_target": True,
                    "eligible_targets": [v["id"] for v in context["nearby"]]} for i in range(90)]
        criteria, pairs = ModelGateway._candidates(context, actions)
        self.assertLessEqual(len(criteria), 255)
        self.assertEqual({a for a, _ in pairs.values()}, {a["id"] for a in actions})
        self.assertEqual({target for _, target in pairs.values()}, {"v00", "v01"})

    def test_private_neighbor_thoughts_are_not_shared(self):
        context = copy.deepcopy(CONTEXT)
        context["oracle_nudge"] = "Listen to the distant roar."
        redacted = ModelGateway._context(context)
        self.assertNotIn("thought", redacted["nearby"][0])
        self.assertNotIn("memories", redacted["nearby"][0])
        self.assertEqual(redacted["oracle_nudge"], context["oracle_nudge"])
        self.assertIn("thought", context["nearby"][0])

    def test_invalid_model_choice_never_becomes_demo(self):
        body = jev_response()
        body["result"]["result"]["answers"]["action"]["choice"] = "invented_action"
        gateway = self.gateway(body)
        with self.assertRaisesRegex(ProviderError, "invalid action choice"):
            gateway.decide(CONTEXT, ACTIONS)
        self.assertEqual(gateway.metrics["jev"]["errors"], 1)
        self.assertEqual(gateway.metrics["jev"]["successes"], 0)

    def test_nan_probabilities_are_rejected(self):
        body = jev_response()
        body["result"]["result"]["answers"]["action"]["probabilities"]["option_000"] = -1
        with self.assertRaisesRegex(ProviderError, "probabilities"):
            self.gateway(body).decide(CONTEXT, ACTIONS)

    def test_errors_and_status_do_not_expose_upstream_secrets(self):
        gateway = self.gateway({"error": "secret-cf-token secret-openai-token sensitive upstream body"}, status=403)
        with self.assertRaises(ProviderError) as caught:
            gateway.decide(CONTEXT, ACTIONS)
        rendered = str(caught.exception) + json.dumps(gateway.status())
        self.assertNotIn("secret-", rendered)
        self.assertNotIn("sensitive upstream", rendered)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(gateway.status()["luna"]["model"], "gpt-6-luna")

    def test_timeout_is_not_retried(self):
        def fail(request):
            raise httpx.ReadTimeout("secret-cf-token", request=request)
        gateway = self.gateway(handler=fail)
        with self.assertRaisesRegex(ProviderError, "timed out"):
            gateway.decide(CONTEXT, ACTIONS)
        self.assertEqual(len(self.requests), 1)

    def test_connection_failures_have_only_one_bounded_retry(self):
        def fail(request):
            raise httpx.ConnectError("secret-cf-token", request=request)
        gateway = self.gateway(handler=fail)
        with patch("village.providers.time.sleep") as sleep:
            with self.assertRaisesRegex(ProviderError, "connection unavailable"):
                gateway.decide(CONTEXT, ACTIONS)
        self.assertEqual(len(self.requests), 2)
        sleep.assert_called_once_with(0.15)

    def test_luna_uses_exact_model_low_reasoning_and_strict_json(self):
        gateway = self.gateway(luna_response({"thought": "I hope Ben has heard the news.", "speech": "Not permitted by gate"}))
        narrative = gateway.narrate(CONTEXT, {"action": "talk", "target_id": "ben", "think": True, "speak": False})
        payload = json.loads(self.requests[0].content)
        self.assertEqual(payload["model"], LUNA_MODEL)
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertLessEqual(payload["max_output_tokens"], 1000)
        self.assertFalse(payload["store"])
        self.assertEqual(narrative["speech"], "")
        self.assertEqual(narrative["source"], "luna")

    def test_disabled_narrative_gates_spend_nothing(self):
        gateway = self.gateway({})
        result = gateway.narrate(CONTEXT, {"think": False, "speak": False})
        self.assertTrue(result["skipped"])
        self.assertEqual(gateway.metrics["total_calls"], 0)
        self.assertEqual(self.requests, [])

    def test_incomplete_luna_response_never_applies_narrative(self):
        gateway = self.gateway(luna_response({"thought": "Partial thought", "speech": ""}, status="incomplete"))
        with self.assertRaisesRegex(ProviderError, "incomplete"):
            gateway.narrate(CONTEXT, {"think": True})
        self.assertEqual(gateway.metrics["luna"]["output_tokens"], 20)

    def test_oracle_validates_effects_and_preserves_original_event(self):
        gateway = self.gateway(luna_response({"kind": "threat", "effects": {
            "dread": 45, "tension": 20, "prosperity": -10, "food": 0, "weather": None}}))
        event = gateway.interpret_oracle("A Godzilla-like creature approaches.", 60, 12)
        self.assertEqual(event["source"], "luna")
        self.assertEqual(event["duration_hours"], 12)
        self.assertNotIn("weather", event["effects"])
        self.assertEqual(event["text"], "A Godzilla-like creature approaches.")

    def test_invalid_oracle_effect_is_not_applied(self):
        gateway = self.gateway(luna_response({"kind": "threat", "effects": {
            "dread": 9000, "tension": 20, "prosperity": -10, "food": 0, "weather": None}}))
        with self.assertRaisesRegex(ProviderError, "numeric effects"):
            gateway.interpret_oracle("A creature approaches.")

    def test_demo_is_deterministic_contextual_and_makes_no_requests(self):
        gateway = self.gateway({})
        first = gateway.demo_decide(CONTEXT, ACTIONS)
        self.assertEqual(first, gateway.demo_decide(CONTEXT, ACTIONS))
        self.assertEqual(first["source"], "demo")
        event = gateway.demo_interpret_oracle("A Godzilla-like creature approaches.", 70)
        self.assertEqual(event["kind"], "threat")
        self.assertGreater(event["effects"]["dread"], 0)
        context = copy.deepcopy(CONTEXT)
        context["contexts"] = [event]
        narrative = gateway.demo_narrate(context, {"think": True, "speak": True, "target_id": "ben"})
        self.assertIn("Godzilla", narrative["thought"])
        self.assertEqual(gateway.metrics["total_calls"], 0)

    def test_demo_rain_is_weather_not_ai_doom(self):
        event = self.gateway({}).demo_interpret_oracle("Gentle rain settles over the village.")
        self.assertEqual(event["kind"], "weather")
        self.assertEqual(event["effects"]["weather"], "rain")

    def test_model_context_and_demo_keep_newest_oracle_first(self):
        context = copy.deepcopy(CONTEXT)
        context["contexts"] = [{"text": f"Event {i}"} for i in range(12)]
        self.assertEqual(ModelGateway._context(context)["contexts"], context["contexts"][:8])
        narrative = self.gateway({}).demo_narrate(context, {"think": True})
        self.assertIn("Event 0", narrative["thought"])
        self.assertNotIn("Event 11", narrative["thought"])

    def test_demo_food_production_responds_to_scarcity(self):
        actions = [{"id": key, "label": key, "requires_target": False} for key in ("harvest", "observe")]
        context = copy.deepcopy(CONTEXT)
        context["world"]["food"] = 95
        gateway = self.gateway({})
        stocked = gateway.demo_decide(context, actions)
        context["world"]["food"] = 0
        scarce = gateway.demo_decide(context, actions)
        self.assertGreater(scarce["probabilities"]["harvest"], stocked["probabilities"]["harvest"])

    def test_demo_marriage_dialogue_expresses_commitment(self):
        narrative = self.gateway({}).demo_narrate(CONTEXT, {"action": "marry", "target_id": "ben", "speak": True})
        self.assertIn("choosing this life", narrative["speech"])
        self.assertNotIn("for a while", narrative["speech"])

    def test_jev_receives_scenario_resolutions_as_history(self):
        context = copy.deepcopy(CONTEXT)
        retired = {"id": "monster-old", "text": "Godzilla is approaching.", "kind": "threat",
                   "status": "dismissed", "ended_at": 650, "resolution": "The creature has left the valley."}
        context["scenario_history"] = [dict(retired, id=f"monster-{i}", internal_debug="omit") for i in range(9)]
        context["actor"]["memories"] = [{"text": retired["text"], "context_id": "monster-0", "resolved": True,
                                         "context_status": "dismissed", "resolution": retired["resolution"]}]
        self.gateway(jev_response()).decide(context, ACTIONS)
        payload = json.loads(self.requests[0].content)["input"]
        self.assertEqual(payload["state"]["contexts"], [])
        self.assertEqual(len(payload["state"]["scenario_history"]), 6)
        self.assertNotIn("internal_debug", payload["state"]["scenario_history"][0])
        self.assertEqual(payload["state"]["scenario_history"][0]["resolution"], retired["resolution"])
        self.assertTrue(payload["state"]["actor"]["memories"][0]["resolved"])
        self.assertIn("no longer happening", payload["state"]["scenario_lifecycle"])
        self.assertTrue(all("scenario_lifecycle" in question["instructions"] for question in payload["questions"].values()))

    def test_luna_receives_active_replacement_and_historical_version(self):
        context = copy.deepcopy(CONTEXT)
        context["contexts"] = [{"id": "new-weather", "text": "A gentle rain falls.", "status": "active"}]
        context["scenario_history"] = [{"id": "old-storm", "text": "A violent storm arrives.", "status": "replaced",
                                        "ended_at": 650, "resolution": "The storm has eased into gentle rain.",
                                        "replaced_by": "new-weather"}]
        narrative = self.gateway(luna_response({"thought": "The gentler rain is a relief.", "speech": ""})).narrate(
            context, {"think": True, "speak": False})
        payload = json.loads(self.requests[0].content)
        model_context = json.loads(payload["input"])["context"]
        self.assertIn("Active contexts are authoritative", payload["instructions"])
        self.assertIn("supersedes its old version", payload["instructions"])
        self.assertEqual(model_context["scenario_history"][0]["replaced_by"], "new-weather")
        self.assertEqual(narrative["context_ids"], ["new-weather"])

    def test_demo_recalls_withdrawn_scenario_as_resolved(self):
        context = copy.deepcopy(CONTEXT)
        context["actor"]["memories"] = [{"text": "Godzilla is approaching.", "context_id": "monster-old"}]
        context["scenario_history"] = [{"id": "monster-old", "status": "dismissed",
                                        "resolution": "The creature has left the valley."}]
        with patch.object(ModelGateway, "_rng") as rng:
            rng.return_value.random.return_value = 0
            narrative = self.gateway({}).demo_narrate(context, {"think": True, "speak": True, "action": "talk"})
        self.assertIn("has left the valley", narrative["thought"])
        self.assertIn("belongs to the past", narrative["thought"])
        self.assertNotIn("is approaching", narrative["thought"] + narrative["speech"])
        self.assertEqual(narrative["context_ids"], [])

    def test_resolved_memory_stays_historical_after_history_is_trimmed(self):
        context = copy.deepcopy(CONTEXT)
        context["actor"]["memories"] = [{"text": "Godzilla is approaching.", "resolved": True,
                                         "context_status": "expired", "resolution": "The threat has passed."}]
        with patch.object(ModelGateway, "_rng") as rng:
            rng.return_value.random.return_value = 0
            narrative = self.gateway({}).demo_narrate(context, {"think": True})
        self.assertIn("threat has passed", narrative["thought"])
        self.assertNotIn("is approaching", narrative["thought"])

    def test_missing_keys_are_explicit_failures(self):
        with patch.dict("os.environ", {"CLOUDFLARE_API_TOKEN": "", "OPENAI_API_KEY": ""}):
            gateway = self.gateway({})
        with self.assertRaisesRegex(ProviderError, "CLOUDFLARE"):
            gateway.decide(CONTEXT, ACTIONS)
        with self.assertRaisesRegex(ProviderError, "OPENAI_API_KEY"):
            gateway.narrate(CONTEXT, {"think": True})
        self.assertEqual(len(self.requests), 0)


if __name__ == "__main__":
    unittest.main()
