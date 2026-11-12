# Hearth

A pixel-art village of 20 people. Jev, TypeSafe's decision model, chooses what each villager does; OpenAI's Luna (`gpt-6-luna`) writes what they think and say. Both run through OpenRouter. A Python engine runs the world and rejects any choice the rules don't allow.

![Hearth: a giant creature approaches while villagers head for shelter](village/presentation/hearth-screenshot.png)

## Run it

Python 3.11 or newer. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r village/requirements.txt
cp village/.env.example .env      # then add your OpenRouter key
.venv/bin/python -m village.server
```

Open http://127.0.0.1:8765 and press Play. The village saves itself to `village/data/village.json`, which git ignores.

Live mode needs one key in `.env`: `OPENROUTER_API_KEY`. It pays for both models:

| Model | OpenRouter ID | Used for |
| --- | --- | --- |
| Jev | `typesafe/jev-1.14` | Choosing each villager's action, with a probability for every option |
| Luna | `openai/gpt-6-luna` | Thoughts, speech and interpreting the scenarios you type |

**Model details** in the app footer shows the calls made and what OpenRouter charged for them this session.

Without keys, or with `--demo`, Hearth runs on local rules and scripted prose and makes no model calls:

```sh
.venv/bin/python -m village.server --demo
```

## Tests

```sh
.venv/bin/pip install pytest
.venv/bin/python -m pytest village/tests -q
```

The tests make no network calls.

## More

- [village/README.md](village/README.md): how the model loop, rate limits, scenarios and saves work
- [village/ACTIONS.md](village/ACTIONS.md): the 89 actions villagers can take
- [village/VALIDATION.md](village/VALIDATION.md): what has been checked live, and how
- [village/presentation/DESCRIPTION.md](village/presentation/DESCRIPTION.md): a short description for slides
