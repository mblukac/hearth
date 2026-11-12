"""Behavioral checks for the authoritative simulation, without model calls."""

import json
import math
from pathlib import Path
import re

import pytest

from village.data import ACTIONS, ACTION_BY_ID, LOCATIONS
from village.engine import GESTATION_DAYS, Simulation, distance


def decision(action, target=None):
    return dict(action=action, target_id=target, think=True, speak=bool(target),
                confidence=.8, probabilities={action: 1}, source="demo")


def meet(simulation, first="v01", second="v02"):
    actor, target = simulation.villager(first), simulation.villager(second)
    actor.update(x=11, y=10)
    target.update(x=12, y=10)
    return actor, target


def finish_walk(simulation, actor_id, max_ticks=200):
    for _ in range(max_ticks):
        if not simulation.villager(actor_id).get("pending_action"):
            return
        simulation.tick(2)
    pytest.fail("Movement failed to complete or report interruption")


def strengthen(first, second, status="partner"):
    for actor, target in ((first, second), (second, first)):
        actor["relationships"][target["id"]] = dict(affinity=90, trust=90, romance=90, status=status)
        actor["cooldowns"] = {}
        actor["needs"].update(energy=90, safety=90)


def test_twenty_distinct_adults_and_large_executable_catalog():
    simulation = Simulation()
    residents = simulation.state["villagers"]
    assert len(residents) == 20
    assert len({v["id"] for v in residents}) == 20
    assert len({v["name"] for v in residents}) == 20
    assert len(ACTIONS) >= 80
    assert len(ACTION_BY_ID) == len(ACTIONS)
    for resident in residents:
        assert resident["age"] >= 18
        assert len(resident["backstory"]) > 80
        assert resident["demographics"]["education"]
        assert simulation._walkable((resident["x"], resident["y"]))
        context_ids = {person["id"] for person in simulation.decision_context(resident["id"])["nearby"]}
        for action in simulation.available_actions(resident["id"]):
            assert set(action["eligible_targets"]) <= context_ids
            assert bool(action["eligible_targets"]) == action["requires_target"]


def test_social_action_requires_walking_before_effect_and_bubble():
    simulation = Simulation()
    actor, target = simulation.villager("v01"), simulation.villager("v02")
    before = actor["relationships"][target["id"]]["affinity"]
    event = simulation.apply_decision(actor["id"], decision("talk", target["id"]))
    assert event["type"] == "movement"
    assert actor["pending_action"]
    assert actor["relationships"][target["id"]]["affinity"] == before
    simulation.apply_narrative(actor["id"], dict(thought="I hope Ivo likes the orchard.", speech="Meet me after work?", source="luna"))
    assert actor["speech"] == ""
    assert not any("Meet me after work?" in memory["text"] for memory in target["memories"])
    finish_walk(simulation, actor["id"])
    assert distance(actor, target) <= 1.55
    assert actor["action"] == "talk"
    assert actor["relationships"][target["id"]]["affinity"] > before
    assert actor["speech"] == "Meet me after work?"
    assert any("Meet me after work?" in memory["text"] for memory in target["memories"])
    assert not any("I hope Ivo likes" in memory["text"] for memory in target["memories"])


def test_paths_go_around_buildings_and_water():
    simulation = Simulation()
    actor = simulation.villager("v01")
    actor.update(x=2, y=4)
    simulation.apply_decision(actor["id"], decision("fish"))
    for _ in range(100):
        simulation.tick(2)
        assert simulation._walkable((round(actor["x"]), round(actor["y"])))
        if not actor["pending_action"]:
            break
    assert actor["action"] == "fish"
    assert actor["x"] == 42 and actor["y"] == 20


