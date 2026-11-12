# Hearth

A living village of twenty people, with Jev choosing their actions and OpenAI Luna writing their speech and fictional inner lives. Everything lives in this folder.

The [89-action catalog](ACTIONS.md) spans twelve categories, including work, gossip, friendship, romance, family, dissent and emergency response.

## Run

From the repository root (setup is in the top-level README):

```sh
.venv/bin/python -m village.server
```

Open **http://127.0.0.1:8765**. The village starts paused. Press Play to run it. It restores its previous saved state automatically.

A `.env` file in the repository root (copied from `village/.env.example`) supplies `OPENROUTER_API_KEY`. The local server calls both models through OpenRouter with that one key; the key stays in Python and never enters the browser. Without it, Hearth starts in the labelled demo mode.

```sh
# Explicit offline demo; no external model requests
.venv/bin/python -m village.server --demo

# New initial world, ignoring the autosave (subsequent saves replace it)
.venv/bin/python -m village.server --fresh --seed 42

# Use a different local port
.venv/bin/python -m village.server --port 8766
```

For another Python environment, install `village/requirements.txt`. Python 3.11+ is required. The browser client has no build step or npm dependencies.

## Explore

- Click a villager to inspect their persona, needs, relationships, memories, thoughts, and latest decision. Follow them through the village or zoom in on a conversation.
- Pan and zoom the map. Pause, step through decisions, or accelerate the village clock.
- Read the chronicle to follow relationships, arguments, work, and changing conditions.
- Use the oracle to introduce events: an approaching creature, unease about AI replacing work, a harvest, a storm, a new tax, or your own context. The text becomes shared experience; numerical effects influence behavior too. Intensity and duration control its strength and lifetime.
- Write any custom scenario in the oracle form. Each active scenario has **Edit** and **End** controls. Editing replaces its current influence and starts the revised duration; ending it immediately withdraws the influence, removes its visual effects (including Godzilla), and tells villagers it has passed. Memories and past consequences remain as history. Ending a scenario needs no model call.
- Invite a selected villager to think, talk, or return home.
- Save the world or export its complete current state as JSON. Reset creates a fresh seeded village.

## Model loop

1. Python advances the clock, needs, movement, and queued interactions independently of network inference.
2. Each available villager receives their own persona, memories, relationships, nearby public observations, and active world contexts.
3. Jev (`typesafe/jev-1.14` through OpenRouter's Decisions endpoint) chooses a valid action/target pair and separately decides whether thought or speech is warranted. It returns a probability for every option; the UI shows them with their source. The engine rechecks eligibility before changing the world.
4. Only when selected, Luna (`openai/gpt-6-luna` through OpenRouter chat completions) with **low reasoning** produces short structured character dialogue. Requests go only to providers that honour the strict JSON schema. The character's displayed thoughts are authored fiction, not the model's private reasoning.
5. Luna also interprets oracle prompts into bounded changes to the world. The original event text remains available to every villager.

Jev's action instructions use a flexible Maslow-inspired priority. All need scores measure fulfillment: `hunger` is nourishment, so zero means unfed and a high value means well fed. Critical bodily needs and immediate danger generally take priority, followed by ordinary work, meals, rest, and a varied social life. These are prompt-level preferences, allowing caregiving and individual differences; they do not impose a rigid hierarchy or force particular actions.

Live mode does not silently replace failed calls with scripted output. Errors appear in the interface; repeated failures pause the scheduler. Demo mode uses seeded local decisions and scripted prose, with its source labelled explicitly.

The default rate limits are **60 Jev decisions and 12 Luna calls per wall-clock minute**, shared with oracle interpretation for Luna. Autonomous dialogue leaves two Luna slots available for creating or editing scenarios. There are at most four background model jobs. Increasing game speed does not increase these call ceilings. Calls, token usage and the cost OpenRouter reports for each call are shown under **Model details**; Hearth adds up those reported costs and estimates nothing itself. A 3,000-call server-session ceiling pauses autonomous inference. Calls already in flight may finish after Pause or a scenario change, but stale results are discarded. Save/export can happen while the village runs. Scenario changes save immediately.

Environment settings, read when the server starts:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | none | Required for live mode |
| `VILLAGE_JEV_MODEL` | `typesafe/jev-1.14` | OpenRouter Decisions model |
| `VILLAGE_LUNA_MODEL` | `openai/gpt-6-luna` | OpenRouter chat model for thoughts, speech and scenarios |
| `VILLAGE_JEV_RPM` | `60` | Maximum scheduled Jev decisions per minute |
| `VILLAGE_LUNA_RPM` | `12` | Maximum narrative/oracle calls per minute |
| `VILLAGE_SESSION_CALL_LIMIT` | `3000` | Total scheduled model calls per process |

## Simulation boundaries

This is a playable simulation sandbox, not a validated model of human behavior. Work, scarcity, trust, attraction, gossip, memory, dissent, and family formation use explicit rules surrounding model choices. All twenty founders are adults. Intimacy is a private, non-graphic state transition with adult relationship eligibility; children are excluded from romance. A decision to seek intimacy does not bypass reciprocal eligibility checks. Pregnancy is compressed to **seven game days**, children age by the normal village calendar, and the population is capped at forty.

The oracle changes shared context and supported world conditions; it does not generate executable code or arbitrary new game mechanics. The map is a fixed village. Contexts expire on the village clock, while their consequences and memories may persist.

This host binds to loopback and rejects foreign browser mutation requests. It is intended for one local observer, not a public multi-user service. A future shared deployment needs authentication, per-world storage and server hosting.

## Files and persistence

- `engine.py`, `data.py`: world rules, seeded population, action catalog and memories.
- `providers.py`: typed Jev adapter, Luna adapter, explicit demo behavior, validation and usage metrics.
- `server.py`: local HTTP host, model scheduling, API, save/restore and call limits.
- `static/`: pixel-art canvas and live observer interface.
- `data/village.json`: atomic autosave every 30 seconds and at graceful shutdown; ignored by version control.
- `tests/`: engine, provider-contract and HTTP integration checks.

Run checks from the project directory:

```sh
.venv/bin/python -m pytest village/tests -q
```

## Design references

- [Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [TypeSafe primitives and structured decisions](https://docs.typesafe.ai/introduction)
- [Jev 1.14 on OpenRouter](https://openrouter.ai/typesafe/jev-1.14)
- [OpenRouter Decisions API (alpha)](https://openrouter.ai/docs/client-sdks/python/sdks/decisions/README.md)

OpenRouter marks the Decisions endpoint as alpha, so its request shape may change.
