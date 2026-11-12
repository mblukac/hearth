# Hearth

**In one line:** A pixel-art village of 20 people. One model decides what each villager does, and another writes what they think and say.

## Short description

Hearth starts with 20 adults, each with a backstory, needs (food, rest, company, safety), relationships and memories. Jev, TypeSafe's decision model, picks every villager's next move from 89 actions in 12 categories, from work and gossip to romance, dissent and emergency response. Jev also decides when a moment calls for a thought or a spoken line, and OpenAI's Luna (`gpt-6-luna`) writes it. A Python engine runs the clock, food, money and movement, and rejects any choice the rules don't allow. Couples can have children, and the village can grow to 40.

You change the world by typing an event: a storm, a new tax, a rumor that machines will take the village's work, a giant creature crossing the river. Luna turns the text into bounded changes to dread, tension, prosperity and food, and every villager remembers it. When we sent a giant creature, residents warned their neighbors, packed supplies and looked for shelter, while still eating meals and finishing work shifts.

Hearth is a sandbox, not a validated model of human behavior. Fixed rules govern work, scarcity, trust, attraction and family, and the models choose within them.

## Screenshot caption

`hearth-screenshot.png`: A giant creature approaches from the east. Jev had Sana Rahman, a 33-year-old librarian, evacuate with Nell Brooks (56%; seeking shelter came next at 19%). Luna wrote Sana's thought and what she says to Nell.

## Before the demo

From the repository root:

```sh
.venv/bin/python -m village.server
```

Open http://127.0.0.1:8765. The village restores its last save and starts paused; press Resume. Add `--demo` to run without model calls.