def _drawn_lanes():
    """Lane centre lines as static/scene.js draws them, in tiles."""
    source = (Path(__file__).resolve().parents[1] / "static" / "scene.js").read_text()
    match = re.search(r"for\(const y of \[([\d.,]+)\]\)\{c\.moveTo\(1\*T,y\*T\);c\.lineTo\(43\.8\*T,y\*T\);\}"
                      r"for\(const x of \[([\d.,]+)\]\)\{c\.moveTo\(x\*T,([\d.]+)\*T\);c\.lineTo\(x\*T,([\d.]+)\*T\);\}"
                      r"c\.stroke\(\);\s*c\.strokeStyle='#[0-9a-f]+';c\.lineWidth=\d+;c\.stroke\(\);"
                      r"c\.strokeStyle='#[0-9a-f]+';c\.lineWidth=\d+;c\.stroke\(\);", source)
    assert match, "scene.js lane drawing changed; update this test with it"
    width = int(re.search(r"c\.lineCap='square';c\.strokeStyle='#[0-9a-f]+';c\.lineWidth=(\d+)", source).group(1))
    rows = [float(value) for value in match.group(1).split(",")]
    columns = [float(value) for value in match.group(2).split(",")]
    return rows, columns, float(match.group(3)), float(match.group(4)), width / 2 / 24


def test_buildings_sit_between_lanes_without_overlapping():
    rows, columns, top, bottom, half = _drawn_lanes()
    places = [place for place in LOCATIONS if place["id"] != "river"]
    for place in places:
        x0, x1, y0, y1 = place["x"], place["x"] + place["w"], place["y"], place["y"] + place["h"]
        for row in rows:
            assert not (y0 < row + half and row - half < y1), f"{place['id']} sits on the lane at y={row}"
        for column in columns:
            on_column = x0 < column + half and column - half < x1
            assert not (on_column and y0 < bottom and top < y1), f"{place['id']} sits on the lane at x={column}"
    for index, first in enumerate(places):
        for second in places[index + 1:]:
            apart = (first["x"] + first["w"] <= second["x"] or second["x"] + second["w"] <= first["x"]
                     or first["y"] + first["h"] <= second["y"] or second["y"] + second["h"] <= first["y"])
            assert apart, f"{first['id']} overlaps {second['id']}"


def test_restored_save_adopts_the_authored_map():
    simulation = Simulation(seed=5)
    save = json.loads(json.dumps(simulation.snapshot()))
    old_home = next(place for place in save["locations"] if place["id"] == "home_2")
    old_home.update(x=11, y=23, entrance={"x": 13, "y": 27})
    resident = next(villager for villager in save["villagers"] if villager["home"] == "home_2")
    resident.update(x=15, y=23)  # Inside the corrected house.
    restored = Simulation.from_state(save)
    assert restored.state["locations"] == LOCATIONS
    moved = restored.villager(resident["id"])
    assert restored._walkable((round(moved["x"]), round(moved["y"])))
    restored.apply_decision(moved["id"], decision("go_home"))
    finish_walk(restored, moved["id"])
    home = next(place for place in LOCATIONS if place["id"] == "home_2")
    assert (moved["x"], moved["y"]) == (home["entrance"]["x"], home["entrance"]["y"])


def test_stale_interaction_is_observably_interrupted():
    simulation = Simulation()
    simulation.apply_decision("v01", decision("intimacy", "v02"))
    simulation.villager("v02")["needs"]["safety"] = 0
    finish_walk(simulation, "v01")
    assert simulation.villager("v01")["action"] == "idle"
    assert simulation.state["events"][0]["type"] == "interrupted"
    assert not any(event.get("action") == "intimacy" and event["type"] == "romance" for event in simulation.state["events"])


@pytest.mark.parametrize("payload", [decision("invented"), decision("talk"), decision("talk", "absent"), decision("talk", "v01"), decision("eat", "v02")])
def test_invalid_model_decisions_do_not_change_world(payload):
    simulation = Simulation()
    before = simulation.snapshot()
    with pytest.raises(ValueError):
        simulation.apply_decision("v01", payload)
    assert simulation.snapshot() == before


def test_resources_and_cooldowns_are_authoritative():
    simulation = Simulation()
    actor = simulation.villager("v01")
    simulation.state["world"]["food"] = 0
    with pytest.raises(ValueError):
        simulation.apply_decision(actor["id"], decision("eat"))
    assert "eat" not in {action["id"] for action in simulation.available_actions(actor["id"])}
    simulation.apply_decision(actor["id"], decision("think"))
    with pytest.raises(ValueError):
        simulation.apply_decision(actor["id"], decision("think"))
    simulation.tick(50)
    simulation.apply_decision(actor["id"], decision("think"))


