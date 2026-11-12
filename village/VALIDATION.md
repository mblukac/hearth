# Validation — 21 September 2026

- **80 automated tests passed** across engine rules, model-provider contracts, scenario lifecycle, and server/HTTP integration. The HTTP tests use a temporary loopback server and mocked models. Both browser JavaScript modules pass syntax checks.
- **Extended offline simulation:** 720 clock advances, 685 decisions and 83 distinct actions over three village days completed without exceptions. Population remained twenty, food remained available, and every need stayed within 0–100. An independent run also checked that residents never entered blocked map tiles.
- **Real provider checks:** verified `typesafe/jev` through the project's existing Cloudflare REST route and `gpt-5.6-luna` with low reasoning through OpenAI Responses. The running browser app also made successful autonomous calls using the complete village action candidates and personas.
- **Live oracle scenario:** an approaching giant creature increased shared concern, entered every villager's memories and appeared on the map. Residents warned neighbors, prepared emergency supplies, sought reassurance and attended to ordinary needs. Luna's dialogue referred to the event and individual backstories.
- **Browser checks:** map rendering, animation, sprite selection, inspector tabs, relationship lists, live/demo selection, play/pause, following/zooming, oracle submission, save confirmation and model provenance. No browser errors were observed. Verified the oracle chronicle row after correcting a CSS class collision.
- **Scenario lifecycle:** live browser checks created a custom Godzilla warning, edited it through Luna, and ended it without a model call. The active influence disappeared and residents received resolution thoughts/memories; old memories were labelled Replaced or Dismissed. Automated checks cover withdrawal, replacement, expiry, overlapping weather, atomic validation, saved history, stale in-flight dialogue, and oracle updates surviving unrelated scenario expiry.
- **Live operation:** after the update, the saved village resumed in live mode with successful Jev decisions and Luna dialogue. A subsequent AI-unease scenario was preserved, and Luna's character dialogue responded to it. No provider errors were reported during verification.
- **Persistence:** automated round-trip checks preserve villagers, memories, contexts, scenario history, clock, paths and random-generator state. The existing village was restored and left running live. A pre-update backup is in ignored `data/before-scenario-controls.json`; the earlier procedural QA world is in `data/qa-demo.json`.

Pregnancy, economics and social consequences are deliberately simplified game rules. These checks establish software behavior, not empirical accuracy as a model of society.

## Needs-priority prompt revision

After pausing the village on day 9 at 16:31, the Jev action instructions were adjusted to explain the need scales and encourage flexible Maslow-inspired priorities, ordinary work, meals, and sleep. No engine rules, candidate filtering, or saved-world values were changed.

A live paired comparison used six isolated copies of the paused context, with controlled needs/resources/time for four cases. The final comparison made twelve Jev calls and no Luna calls. Selected actions shifted from reflection to sleep for the exhausted farmer, listening to baking for the hungry baker, sharing food to eating for a hungry resident with food available, and eating to sleep for the tired nighttime resident. The fed, rested, lonely resident continued choosing a social action. In the empty-larder baker case, total probability on food-producing actions rose from about 1% to 62%; in the nighttime case, recovery actions rose from about 6% to 55%.

These are single paired samples per case, not a long-run sustainability test. Full results are retained in ignored `data/jev-needs-prompt-check.json`. The user's village remains paused.

## World-value precision correction

World changes now retain full precision internally, with rounding left to the interface. Previously, the two-minute live tick's 0.004 tension decrease rounded away, while other small changes varied with tick size. The existing rates and bounds are unchanged.

Five regression cases reproduce the former failures and now pass: equal elapsed-time recovery with two-, five-, and twenty-minute ticks; sub-cent decay across save/restore and the zero boundary; and continued famine pressure with an upper bound of 100. The complete suite passes **85 tests**.

Offline checks on copies of the paused day-9 village verified tension falls from 100 to 99.52 over four hours when the larder is stocked, equally at two- and five-minute tick sizes. The original hungry, empty-larder conditions still keep tension at 100 because ongoing pressure outweighs recovery. No model calls were needed, and the user's saved world was preserved.

## Luna model update (2026-11-06)

Luna moved from `gpt-5.6-luna` to `gpt-6-luna`. This account has no `gpt-6.1-luna`: the OpenAI model list does not include it and a direct request returns 404. All 85 tests passed. A live run of the saved village made 99 Jev and 23 Luna calls with no errors, and a separate oracle interpretation returned a valid bounded event. Afterwards the autosave was restored to its state before the run.

## Map layout fix (2026-11-06)

Four homes overlapped the lanes drawn in `static/scene.js`, and Rosemary house overlapped Little green house. The homes now sit one per block in the two western columns and two per block in the eastern column, and Stillwater pond moved to the open north-east corner by the river. Saved villages adopt the authored map when loaded; residents standing inside a moved building step to the nearest open tile, and walks to a moved door are re-routed. A new test reads the lanes from `scene.js` and fails on the old layout. All 87 tests passed, and the saved village loaded and ran live (61 Jev and 13 Luna calls, no errors) before the autosave was restored.

## OpenRouter transport (2026-11-12)

Both models now run through OpenRouter with one `OPENROUTER_API_KEY`. Jev is `typesafe/jev-1.14` on the alpha Decisions endpoint (`/api/alpha/decisions`), which takes the same typed questions and returns the same per-option probabilities as the earlier Cloudflare route. Luna is `openai/gpt-6-luna` through chat completions, with a strict JSON schema, low reasoning, and routing limited to providers that honour both. All 91 tests passed. A live check on the saved village made three Jev decisions over 76–82 actions each (0.3–0.4 s per decision) and four Luna calls (three narrations, one scenario), with no errors. The app then ran live from a fresh world for about half a minute: 29 of 29 Jev calls and 9 of 9 Luna calls succeeded, and Model details showed the spend OpenRouter reported ($0.0123 for Jev, $0.0064 for Luna).
