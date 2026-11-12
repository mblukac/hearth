"""Deterministic village state, movement and consequences; no network access.

Models propose decisions. This module is the authority on which decisions can
happen: a model cannot teleport, spend missing resources, bypass consent or
romantic eligibility, or invent a resident. Paths and pending interactions are
part of the saved state, so a save is resumable mid-walk.
"""

from collections import deque
from copy import deepcopy
import math
import random

from .data import ACTIONS, ACTION_BY_ID, LOCATIONS, MAP_HEIGHT, MAP_WIDTH, initial_villagers


ROMANCE = {a["id"] for a in ACTIONS if a["category"] == "romance"}
COMMITTED = {"partner", "married"}
MAX_EVENTS = 300
MAX_MEMORIES = 60
MAX_SCENARIO_HISTORY = 50
GESTATION_DAYS = 7  # Explicit game-time compression; calendar age remains normal.


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def distance(first, second):
    return math.hypot(first["x"] - second["x"], first["y"] - second["y"])


class Simulation:
    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.state = dict(
            version=1, seed=seed, tick=0, day=1, minute=8 * 60,
            total_minutes=8 * 60, weather="clear", baseline_weather="clear", season="early autumn",
            villagers=initial_villagers(self.rng), locations=deepcopy(LOCATIONS),
            events=[], contexts=[], scenario_history=[],
            world=dict(prosperity=62, tension=17, dread=8, food=95, treasury=160,
                       leadership="Edda Holm", civic_support=8, harvests=0, births=0),
            rules=dict(gestation_days=GESTATION_DAYS, adult_age=18, population_limit=40,
                       intimacy="abstract, consensual adults only", aging_days_per_year=365),
        )
        self._counter = 0
        self._rebuild_geometry()
        for villager in self.state["villagers"]:
            self._memory(villager, villager["backstory"], "identity", 7)
            self._memory(villager, f"My hope: {villager['goal']}", "hope", 6)
        self._event("arrival", "A new morning in Hearth. Twenty lives, one shared village.")

    @classmethod
    def from_state(cls, state):
        if not isinstance(state, dict) or not isinstance(state.get("villagers"), list):
            raise ValueError("This is not a village save.")
        simulation = cls.__new__(cls)
        simulation.state = deepcopy(state)
        simulation.rng = random.Random(state.get("seed", 42))
        saved_rng = simulation.state.pop("_rng_state", None)
        if saved_rng:
            def tuplify(value):
                return tuple(tuplify(item) for item in value) if isinstance(value, (list, tuple)) else value
            simulation.rng.setstate(tuplify(saved_rng))
        simulation._counter = int(simulation.state.pop("_event_counter", 1000 + state.get("tick", 0) * 100))
        simulation.state.setdefault("total_minutes", (state["day"] - 1) * 1440 + state["minute"])
        simulation.state.setdefault("rules", dict(gestation_days=GESTATION_DAYS, adult_age=18, population_limit=40))
        for villager in simulation.state["villagers"]:
            villager.setdefault("pending_action", None)
            villager.setdefault("cooldowns", {})
            villager.setdefault("wallet", 20)
            villager.setdefault("family", dict(parents=[], children=[], siblings=[]))
            villager.setdefault("pregnancy", None)
        map_changed = simulation._adopt_authored_locations()
        simulation._rebuild_geometry()
        if map_changed:
            simulation._settle_after_map_change()
        simulation._migrate_context_lifecycle()
        return simulation

    def _adopt_authored_locations(self):
        """The map is authored, not simulated: saves pick up corrected building positions."""
        authored = {place["id"]: place for place in LOCATIONS}
        saved = self.state.get("locations") or []
        extra = [place for place in saved if place.get("id") not in authored]
        changed = [place for place in saved if place.get("id") in authored] != LOCATIONS
        self.state["locations"] = deepcopy(LOCATIONS) + deepcopy(extra)
        return changed

    def _settle_after_map_change(self):
        """Step residents off moved walls and send walks toward moved doors."""
        for actor in self.state["villagers"]:
            point = (round(actor["x"]), round(actor["y"]))
            if not self._walkable(point):
                actor["x"], actor["y"] = self._nearest_walkable(point)
            pending = actor.get("pending_action")
            if not pending:
                continue
            if pending.get("target_id"):
                actor["destination"] = None  # _move replans toward the person.
                continue
            action = ACTION_BY_ID.get(pending["action"])
            if action and action.get("location"):
                destination = self._destination(actor, action)
                path = self._path(actor, destination) if destination else None
                if path is not None:
                    actor["destination"], actor["_path"] = destination, path

    def _nearest_walkable(self, start):
        visited, queue = {start}, deque([start])
        while queue:
            x, y = queue.popleft()
            for candidate in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if candidate in visited or not (0 <= candidate[0] < MAP_WIDTH and 0 <= candidate[1] < MAP_HEIGHT):
                    continue
                if self._walkable(candidate):
                    return candidate
                visited.add(candidate)
                queue.append(candidate)
        return start

    def _migrate_context_lifecycle(self):
        """Upgrade existing villages in place without resetting people or history."""
        history = self.state.setdefault("scenario_history", [])
        active = []
        for context in self.state.setdefault("contexts", []):
            context.setdefault("status", "active")
            context.setdefault("effects", {})
            context.setdefault("created_at", self.state["total_minutes"])
            context.setdefault("expires_at", context["created_at"] + context.get("duration_hours", 24) * 60)
            if context["status"] == "active":
                active.append(context)
            elif not any(ended["id"] == context["id"] for ended in history):
                history.insert(0, context)
        self.state["contexts"] = active
        self.state["scenario_history"] = history[:MAX_SCENARIO_HISTORY]
        weather_contexts = [context for context in active if context["effects"].get("weather")]
        if "baseline_weather" not in self.state:
            # Old saves retained only the resulting weather. Where a weather
            # scenario exists, associate it with that observed weather and use
            # the original world's clear skies as the best available baseline.
            if not weather_contexts:
                legacy_weather = next((context for context in active if context["kind"] == "weather"), None)
                if legacy_weather:
                    legacy_weather["effects"]["weather"] = self.state["weather"]
                    weather_contexts = [legacy_weather]
            self.state["baseline_weather"] = (weather_contexts[-1].get("previous_weather", "clear")
                                               if weather_contexts else self.state["weather"])
        active_ids = self._active_context_ids()
        if active_ids:
            for actor in self.state["villagers"]:
                # Legacy saves did not carry model context provenance. Treat pending
                # work conservatively when an active scenario is later withdrawn.
                for field in ("decision", "pending_action", "pending_narrative"):
                    if actor.get(field):
                        actor[field].setdefault("context_ids", list(active_ids))
                if actor.get("speech"):
                    actor.setdefault("speech_context_ids", list(active_ids))
                for memory in actor["memories"]:
                    if memory.get("context_id") in active_ids:
                        memory.setdefault("context_status", "active")
                        memory.setdefault("resolved", False)
        for context in list(self.state["contexts"]):
            if context["expires_at"] <= self.state["total_minutes"]:
                self._end_context(context, "expired", "Its scheduled duration has ended.")

    def _active_context_ids(self):
        return [context["id"] for context in self.state["contexts"]]

    def _refresh_scenario_weather(self):
        current = next((context["effects"]["weather"] for context in self.state["contexts"]
                        if context.get("effects", {}).get("weather")), None)
        self.state["weather"] = current or self.state.get("baseline_weather", "clear")

    def _rebuild_geometry(self):
        self._blocked = set()
        self._locations = {item["id"]: item for item in self.state["locations"]}
        for place in self.state["locations"]:
            for x in range(place["x"], place["x"] + place["w"]):
                for y in range(place["y"], place["y"] + place["h"]):
                    self._blocked.add((x, y))

    def snapshot(self):
        result = deepcopy(self.state)
        result["action_catalog"] = [
            {key: action[key] for key in ("id", "label", "category", "description", "requires_target")}
            for action in ACTIONS
        ]
        result["_rng_state"] = self.rng.getstate()
        result["_event_counter"] = self._counter
        # Internal paths are useful in saves, but large narrative payloads are not exposed twice.
        return result

    def villager(self, villager_id):
        for villager in self.state["villagers"]:
            if villager["id"] == villager_id:
                return villager
        raise ValueError(f"Unknown villager: {villager_id}")

    def _event(self, event_type, text, actor=None, target=None, **extra):
        self._counter += 1
        event = dict(id=f"e{self._counter}", day=self.state["day"], minute=self.state["minute"],
                     type=event_type, text=text, actor_id=actor["id"] if actor else None,
                     target_id=target["id"] if target else None, **extra)
        self.state["events"].insert(0, event)
        del self.state["events"][MAX_EVENTS:]
        return event

    def _memory(self, actor, text, emotion="neutral", importance=3, **extra):
        self._counter += 1
        memory = dict(id=f"m{self._counter}", day=self.state["day"], minute=self.state["minute"],
                      text=text, emotion=emotion, importance=importance, **extra)
        actor["memories"].insert(0, memory)
        del actor["memories"][MAX_MEMORIES:]
        return memory

    def _walkable(self, point):
        x, y = point
        return 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT and point not in self._blocked

    def _path(self, actor, destination):
        start = (round(actor["x"]), round(actor["y"]))
        goal = (round(destination["x"]), round(destination["y"]))
        if not self._walkable(goal):
            return None
        if start == goal:
            return []
        visited = {start: None}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for candidate in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if candidate in visited or not self._walkable(candidate):
                    continue
                visited[candidate] = (x, y)
                if candidate == goal:
                    result = [goal]
                    previous = visited[goal]
                    while previous != start:
                        result.append(previous)
                        previous = visited[previous]
                    return list(reversed(result))
                queue.append(candidate)
        return None

    def _target_destination(self, actor, target):
        tx, ty = round(target["x"]), round(target["y"])
        options = [(tx + dx, ty + dy) for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1), (0, 0))]
        options = [point for point in options if self._walkable(point)]
        if not options:
            return None
        x, y = min(options, key=lambda point: abs(actor["x"] - point[0]) + abs(actor["y"] - point[1]))
        return dict(x=x, y=y)

    def _destination(self, actor, action, target=None):
        if target:
            return self._target_destination(actor, target)
        place = action.get("location")
        if place in ("home", "workplace"):
            place = actor[place]
        if place == "river_bank":
            return dict(x=42, y=20)
        if place:
            return deepcopy(self._locations[place]["entrance"])
        if action["id"] in ("walk", "explore"):
            candidates = [(round(actor["x"]) + dx, round(actor["y"]) + dy)
                          for dx in range(-7, 8) for dy in range(-7, 8)
                          if 4 <= abs(dx) + abs(dy) <= 9]
            candidates = [point for point in candidates if self._walkable(point)]
            if candidates:
                x, y = self.rng.choice(candidates)
                return dict(x=x, y=y)
        return None

    def _nearby(self, actor):
        others = [other for other in self.state["villagers"] if other["id"] != actor["id"] and distance(actor, other) <= 14]
        return sorted(others, key=lambda other: (distance(actor, other), other["id"]))[:12]

    def _ancestors(self, actor):
        result = set()
        frontier = list(actor.get("family", {}).get("parents", []))
        for _ in range(4):
            next_level = []
            for parent_id in frontier:
                if parent_id in result:
                    continue
                result.add(parent_id)
                try:
                    next_level.extend(self.villager(parent_id).get("family", {}).get("parents", []))
                except ValueError:
                    pass
            frontier = next_level
        return result

    def _related(self, actor, target):
        first_family, second_family = actor.get("family", {}), target.get("family", {})
        if target["id"] in sum((first_family.get(key, []) for key in ("parents", "children", "siblings")), []):
            return True
        if actor["id"] in sum((second_family.get(key, []) for key in ("parents", "children", "siblings")), []):
            return True
        first_ancestors, second_ancestors = self._ancestors(actor), self._ancestors(target)
        if actor["id"] in second_ancestors or target["id"] in first_ancestors or first_ancestors & second_ancestors:
            return True
        # Authored siblings can have unknown parents; include their descendants.
        first_line = first_ancestors | {actor["id"]}
        second_line = second_ancestors | {target["id"]}
        for identity in first_line:
            try:
                if set(self.villager(identity)["family"].get("siblings", [])) & second_line:
                    return True
            except ValueError:
                pass
        return False

    def _attracted(self, actor, target):
        orientation = actor["demographics"].get("orientation", "pansexual")
        if orientation in ("bisexual", "pansexual", "asexual"):
            return True
        if orientation == "lesbian":
            return target["gender"] == "woman"
        if orientation == "gay":
            return target["gender"] == actor["gender"]
        if orientation == "heterosexual":
            return (actor["gender"], target["gender"]) in (("man", "woman"), ("woman", "man"))
        return False

    def _relation(self, actor, target):
        return actor["relationships"].setdefault(target["id"], dict(affinity=10, trust=10, romance=0, status="neighbor"))

    def _romance_eligible(self, actor, target, action_id):
        if actor["age"] < 18 or target["age"] < 18 or self._related(actor, target):
            return False
        first, second = self._relation(actor, target), self._relation(target, actor)
        if action_id == "break_up":
            return first["status"] in COMMITTED and second["status"] in COMMITTED
        if not self._attracted(actor, target) or not self._attracted(target, actor):
            return False
        for person, other in ((actor, target), (target, actor)):
            if any(key != other["id"] and relation["status"] in COMMITTED for key, relation in person["relationships"].items()):
                return False
        minimums = {
            "flirt": (15, 10, 0), "court": (25, 20, 12), "hold_hands": (30, 25, 20),
            "kiss": (40, 35, 30), "form_partnership": (55, 45, 50),
            "marry": (75, 72, 70), "intimacy": (60, 60, 60),
            "discuss_family": (55, 55, 45), "try_for_child": (65, 60, 55),
        }
        minimum = minimums.get(action_id, (0, 0, 0))
        if any(relation[key] < limit for relation in (first, second)
               for key, limit in zip(("affinity", "trust", "romance"), minimum)):
            return False
        if action_id == "form_partnership" and (first["status"] in COMMITTED or second["status"] in COMMITTED):
            return False
        if action_id in ("marry", "intimacy", "discuss_family", "try_for_child") and not (
                first["status"] in COMMITTED and second["status"] in COMMITTED):
            return False
        if action_id == "marry" and (first["status"] == "married" or second["status"] == "married"):
            return False
        if action_id in ("intimacy", "try_for_child"):
            if any(person["needs"]["safety"] < 30 or person["needs"]["energy"] < 25 for person in (actor, target)):
                return False
            if any(person["demographics"].get("intimacy_preference") == "declines" for person in (actor, target)):
                return False  # This authored resident has opted out of sexual intimacy.
        if action_id == "try_for_child":
            if len(self.state["villagers"]) >= self.state["rules"]["population_limit"]:
                return False
            gestating, contributing = self._reproductive_pair(actor, target)
            if not gestating or not contributing or gestating.get("pregnancy") or gestating["age"] >= 50:
                return False
            if any(person.get("family_plan", {}).get("partner_id") != other["id"] or
                   person.get("family_plan", {}).get("expires_at", 0) <= self.state["total_minutes"]
                   for person, other in ((actor, target), (target, actor))):
                return False
        return True

    @staticmethod
    def _reproductive_pair(first, second):
        capacities = {person["demographics"].get("reproductive_capacity"): person for person in (first, second)}
        return capacities.get("can_gestate"), capacities.get("can_contribute_sperm")

    def _eligible(self, actor, action, target=None, *, cooldown=True):
        now = self.state["total_minutes"]
        if cooldown and actor.get("cooldowns", {}).get(action["id"], 0) > now:
            return False
        if actor.get("busy_until", 0) > now:
            return False
        if actor["age"] < 18 and action["id"] not in {"eat", "sleep", "rest", "wash", "go_home", "walk", "seek_shelter", "talk", "greet", "listen", "joke", "study", "think", "observe", "paint"}:
            return False
        if actor["age"] < 2 and action["id"] not in {"sleep", "rest", "observe"}:
            return False
        if actor["wallet"] < action.get("cost", 0):
            return False
        for key, change in action.get("world", {}).items():
            if key in ("food", "treasury") and change < 0 and self.state["world"].get(key, 0) < -change:
                return False
        key = action["id"]
        if key in ("eat", "cook") and actor["needs"]["hunger"] > 92:
            return False
        if key in ("sleep", "rest") and actor["needs"]["energy"] > 92:
            return False
        if key == "revolt" and (self.state["world"]["tension"] < 65 or self.state["world"].get("civic_support", 0) < 35):
            return False
        if key in ("protest", "strike") and self.state["world"]["tension"] < 25:
            return False
        if action["requires_target"]:
            if not target or actor["id"] == target["id"]:
                return False
            if target.get("busy_until", 0) > now:
                return False
            relation = self._relation(actor, target)
            if relation["trust"] < action.get("min_trust", -100) or relation["affinity"] < action.get("min_affinity", -100):
                return False
            if key in ROMANCE and not self._romance_eligible(actor, target, key):
                return False
            if key in ("fight", "insult", "argue", "confront") and target["age"] < 18:
                return False
            if key == "fight" and relation["affinity"] > 10 and self.state["world"]["tension"] < 60:
                return False
            if key == "care_for_child" and target["age"] >= 18:
                return False
            if key == "make_friend" and relation["status"] in ("friend", "family", "partner", "married"):
                return False
            if key == "share_food" and target["needs"]["hunger"] > 90:
                return False
        elif target:
            return False
        return True

    def available_actions(self, villager_id):
        actor = self.villager(villager_id)
        if actor.get("pending_action") or actor.get("busy_until", 0) > self.state["total_minutes"]:
            return []
        nearby = self._nearby(actor)
        options = []
        for action in ACTIONS:
            valid_targets = []
            if action["requires_target"]:
                valid_targets = [target["id"] for target in nearby if self._eligible(actor, action, target)]
                if not valid_targets:
                    continue
            elif not self._eligible(actor, action):
                continue
            descriptor = {key: action[key] for key in ("id", "label", "category", "description", "requires_target")}
            descriptor["eligible_targets"] = valid_targets
            descriptor["target_ids"] = valid_targets
            options.append(descriptor)
        return options

    def decision_context(self, villager_id):
        actor = self.villager(villager_id)
        nearby = []
        for other in self._nearby(actor):
            nearby.append(dict(id=other["id"], name=other["name"], age=other["age"], gender=other["gender"],
                               occupation=other["occupation"], mood=other["mood"], x=other["x"], y=other["y"],
                               action=other["action"], action_label=other["action_label"], speech=other["speech"],
                               distance=round(distance(actor, other), 2), relationship=deepcopy(self._relation(actor, other)),
                               needs=deepcopy(other["needs"])))
        actor_copy = deepcopy(actor)
        actor_copy["memories"] = actor_copy["memories"][:12]
        actor_copy.pop("_path", None)
        actor_copy.pop("pending_narrative", None)
        return dict(actor=actor_copy, nearby=nearby, nearby_villagers=nearby,
                    world=deepcopy(self.state["world"]), contexts=deepcopy(self.state["contexts"]),
                    scenario_history=deepcopy(self.state["scenario_history"][:6]),
                    locations=deepcopy(self.state["locations"]), seed=self.state["seed"],
                    clock=dict(day=self.state["day"], minute=self.state["minute"],
                               total_minutes=self.state["total_minutes"], tick=self.state["tick"],
                               weather=self.state["weather"], season=self.state["season"]))

    def apply_decision(self, villager_id, decision):
        actor = self.villager(villager_id)
        if not isinstance(decision, dict):
            raise ValueError("A decision must be an object.")
        if actor.get("pending_action"):
            raise ValueError("This villager is still on the way to a previous action.")
        action = ACTION_BY_ID.get(decision.get("action"))
        if not action:
            raise ValueError("The proposed action is not in the village action catalog.")
        target = self.villager(decision["target_id"]) if decision.get("target_id") else None
        if not self._eligible(actor, action, target):
            raise ValueError(f"{actor['name']} cannot currently {action['label'].lower()} with this target or these resources.")
        context_ids = self._narrative_context_ids(decision.get("context_ids", self._active_context_ids()))
        if set(context_ids) - set(self._active_context_ids()):
            raise ValueError("This decision refers to a scenario that is no longer active.")
        actor["decision"] = deepcopy(decision)
        actor["decision"]["context_ids"] = context_ids
        actor["target_id"] = target["id"] if target else None
        actor["speech"] = ""
        actor.pop("pending_narrative", None)
        destination = self._destination(actor, action, target)
        adjacent = target is not None and distance(actor, target) <= 1.55
        if destination and not adjacent and distance(actor, destination) > .1:
            path = self._path(actor, destination)
            if path is None:
                raise ValueError("There is no walkable route to that action.")
            actor["pending_action"] = dict(action=action["id"], target_id=target["id"] if target else None,
                                            started_at=self.state["total_minutes"], decision=deepcopy(actor["decision"]),
                                            context_ids=list(context_ids))
            actor["destination"] = destination
            actor["_path"] = path
            actor["action"] = "walk"
            actor["action_label"] = f"On the way: {action['label'].lower()}"
            target_name = target["name"] if target else self._place_name(actor, action)
            return self._event("movement", f"{actor['name']} heads toward {target_name} to {action['label'].lower()}.", actor, target,
                               action=action["id"], source=decision.get("source", "demo"))
        return self._resolve(actor, action, target)

    def _place_name(self, actor, action):
        place = action.get("location")
        if place in ("home", "workplace"):
            place = actor[place]
        return self._locations[place]["name"] if place in self._locations else "the village lanes"

    def _change_needs(self, actor, changes):
        for key, change in changes.items():
            actor["needs"][key] = round(clamp(actor["needs"].get(key, 50) + change), 2)

    def _change_world(self, changes):
        for key, change in changes.items():
            if key == "weather":
                self.state["weather"] = str(change)
                continue
            if key not in self.state["world"] or not isinstance(change, (int, float)) or not math.isfinite(change):
                continue
            result = self.state["world"][key] + change
            # Retain sub-cent changes: live ticks ease tension by only 0.004.
            # The interface rounds for display; stored values must accumulate.
            self.state["world"][key] = clamp(result) if key in ("prosperity", "tension", "dread", "civic_support") else max(0, result)

    def _resolve(self, actor, action, target):
        key, now = action["id"], self.state["total_minutes"]
        if target and distance(actor, target) > 1.55:
            raise ValueError("Villagers must meet before interacting.")
        if not self._eligible(actor, action, target):
            return self._interrupt(actor, "The circumstances changed before the action could happen.")
        self._change_needs(actor, action["needs"])
        self._change_world(action["world"])
        actor["wallet"] = round(actor["wallet"] - action["cost"] + action["income"], 2)
        actor["action"], actor["action_label"] = key, action["label"]
        actor["destination"], actor["pending_action"] = None, None
        actor.pop("_path", None)
        actor["last_action_at"] = now
        actor["cooldowns"][key] = now + action["cooldown"]
        actor["speech"] = ""
        if action.get("duration"):
            actor["busy_until"] = now + action["duration"]
        text = f"{actor['name']} {self._verb(key)}"
        if target:
            text += f" with {target['name']}"
            self._change_needs(target, action.get("target_needs", {"social": 5}))
            for person, other in ((actor, target), (target, actor)):
                relation = self._relation(person, other)
                for trait, change in action["bond"].items():
                    relation[trait] = round(clamp(relation[trait] + change, -100 if trait == "affinity" else 0), 2)
                if relation["status"] not in COMMITTED and relation["status"] != "family":
                    if relation["romance"] >= 15:
                        relation["status"] = "crush"
                    elif relation["affinity"] < 0:
                        relation["status"] = "rival"
                    elif relation["affinity"] >= 45 and relation["trust"] >= 35:
                        relation["status"] = "friend"
                # Mutual interactions also impose a short pair-side cooldown.
                if key in ROMANCE:
                    person["cooldowns"][key] = now + action["cooldown"]
        text += "."
        emotion = "connection" if target else "purpose"
        importance = 3
        if key == "work":
            if actor["occupation"] in ("farmer", "farmhand", "gardener", "miller", "baker", "fisher"):
                self._change_world({"food": 4})
            elif actor["occupation"] in ("physician", "herbalist", "warden"):
                self._change_world({"dread": -.4})
            elif actor["occupation"] in ("mayor", "accountant", "merchant"):
                self._change_world({"treasury": 2})
        elif key == "harvest":
            self.state["world"]["harvests"] += 1
        elif key == "gossip":
            memories = [memory for memory in actor["memories"] if memory.get("emotion") not in ("identity", "hope")]
            if memories:
                remembered = self.rng.choice(memories[:8])
                remembered_text = remembered.get("resolution", remembered["text"]) if remembered.get("resolved") else remembered["text"]
                rumor = f"{actor['name']} says they heard: {remembered_text[:220]}"
                provenance = dict(context_ids=list(remembered.get("context_ids", [])),
                                  resolved=bool(remembered.get("resolved", False)))
                if remembered.get("context_id"):
                    provenance["context_id"] = remembered["context_id"]
                if remembered.get("resolved"):
                    provenance.update(context_status=remembered.get("context_status"),
                                      resolution=remembered.get("resolution", remembered_text))
                target["rumors"] = ([dict(text=rumor, source_id=actor["id"], verified=False,
                                          day=self.state["day"], **provenance)] + target.get("rumors", []))[:12]
                text = f"{actor['name']} passes an unverified story to {target['name']}: {remembered_text[:180]}"
                self._memory(target, rumor, "curiosity", 5, verified=False, source_id=actor["id"], **provenance)
            else:
                text = f"{actor['name']} and {target['name']} wonder what is changing in the village; neither claims to know."
        elif key in ("form_partnership", "marry"):
            status = "partner" if key == "form_partnership" else "married"
            for person, other in ((actor, target), (target, actor)):
                self._relation(person, other)["status"] = status
                person["partner_id"] = other["id"]
            text = f"{actor['name']} and {target['name']} {'agree to become partners' if status == 'partner' else 'marry in a small village celebration'}."
            importance, emotion = 10, "love"
        elif key == "intimacy":
            text = f"{actor['name']} and {target['name']} choose to share private intimacy. Their time together stays private."
            importance, emotion = 7, "love"
        elif key == "discuss_family":
            for person, other in ((actor, target), (target, actor)):
                person["family_plan"] = dict(partner_id=other["id"], expires_at=now + 7 * 1440, willing=True)
            text = f"{actor['name']} and {target['name']} agree they would welcome a child together."
            importance, emotion = 8, "hope"
        elif key == "try_for_child":
            gestating, contributing = self._reproductive_pair(actor, target)
            if self.rng.random() < .32:
                gestating["pregnancy"] = dict(other_parent_id=contributing["id"], conceived_at=now,
                                                due_at=now + GESTATION_DAYS * 1440,
                                                gestation_days=GESTATION_DAYS, progress=0)
                text = f"{actor['name']} and {target['name']} are expecting a child. Pregnancy lasts {GESTATION_DAYS} days in village game time."
                importance, emotion = 10, "hope"
            else:
                text = f"{actor['name']} and {target['name']} privately try for a child; no pregnancy begins this time."
                importance, emotion = 6, "hope"
        elif key == "break_up":
            for person, other in ((actor, target), (target, actor)):
                self._relation(person, other)["status"] = "former_partner"
                person.pop("partner_id", None)
                person.pop("family_plan", None)
            text = f"{actor['name']} and {target['name']} end their partnership."
            importance, emotion = 9, "sadness"
        elif key == "make_friend":
            for person, other in ((actor, target), (target, actor)):
                self._relation(person, other)["status"] = "friend"
        elif key in ("fight", "insult", "argue", "confront"):
            emotion, importance = "anger", 7 if key == "fight" else 5
            if key == "fight":
                actor["injury"], target["injury"] = "bruised", "bruised"
                text = f"{actor['name']} and {target['name']} have a brief scuffle. Both leave bruised and shaken."
        elif key == "heal":
            target.pop("injury", None)
        elif key in ("protest", "organize", "strike"):
            self._change_world({"civic_support": 5 if key == "organize" else 3})
        elif key in ("petition", "negotiate", "vote"):
            self._change_world({"civic_support": -1})
        elif key == "revolt":
            self.state["world"]["leadership"] = f"Assembly led by {actor['name']}"
            self._change_world({"civic_support": -25})
            text = f"{actor['name']} leads an organized revolt. The old leadership yields to a new assembly; the village must rebuild trust."
            emotion, importance = "defiance", 10
            for witness in self.state["villagers"]:
                if witness is not actor:
                    self._memory(witness, text, "uncertainty", 9)
        if key in ("organize_feast", "perform", "clean_up", "guard"):
            for witness in self.state["villagers"]:
                if witness is not actor and distance(actor, witness) < 9:
                    self._change_needs(witness, {"social": 4, "safety": 3})
        source = actor.get("decision", {}).get("source", "demo") if actor.get("decision") else "demo"
        event = self._event(action["category"], text, actor, target, action=key, source=source)
        context_ids = (actor.get("decision") or {}).get("context_ids", [])
        self._memory(actor, text, emotion, importance, event_id=event["id"], context_ids=list(context_ids))
        if target:
            self._memory(target, text, emotion, importance, event_id=event["id"], context_ids=list(context_ids))
        self._update_mood(actor)
        if target:
            self._update_mood(target)
        if actor.get("pending_narrative"):
            narrative = actor.pop("pending_narrative")
            self._publish_narrative(actor, narrative)
        return event

    @staticmethod
    def _verb(key):
        special = {
            "eat": "enjoys a filling meal", "cook": "cooks a meal at home", "sleep": "settles down to sleep",
            "rest": "takes a well-earned breather", "go_home": "arrives home", "work": "finishes a shift of useful work",
            "walk": "takes a quiet walk", "explore": "explores a new corner of the lanes",
            "think": "takes a moment to think things through", "talk": "shares a conversation", "greet": "exchanges a greeting",
            "flirt": "shares a flirtatious moment", "court": "spends affectionate time", "hold_hands": "shares a hand-held moment",
            "kiss": "shares a consensual kiss", "care_for_child": "spends time caring for a child",
            "warn": "shares a warning about a perceived danger", "evacuate": "makes a plan for reaching shelter",
            "pray": "takes time for a quiet personal ritual", "grieve": "makes room for a difficult feeling",
        }
        return special.get(key, f"takes time to {ACTION_BY_ID[key]['label'].lower()}")

    def _interrupt(self, actor, reason):
        pending = actor.get("pending_action") or {}
        actor["pending_action"], actor["destination"] = None, None
        actor.pop("_path", None)
        actor.pop("pending_narrative", None)
        actor["action"], actor["action_label"] = "idle", "Reconsidering the plan"
        actor["thought"] = reason
        return self._event("interrupted", f"{actor['name']} changes plans. {reason}", actor, action=pending.get("action"))

    def _move(self, actor, minutes):
        pending = actor.get("pending_action")
        if not pending:
            return
        action = ACTION_BY_ID.get(pending["action"])
        if not action:
            self._interrupt(actor, "The planned action no longer exists.")
            return
        try:
            target = self.villager(pending["target_id"]) if pending.get("target_id") else None
        except ValueError:
            self._interrupt(actor, "The other person is no longer here.")
            return
        if self.state["total_minutes"] - pending["started_at"] > 240:
            self._interrupt(actor, "Too much time passed to carry out the original plan.")
            return
        if target and distance(actor, target) <= 1.55:
            self._resolve(actor, action, target)
            return
        if target and (not actor.get("destination") or distance(actor["destination"], target) > 1.6):
            destination = self._target_destination(actor, target)
            path = self._path(actor, destination) if destination else None
            if path is None:
                self._interrupt(actor, "A route to the other person could not be found.")
                return
            actor["destination"], actor["_path"] = destination, path
        budget = minutes * (.36 if actor["age"] < 18 else .48)
        path = actor.get("_path", [])
        while budget > 0 and path:
            point = dict(x=path[0][0], y=path[0][1])
            remaining = distance(actor, point)
            if remaining <= budget + 1e-8:
                actor["x"], actor["y"] = point["x"], point["y"]
                budget -= remaining
                path.pop(0)
                if target and distance(actor, target) <= 1.55:
                    break
            else:
                ratio = budget / remaining
                actor["x"] += (point["x"] - actor["x"]) * ratio
                actor["y"] += (point["y"] - actor["y"]) * ratio
                budget = 0
        if target:
            if distance(actor, target) <= 1.55:
                self._resolve(actor, action, target)
            elif not path:
                actor["destination"] = None  # Replan toward a moving target next tick.
        elif not path:
            self._resolve(actor, action, None)

    def _update_mood(self, actor):
        needs = actor["needs"]
        if actor.get("injury"):
            actor["mood"] = "shaken"
        elif needs["hunger"] < 20:
            actor["mood"] = "hungry"
        elif needs["energy"] < 20:
            actor["mood"] = "exhausted"
        elif needs["safety"] < 30 or self.state["world"]["dread"] > 65:
            actor["mood"] = "anxious"
        elif needs["social"] < 25:
            actor["mood"] = "lonely"
        elif actor["action"] in ROMANCE and actor["action"] != "break_up":
            actor["mood"] = "affectionate"
        elif self.state["world"]["tension"] > 65:
            actor["mood"] = "restless"
        elif min(needs.values()) > 65:
            actor["mood"] = "content"
        else:
            actor["mood"] = "thoughtful"

    def tick(self, minutes=5):
        if not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or minutes <= 0 or minutes > 1440:
            raise ValueError("Advance the village by between 0 and 1,440 minutes.")
        # Small steps prevent skipped births, context expiries or routes when fast-forwarding.
        remaining = float(minutes)
        while remaining > 0:
            step = min(remaining, 5)
            remaining -= step
            self.state["tick"] += 1
            self.state["total_minutes"] += step
            self.state["day"] = int(self.state["total_minutes"] // 1440) + 1
            self.state["minute"] = round(self.state["total_minutes"] % 1440, 2)
            now = self.state["total_minutes"]
            expired = [context for context in self.state["contexts"] if context["expires_at"] <= now]
            for context in expired:
                self._end_context(context, "expired", "Its scheduled duration has ended.")
            threat_pressure = sum(context["intensity"] / 100 for context in self.state["contexts"]
                                  if context["kind"] in ("threat", "scarcity"))
            atmosphere_pressure = sum(context["intensity"] / 100 for context in self.state["contexts"]
                                      if context["kind"] == "atmosphere")
            self._change_world({"dread": step * (-.003 + .008 * threat_pressure + .002 * atmosphere_pressure),
                                "tension": step * (-.002 + .003 * threat_pressure)})
            for actor in list(self.state["villagers"]):
                actor["age"] = max(0, int((self.state["day"] - actor.get("birth_day", 1 - actor["age"] * 365)) // 365))
                sleeping = actor.get("busy_until", 0) > now and actor["action"] == "sleep"
                self._change_needs(actor, {"energy": step * (.08 if sleeping else -.027),
                                          "hunger": -step * .035,
                                          "social": -step * (.012 + actor["traits"]["extraversion"] * .00012),
                                          "safety": step * (.006 - .018 * threat_pressure - .004 * atmosphere_pressure)})
                if self.state["world"]["food"] < 10 and actor["needs"]["hunger"] < 40:
                    self._change_needs(actor, {"safety": -step * .04})
                    self._change_world({"tension": step * .006})
                if actor.get("speech_until", 0) <= now:
                    actor["speech"] = ""
                actor["cooldowns"] = {key: until for key, until in actor.get("cooldowns", {}).items() if until > now}
                self._move(actor, step)
                pregnancy = actor.get("pregnancy")
                if pregnancy:
                    pregnancy["progress"] = clamp((now - pregnancy["conceived_at"]) / (pregnancy["due_at"] - pregnancy["conceived_at"]) * 100)
                    if pregnancy["due_at"] <= now:
                        self._birth(actor, pregnancy)
                self._update_mood(actor)

    def apply_narrative(self, villager_id, narrative):
        actor = self.villager(villager_id)
        if not isinstance(narrative, dict):
            raise ValueError("A narrative must be an object.")
        context_ids = self._narrative_context_ids(narrative.get(
            "context_ids", (actor.get("decision") or {}).get("context_ids", self._active_context_ids())))
        if set(context_ids) - set(self._active_context_ids()):
            return  # A reply from a withdrawn scenario is stale, even after a new decision.
        if "context_ids" not in narrative and (actor.get("decision") or {}).get("invalidated_context_ids"):
            return
        clean = dict(thought=str(narrative.get("thought", ""))[:1600],
                     speech=str(narrative.get("speech", ""))[:500], source=narrative.get("source", "demo"),
                     context_ids=context_ids)
        if actor.get("pending_action"):
            actor["pending_narrative"] = clean
            if clean["thought"]:
                actor["thought"] = clean["thought"]
                actor["thought_source"] = clean["source"]
                actor["thought_context_ids"] = list(context_ids)
            return
        self._publish_narrative(actor, clean)

    def _publish_narrative(self, actor, narrative):
        context_ids = self._narrative_context_ids(narrative.get("context_ids", []))
        if set(context_ids) - set(self._active_context_ids()):
            return
        if narrative.get("thought"):
            actor["thought"] = narrative["thought"]
            actor["thought_source"] = narrative.get("source", "demo")
            actor["thought_context_ids"] = list(context_ids)
        if narrative.get("speech"):
            actor["speech"] = narrative["speech"]
            actor["speech_until"] = self.state["total_minutes"] + 40
            actor["speech_source"] = narrative.get("source", "demo")
            actor["speech_context_ids"] = list(context_ids)
            target = None
            if actor.get("target_id"):
                try:
                    target = self.villager(actor["target_id"])
                except ValueError:
                    pass
            if target and distance(actor, target) > 1.55:
                actor["speech"] = ""
                return
            spoken_text = f"{actor['name']}: “{actor['speech']}”"
            spoken_event = self._event("speech", spoken_text, actor, target,
                                       source=narrative.get("source", "demo"))
            listeners = [target] if target else [person for person in self.state["villagers"]
                                               if person is not actor and distance(actor, person) <= 3]
            for listener in [actor, *listeners]:
                self._memory(listener, spoken_text, "conversation", 5,
                             event_id=spoken_event["id"], source=narrative.get("source", "demo"),
                             speaker_id=actor["id"], context_ids=list(context_ids))

    @staticmethod
    def _narrative_context_ids(value):
        if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
            raise ValueError("Scenario references must be a list of scenario IDs.")
        return list(dict.fromkeys(value))

    @staticmethod
    def _prepare_oracle(event):
        """Validate completely before a replacement retires the previous context."""
        if not isinstance(event, dict) or not isinstance(event.get("text"), str) or not event["text"].strip():
            raise ValueError("An oracle event needs a description.")
        text = event["text"].strip()[:1500]
        kind = event.get("kind", "atmosphere")
        if not isinstance(kind, str) or kind not in {"atmosphere", "threat", "abundance", "scarcity", "celebration", "politics", "weather"}:
            kind = "atmosphere"
        try:
            intensity = float(event.get("intensity", 60))
            duration = float(event.get("duration_hours", 24))
        except (TypeError, ValueError):
            raise ValueError("Oracle intensity and duration must be finite numbers.") from None
        if not math.isfinite(intensity) or not math.isfinite(duration):
            raise ValueError("Oracle intensity and duration must be finite numbers.")
        intensity, duration = clamp(intensity), clamp(duration, .25, 720)
        effects = event.get("effects", {})
        if not isinstance(effects, dict):
            raise ValueError("Oracle effects must be an object.")
        clean_effects = {}
        for key, value in effects.items():
            if key not in {"dread", "tension", "prosperity", "food", "weather"}:
                continue
            if key == "weather":
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("The weather effect must describe the new weather.")
                clean_effects[key] = value.strip()[:120]
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("Oracle effects must contain finite numbers.")
                clean_effects[key] = value
        return dict(text=text, kind=kind, intensity=intensity, duration_hours=duration,
                    effects=clean_effects, source=str(event.get("source", "oracle")))

    def _new_context_id(self):
        used = {context["id"] for context in self.state["contexts"] + self.state["scenario_history"]}
        while True:
            self._counter += 1
            candidate = f"oracle-{self._counter}"
            if candidate not in used:
                return candidate

    def apply_oracle(self, event):
        return self._apply_prepared_oracle(self._prepare_oracle(event))

    def _apply_prepared_oracle(self, event, context_id=None):
        text, kind, intensity = event["text"], event["kind"], event["intensity"]
        duration = event["duration_hours"]
        context = dict(id=context_id or self._new_context_id(), text=text, kind=kind, intensity=intensity,
                       created_at=self.state["total_minutes"], expires_at=self.state["total_minutes"] + duration * 60,
                       duration_hours=duration, source=event["source"], effects=deepcopy(event["effects"]), status="active")
        if "weather" in event["effects"]:
            context["previous_weather"] = self.state["weather"]
        while len(self.state["contexts"]) >= 20:
            self._end_context(self.state["contexts"][-1], "expired", "Newer scenarios have taken its place.")
        self.state["contexts"].insert(0, context)
        self._change_world(event["effects"])
        feeling = "uncertainty" if kind in ("atmosphere", "threat", "scarcity", "politics") else "hope"
        for actor in self.state["villagers"]:
            sensitivity = .65 + actor["traits"]["neuroticism"] / 140
            impact = intensity * .2 * sensitivity
            if kind in ("threat", "scarcity", "atmosphere"):
                self._change_needs(actor, {"safety": -impact})
            elif kind in ("abundance", "celebration"):
                self._change_needs(actor, {"safety": impact * .6, "social": impact * .5})
            actor["thought"] = f"Something has changed: {text} I need to consider what this means for {actor['goal'].lower()}"
            actor["thought_source"] = "oracle-context"
            actor["thought_context_ids"] = [context["id"]]
            self._memory(actor, f"A change felt throughout the village: {text}", feeling, max(4, round(intensity / 10)),
                         context_id=context["id"], context_status="active", resolved=False)
            self._update_mood(actor)
        return self._event("oracle", text, source=event["source"], kind=kind, intensity=intensity, context_id=context["id"])

    def _find_context(self, context_id):
        if not isinstance(context_id, str):
            raise ValueError("A scenario ID is required.")
        for context in self.state["contexts"]:
            if context["id"] == context_id:
                return context
        raise ValueError("That scenario is unknown or is no longer active.")

    @staticmethod
    def _resolution_reason(reason):
        if not isinstance(reason, str):
            raise ValueError("A scenario resolution must be text.")
        return reason.strip()[:1000]

    def dismiss_context(self, context_id, reason=""):
        context = self._find_context(context_id)
        reason = self._resolution_reason(reason) or "The oracle has withdrawn this scenario."
        return self._end_context(context, "dismissed", reason)

    def replace_context(self, context_id, event):
        context = self._find_context(context_id)
        prepared = self._prepare_oracle(event)
        # All input validation precedes any mutation. Keep rollback local as a
        # safeguard against unexpected state corruption in an imported old save.
        previous_state, previous_counter = deepcopy(self.state), self._counter
        try:
            replacement_id = self._new_context_id()
            self._end_context(context, "replaced", "The oracle replaced this scenario with an updated account.",
                              replaced_by=replacement_id)
            return self._apply_prepared_oracle(prepared, context_id=replacement_id)
        except Exception:
            self.state, self._counter = previous_state, previous_counter
            raise

    def _end_context(self, context, status, reason, *, replaced_by=None):
        """Retire the influence, preserve its history, and tell every resident."""
        identity, now = context["id"], self.state["total_minutes"]
        self.state["contexts"] = [active for active in self.state["contexts"] if active["id"] != identity]
        if context.get("effects", {}).get("weather"):
            self._refresh_scenario_weather()
        if status == "replaced":
            resolution = "The previous scenario has been superseded. Its old description is no longer the current situation."
        elif context["kind"] == "threat":
            resolution = "The reported threat has passed and is no longer active. The village can stop preparing for that warning."
        elif status == "expired":
            resolution = "This scenario has ended. Its influence is no longer part of the current situation."
        else:
            resolution = "This scenario has been withdrawn. It is no longer part of the current situation."
        if reason:
            resolution += f" {reason}"
        archived = deepcopy(context)
        archived.update(status=status, ended_at=now, resolution=resolution, reason=reason)
        if replaced_by:
            archived["replaced_by"] = replaced_by
        self.state["scenario_history"].insert(0, archived)
        del self.state["scenario_history"][MAX_SCENARIO_HISTORY:]

        # Relief is a bounded psychological consequence, not a rollback of world
        # history: consumed food, completed work, injuries and other events stay.
        lingering = sum(active["intensity"] / 100 for active in self.state["contexts"]
                        if active["kind"] in ("threat", "scarcity", "atmosphere"))
        relief_scale = 1 / (1 + lingering)
        relieved = context["kind"] in ("threat", "scarcity", "atmosphere", "politics")
        if relieved:
            self._change_world({"dread": -min(30, context["intensity"] * .35) * relief_scale,
                                "tension": -min(12, context["intensity"] * .1) * relief_scale})
        for actor in self.state["villagers"]:
            decision = actor.get("decision") or {}
            pending = actor.get("pending_action") or {}
            pending_narrative = actor.get("pending_narrative") or {}
            if identity in pending.get("context_ids", pending.get("decision", {}).get("context_ids", [])):
                self._interrupt(actor, "The scenario behind this plan has ended, so I need to reconsider it.")
                actor["target_id"] = None
            if identity in pending_narrative.get("context_ids", []):
                actor.pop("pending_narrative", None)
            if identity in decision.get("context_ids", []):
                invalidated = decision.setdefault("invalidated_context_ids", [])
                if identity not in invalidated:
                    invalidated.append(identity)
            if identity in actor.get("speech_context_ids", []):
                actor["speech"], actor["speech_until"] = "", now
                actor["speech_context_ids"] = []
            for memory in actor["memories"]:
                if memory.get("context_id") == identity or identity in memory.get("context_ids", []):
                    memory.update(resolved=True, context_status=status, ended_at=now, resolution=resolution)
                    resolved_ids = memory.setdefault("resolved_context_ids", [])
                    if identity not in resolved_ids:
                        resolved_ids.append(identity)
            for rumor in actor.get("rumors", []):
                if rumor.get("context_id") == identity or identity in rumor.get("context_ids", []):
                    rumor.update(resolved=True, context_status=status, ended_at=now, resolution=resolution)
            if relieved:
                sensitivity = .65 + actor["traits"]["neuroticism"] / 140
                self._change_needs(actor, {"safety": min(18, context["intensity"] * .15 * sensitivity) * relief_scale})
            actor["thought"] = resolution
            if self.state["contexts"]:
                actor["thought"] += " Other active circumstances still need my attention."
            actor["thought_source"] = "oracle-resolution"
            actor["thought_context_ids"] = self._active_context_ids()
            self._memory(actor, f"Scenario resolved: “{context['text']}” {resolution}",
                         "relief" if relieved else "reflection", 8, context_id=identity,
                         context_status=status, resolved=True, ended_at=now, resolution=resolution)
            self._update_mood(actor)
        return self._event("context_resolved", f"“{context['text']}” {resolution}", context_id=identity,
                           status=status, reason=reason, resolution=resolution, replaced_by=replaced_by,
                           source="oracle" if status != "expired" else "simulation")

    def _birth(self, parent, pregnancy):
        other_parent = self.villager(pregnancy["other_parent_id"])
        if len(self.state["villagers"]) >= self.state["rules"]["population_limit"]:
            # A pregnancy already underway still resolves; the cap only prevents new conceptions.
            pass
        number = max(int(person["id"][1:]) for person in self.state["villagers"]) + 1
        child_id = f"v{number:02d}"
        given_name = self.rng.choice(["Rowan", "Robin", "Alex", "River", "Sam", "Ash", "Kit", "Wren"])
        existing = {person["name"].split()[0] for person in self.state["villagers"]}
        if given_name in existing:
            given_name += str(number)
        child = dict(
            id=child_id, name=f"{given_name} {parent['name'].split()[-1]}", age=0,
            gender="child", pronouns="they/them", occupation="child", home=parent["home"], workplace="school",
            color="#d5bb75", skin=parent["skin"], hair=other_parent["hair"],
            backstory=f"Born in Hearth to {parent['name']} and {other_parent['name']} on day {self.state['day']}.",
            goal="Grow up safe, loved, and curious.", values=["care", "play", "belonging"],
            traits={key: self.rng.randint(35, 75) for key in parent["traits"]},
            demographics=dict(identity="Hearth-born", education="not yet school age", economic_background="dependent child",
                              languages=["learning Common"], orientation="not applicable", reproductive_capacity="none",
                              relationship_preference="not applicable", religion="not specified", disability="none specified", residence_years=0),
            x=parent["x"], y=parent["y"], action="rest", action_label="Resting with family", target_id=None,
            destination=None, pending_action=None, needs=dict(energy=90, hunger=85, social=90, safety=95),
            mood="content", wallet=0, thought="Warmth, familiar voices, and a safe place to rest.", speech="",
            relationships={}, memories=[], decision=None, cooldowns={}, pregnancy=None,
            family=dict(parents=[parent["id"], other_parent["id"]], children=[], siblings=[]),
            birth_day=self.state["day"], last_action_at=self.state["total_minutes"],
        )
        for resident in self.state["villagers"]:
            is_parent = resident["id"] in child["family"]["parents"]
            relationship = dict(affinity=90 if is_parent else 15, trust=90 if is_parent else 10, romance=0,
                                status="family" if is_parent else "neighbor")
            child["relationships"][resident["id"]] = deepcopy(relationship)
            resident["relationships"][child_id] = deepcopy(relationship)
        siblings = set(parent["family"]["children"]) | set(other_parent["family"]["children"])
        for sibling_id in siblings:
            sibling = self.villager(sibling_id)
            sibling["family"]["siblings"].append(child_id)
            child["family"]["siblings"].append(sibling_id)
        for adult in (parent, other_parent):
            adult["family"]["children"].append(child_id)
            adult.pop("family_plan", None)
        parent["pregnancy"] = None
        self._change_needs(parent, {"energy": -25, "social": 20})
        self.state["villagers"].append(child)
        self.state["world"]["births"] += 1
        event = self._event("birth", f"{parent['name']} and {other_parent['name']} welcome {child['name']} to Hearth.", parent, child)
        for resident in (parent, other_parent, child):
            self._memory(resident, event["text"], "love", 10)