@pytest.mark.parametrize("tick_minutes", [2, 5, 20])
def test_passive_world_recovery_depends_on_elapsed_time_not_tick_size(tick_minutes):
    simulation = Simulation()
    simulation.state["world"].update(tension=100, dread=60, food=100)
    for _ in range(240 // tick_minutes):
        simulation.tick(tick_minutes)
    assert simulation.state["world"]["tension"] == pytest.approx(99.52)
    assert simulation.state["world"]["dread"] == pytest.approx(59.28)


def test_small_decay_survives_save_restore_and_stops_at_zero():
    simulation = Simulation()
    simulation.state["world"].update(tension=.006, dread=.01, food=100)
    simulation.tick(2)
    restored = Simulation.from_state(json.loads(json.dumps(simulation.snapshot())))
    assert restored.state["world"]["tension"] == pytest.approx(.002)
    assert restored.state["world"]["dread"] == pytest.approx(.004)
    restored.tick(2)
    assert restored.state["world"]["tension"] == 0
    assert restored.state["world"]["dread"] == 0


def test_scarcity_pressure_still_outweighs_passive_recovery():
    simulation = Simulation()
    simulation.state["world"].update(tension=50, food=0)
    for actor in simulation.state["villagers"]:
        actor["needs"]["hunger"] = 10
    simulation.tick(2)
    assert simulation.state["world"]["tension"] == pytest.approx(50 + 2 * (20 * .006 - .002))
    simulation.tick(1440)
    assert simulation.state["world"]["tension"] == 100


def test_romance_requires_reciprocity_adults_compatibility_and_not_family():
    simulation = Simulation()
    actor, target = meet(simulation)
    target["relationships"][actor["id"]]["romance"] = 0
    with pytest.raises(ValueError):
        simulation.apply_decision(actor["id"], decision("intimacy", target["id"]))
    strengthen(actor, target)
    target["age"] = 17
    with pytest.raises(ValueError):
        simulation.apply_decision(actor["id"], decision("flirt", target["id"]))
    target["age"] = 36
    actor["family"]["siblings"].append(target["id"])
    with pytest.raises(ValueError):
        simulation.apply_decision(actor["id"], decision("flirt", target["id"]))
    actor["family"]["siblings"] = []
    target["demographics"]["orientation"] = "gay"
    with pytest.raises(ValueError):
        simulation.apply_decision(actor["id"], decision("flirt", target["id"]))


def test_reproductive_pair_and_shared_family_plan_required():
    simulation = Simulation()
    first, second = meet(simulation, "v17", "v18")
    strengthen(first, second)
    simulation.apply_decision(first["id"], decision("discuss_family", second["id"]))
    assert not simulation._romance_eligible(first, second, "try_for_child")
    with pytest.raises(ValueError):
        simulation.apply_decision(first["id"], decision("try_for_child", second["id"]))
    first, second = meet(simulation)
    with pytest.raises(ValueError):
        simulation.apply_decision(first["id"], decision("try_for_child", second["id"]))


def test_conception_birth_family_links_and_child_exclusion():
    simulation = Simulation()
    actor, partner = meet(simulation)
    strengthen(actor, partner)
    simulation.apply_decision(actor["id"], decision("discuss_family", partner["id"]))
    simulation.rng.seed(1)  # First random draw .134 < conception probability .32.
    event = simulation.apply_decision(actor["id"], decision("try_for_child", partner["id"]))
    assert "expecting" in event["text"]
    assert actor["pregnancy"]["gestation_days"] == GESTATION_DAYS
    for _ in range(GESTATION_DAYS):
        simulation.tick(1440)
    assert actor["pregnancy"] is None
    assert len(simulation.state["villagers"]) == 21
    child = simulation.state["villagers"][-1]
    assert child["age"] == 0
    assert child["family"]["parents"] == [actor["id"], partner["id"]]
    assert child["id"] in actor["family"]["children"]
    assert not simulation._romance_eligible(partner, child, "flirt")
    assert {action["id"] for action in simulation.available_actions(child["id"])} <= {"sleep", "rest", "observe"}


def test_marriage_and_breakup_preserve_reciprocal_status():
    simulation = Simulation()
    actor, partner = meet(simulation)
    simulation.apply_decision(actor["id"], decision("marry", partner["id"]))
    assert actor["relationships"][partner["id"]]["status"] == "married"
    assert partner["relationships"][actor["id"]]["status"] == "married"
    simulation.apply_decision(actor["id"], decision("break_up", partner["id"]))
    assert actor["relationships"][partner["id"]]["status"] == "former_partner"
    assert partner["relationships"][actor["id"]]["status"] == "former_partner"
    assert "partner_id" not in actor


def test_oracle_reaches_everyone_and_expires_without_erasing_memories():
    simulation = Simulation()
    before = [actor["needs"]["safety"] for actor in simulation.state["villagers"]]
    event = simulation.apply_oracle(dict(text="A gigantic creature approaches the village", kind="threat", intensity=80,
                                         duration_hours=1, effects={"dread": 50, "tension": 30}, source="demo"))
    assert event["type"] == "oracle"
    assert simulation.state["world"]["dread"] == 58
    for actor, safety in zip(simulation.state["villagers"], before):
        assert actor["needs"]["safety"] < safety
        assert "gigantic creature" in actor["memories"][0]["text"]
        assert simulation.decision_context(actor["id"])["contexts"][0]["kind"] == "threat"
    simulation.tick(60)
    assert not simulation.state["contexts"]
    assert "gigantic creature" in simulation.villager("v01")["memories"][0]["text"]


@pytest.mark.parametrize("field", ["intensity", "duration_hours"])
def test_nonfinite_oracle_is_atomic(field):
    simulation = Simulation()
    before = simulation.snapshot()
    with pytest.raises(ValueError):
        simulation.apply_oracle(dict(text="Doom", **{field: math.nan}))
    assert simulation.snapshot() == before


def test_saved_rng_and_pending_path_resume_identically():
    original = Simulation(24)
    original.apply_decision("v01", decision("go_home"))
    original.tick(3)
    restored = Simulation.from_state(json.loads(json.dumps(original.snapshot())))
    original.tick(80)
    restored.tick(80)
    assert json.loads(json.dumps(original.snapshot())) == json.loads(json.dumps(restored.snapshot()))
    original.apply_decision("v02", decision("explore"))
    restored.apply_decision("v02", decision("explore"))
    assert json.loads(json.dumps(original.snapshot())) == json.loads(json.dumps(restored.snapshot()))


def test_revolt_requires_crisis_and_organized_support_then_changes_leadership():
    simulation = Simulation()
    with pytest.raises(ValueError):
        simulation.apply_decision("v17", decision("revolt"))
    simulation.state["world"].update(tension=90, civic_support=60)
    simulation.apply_decision("v17", decision("revolt"))
    finish_walk(simulation, "v17")
    assert "Tess Morgan" in simulation.state["world"]["leadership"]
    assert simulation.state["world"]["tension"] < 80


def test_speech_is_remembered_only_by_people_who_can_hear():
    simulation = Simulation()
    actor, target = meet(simulation)
    far_away = simulation.villager("v03")
    simulation.apply_decision(actor["id"], decision("talk", target["id"]))
    simulation.apply_narrative(actor["id"], dict(thought="This stays private.", speech="The orchard needs new trees.", source="luna"))
    for resident in (actor, target):
        memory = resident["memories"][0]
        assert "orchard needs new trees" in memory["text"]
        assert memory["source"] == "luna"
    assert all("This stays private" not in memory["text"] for resident in simulation.state["villagers"] for memory in resident["memories"])
    assert not any("orchard needs new trees" in memory["text"] for memory in far_away["memories"])


def threat_event(**overrides):
    return dict(text="A Godzilla-like creature approaches Hearth.", kind="threat", intensity=80,
                duration_hours=overrides.pop("duration_hours", 24),
                effects={"dread": 50, "tension": 30, "food": -5}, source="demo", **overrides)


def test_dismissal_retires_scenario_preserves_history_and_teaches_resolution():
    simulation = Simulation()
    applied = simulation.apply_oracle(threat_event())
    identity = applied["context_id"]
    before = simulation.snapshot()
    result = simulation.dismiss_context(identity, "The sighting was mistaken; the valley is clear.")
    assert result["type"] == "context_resolved"
    assert result["status"] == "dismissed"
    assert simulation.state["contexts"] == []
    history = simulation.state["scenario_history"][0]
    assert history["id"] == identity
    assert history["text"] == before["contexts"][0]["text"]
    assert history["status"] == "dismissed"
    assert history["ended_at"] == simulation.state["total_minutes"]
    assert history["effects"] == {"dread": 50, "tension": 30, "food": -5}
    assert simulation.state["world"]["food"] == before["world"]["food"]
    assert simulation.state["world"]["treasury"] == before["world"]["treasury"]
    assert simulation.state["world"]["dread"] < before["world"]["dread"]
    assert simulation.state["world"]["tension"] < before["world"]["tension"]
    for actor, previous in zip(simulation.state["villagers"], before["villagers"]):
        assert actor["needs"]["safety"] > previous["needs"]["safety"]
        assert "no longer active" in actor["thought"]
        assert actor["thought_source"] == "oracle-resolution"
        original = next(memory for memory in actor["memories"] if memory["id"] == previous["memories"][0]["id"])
        assert original["text"] == previous["memories"][0]["text"]
        assert original["resolved"] is True and original["context_status"] == "dismissed"
        assert actor["memories"][0]["resolved"] is True
        assert actor["memories"][0]["context_id"] == identity
    context = simulation.decision_context("v01")
    assert context["contexts"] == []
    assert context["scenario_history"][0]["id"] == identity


def test_dismissal_does_not_remove_other_scenarios_or_undo_economy():
    simulation = Simulation()
    first = simulation.apply_oracle(threat_event())["context_id"]
    second = simulation.apply_oracle(dict(text="A prolonged drought threatens the fields.", kind="scarcity", intensity=60,
                                         duration_hours=50, effects={"food": -20, "dread": 15}))["context_id"]
    simulation.state["world"]["food"] -= 3  # Food actually eaten after both events.
    food = simulation.state["world"]["food"]
    simulation.dismiss_context(first)
    assert simulation._active_context_ids() == [second]
    assert simulation.state["world"]["food"] == food
    assert "Other active circumstances" in simulation.villager("v01")["thought"]
    active_memory = next(m for m in simulation.villager("v01")["memories"] if m.get("context_id") == second)
    assert active_memory["resolved"] is False


@pytest.mark.parametrize("replacement", [None, {}, {"text": ""}, {"text": None},
                                         {"text": "A new day", "intensity": math.inf},
                                         {"text": "A new day", "effects": {"food": math.nan}}])
def test_replacement_validation_is_atomic(replacement):
    simulation = Simulation()
    identity = simulation.apply_oracle(threat_event())["context_id"]
    before = simulation.snapshot()
    with pytest.raises(ValueError):
        simulation.replace_context(identity, replacement)
    assert simulation.snapshot() == before


def test_replacement_archives_old_scenario_with_link_and_applies_new_one():
    simulation = Simulation()
    identity = simulation.apply_oracle(threat_event())["context_id"]
    replacement = simulation.replace_context(identity, dict(text="The valley celebrates a peaceful harvest.",
                                                            kind="celebration", intensity=50, effects={"food": 12}))
    assert replacement["context_id"] != identity
    assert simulation._active_context_ids() == [replacement["context_id"]]
    assert simulation.state["contexts"][0]["status"] == "active"
    history = simulation.state["scenario_history"][0]
    assert history["status"] == "replaced"
    assert history["replaced_by"] == replacement["context_id"]
    for actor in simulation.state["villagers"]:
        assert "peaceful harvest" in actor["thought"]
        assert "Godzilla" not in actor["thought"]
        original = next(memory for memory in actor["memories"] if memory.get("context_id") == identity)
        assert original["resolved"] is True


def test_unknown_or_already_ended_scenario_is_atomic():
    simulation = Simulation()
    identity = simulation.apply_oracle(threat_event())["context_id"]
    simulation.dismiss_context(identity)
    before = simulation.snapshot()
    for operation in (lambda: simulation.dismiss_context(identity),
                      lambda: simulation.dismiss_context("unknown"),
                      lambda: simulation.replace_context(identity, dict(text="Something else"))):
        with pytest.raises(ValueError):
            operation()
        assert simulation.snapshot() == before


def test_expiry_uses_resolution_lifecycle_and_stops_pressure():
    simulation = Simulation()
    identity = simulation.apply_oracle(threat_event(duration_hours=.25))["context_id"]
    simulation.tick(15)
    assert simulation.state["contexts"] == []
    history = simulation.state["scenario_history"][0]
    assert history["id"] == identity and history["status"] == "expired"
    assert history["ended_at"] == 495
    assert "no longer active" in simulation.villager("v01")["thought"]
    dread, tension = simulation.state["world"]["dread"], simulation.state["world"]["tension"]
    simulation.tick(5)
    assert simulation.state["world"]["dread"] <= dread
    assert simulation.state["world"]["tension"] <= tension


def test_withdrawal_cancels_affected_walk_and_stale_narratives_but_keeps_prior_plan():
    simulation = Simulation()
    simulation.apply_decision("v03", decision("go_home"))
    unaffected = simulation.villager("v03")["pending_action"].copy()
    identity = simulation.apply_oracle(threat_event())["context_id"]
    simulation.apply_decision("v01", decision("warn", "v02"))
    stale = dict(thought="The creature is coming.", speech="Hide before Godzilla reaches us!", source="luna", context_ids=[identity])
    simulation.apply_narrative("v01", stale)
    assert simulation.villager("v01")["pending_narrative"]
    simulation.dismiss_context(identity)
    actor = simulation.villager("v01")
    assert actor["pending_action"] is None and actor["destination"] is None
    assert "pending_narrative" not in actor
    assert actor["speech"] == ""
    assert simulation.villager("v03")["pending_action"] == unaffected
    expected_thought = actor["thought"]
    simulation.apply_narrative("v01", stale)
    assert actor["thought"] == expected_thought
    simulation.apply_narrative("v01", dict(thought="Untagged old narrative", speech="It still approaches!"))
    assert actor["thought"] == expected_thought
    simulation.apply_decision("v01", decision("think"))
    simulation.apply_narrative("v01", stale)  # Stale even after a newer decision replaces old provenance.
    assert actor["thought"] == expected_thought
    simulation.apply_narrative("v01", dict(thought="The warning has ended.", context_ids=[]))
    assert actor["thought"] == "The warning has ended."


def test_withdrawal_clears_existing_bubbles_and_marks_spoken_memories_resolved():
    simulation = Simulation()
    actor, target = meet(simulation)
    identity = simulation.apply_oracle(threat_event())["context_id"]
    simulation.apply_decision(actor["id"], decision("talk", target["id"]))
    simulation.apply_narrative(actor["id"], dict(speech="I saw the creature near the river.", context_ids=[identity]))
    spoken_id = target["memories"][0]["id"]
    assert actor["speech"]
    simulation.dismiss_context(identity)
    assert actor["speech"] == ""
    spoken = next(memory for memory in target["memories"] if memory["id"] == spoken_id)
    assert spoken["resolved"] is True
    assert identity in spoken["resolved_context_ids"]


def test_lifecycle_save_restore_and_legacy_migration_preserve_world():
    original = Simulation()
    identity = original.apply_oracle(threat_event())["context_id"]
    original.dismiss_context(identity)
    active = original.apply_oracle(dict(text="A mild summer breeze", kind="weather", effects={"weather": "breezy"}))["context_id"]
    restored = Simulation.from_state(json.loads(json.dumps(original.snapshot())))
    assert json.loads(json.dumps(restored.snapshot())) == json.loads(json.dumps(original.snapshot()))
    another = restored.apply_oracle(dict(text="A local festival", kind="celebration"))["context_id"]
    assert len({identity, active, another}) == 3
    legacy = json.loads(json.dumps(original.snapshot()))
    legacy.pop("scenario_history")
    for context in legacy["contexts"]:
        context.pop("status")
        context.pop("effects")
    names = [actor["name"] for actor in legacy["villagers"]]
    loaded = Simulation.from_state(legacy)
    assert [actor["name"] for actor in loaded.state["villagers"]] == names
    assert loaded.state["world"] == legacy["world"]
    assert loaded.state["contexts"][0]["status"] == "active"
    loaded.dismiss_context(active)
    assert loaded.state["scenario_history"][0]["id"] == active


def test_restore_retires_already_expired_legacy_context():
    simulation = Simulation()
    identity = simulation.apply_oracle(threat_event())["context_id"]
    save = simulation.snapshot()
    save.pop("scenario_history")
    save["contexts"][0]["expires_at"] = save["total_minutes"] - 1
    save["contexts"][0].pop("status")
    restored = Simulation.from_state(save)
    assert restored.state["contexts"] == []
    assert restored.state["scenario_history"][0]["id"] == identity
    assert restored.state["scenario_history"][0]["status"] == "expired"


def test_gossip_about_ended_scenario_reports_resolution():
    simulation = Simulation()
    actor, target = meet(simulation)
    identity = simulation.apply_oracle(threat_event())["context_id"]
    simulation.dismiss_context(identity)
    actor["memories"] = [actor["memories"][0]]  # Make the selected gossip memory deterministic.
    event = simulation.apply_decision(actor["id"], decision("gossip", target["id"]))
    assert "no longer active" in event["text"]
    assert "Godzilla-like creature approaches" not in event["text"]
    assert target["rumors"][0]["resolved"] is True


def test_history_is_bounded_and_context_ids_remain_unique():
    simulation = Simulation()
    identities = []
    for index in range(55):
        identity = simulation.apply_oracle(dict(text=f"Temporary festival {index}", kind="celebration"))["context_id"]
        identities.append(identity)
        simulation.dismiss_context(identity)
    assert len(simulation.state["scenario_history"]) == 50
    assert len(set(identities)) == 55
    assert simulation.state["scenario_history"][0]["id"] == identities[-1]


def test_weather_scenario_end_restores_remaining_weather_then_baseline():
    simulation = Simulation()
    first = simulation.apply_oracle(dict(text="Rain soaks the fields.", kind="weather", effects={"weather": "rain"}))["context_id"]
    second = simulation.apply_oracle(dict(text="A storm threatens the village.", kind="threat", effects={"weather": "storm"}))["context_id"]
    assert simulation.state["weather"] == "storm"
    simulation.dismiss_context(second)
    assert simulation.state["weather"] == "rain"
    simulation.dismiss_context(first)
    assert simulation.state["weather"] == "clear"
    assert simulation.state["baseline_weather"] == "clear"


def test_ending_older_weather_does_not_override_newer_weather():
    simulation = Simulation()
    first = simulation.apply_oracle(dict(text="A grey morning", effects={"weather": "overcast"}))["context_id"]
    simulation.apply_oracle(dict(text="A storm approaches", effects={"weather": "storm"}, duration_hours=.25))
    simulation.dismiss_context(first)
    assert simulation.state["weather"] == "storm"
    simulation.tick(15)
    assert simulation.state["weather"] == "clear"


def test_legacy_weather_save_has_sensible_end_behavior():
    simulation = Simulation()
    identity = simulation.apply_oracle(dict(text="A thunderstorm breaks out", kind="weather", effects={"weather": "storm"}))["context_id"]
    saved = simulation.snapshot()
    saved.pop("baseline_weather")
    saved["contexts"][0].pop("effects")
    saved["contexts"][0].pop("previous_weather")
    restored = Simulation.from_state(saved)
    assert restored.state["weather"] == "storm"
    restored.dismiss_context(identity)
    assert restored.state["weather"] == "clear"
