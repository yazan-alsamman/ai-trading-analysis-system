# P7: the AI layer that explains (plan, 2026-11-13)

Principle (unchanged): **code computes, the model scores, the LLM explains.** The LLM never produces
a number; every number it writes is checked against the tool output, and an unchecked text is never
shown (contract §9: `verified` / `template_used`).

## Decisions (Fadi, 2026-11-13)

1. **LLM: Gemini 3.6 Flash** (`gemini-3.6-flash`), through Google's official `google-genai` SDK,
   the same model and SDK the backend already runs for chart analysis (`docs/chart-analysis.md`).
   Behind a thin provider interface in `app/agent/llm.py`, so the model can change without touching
   the rest. Key: `GEMINI_API_KEY` in ai-service's environment; with no key, `/v1/explain` answers
   with the template (below), never an error.
2. **What is explained: the five (and ROUND), served by ai-service.** Today `/v1/evaluate` serves
   the L1 SMC setups, which showed no edge; the only strategies with one run on the EA alone. P7
   first serves them as a new profile, then explains them.

## Built for more strategies (Fadi, 2026-11-13)

F1-F3 are built so that a strategy added later is served and explained without new explanation
code or a new contract negotiation:

1. **A strategy registry** (`app/catalog/`): each strategy is an entry with an id, a version, the
   code that computes its signals, and a **description file** in Arabic and English
   (`app/catalog/descriptions/<id>.<lang>.md`) that states its logic in plain words. The LLM and the
   template read the description; a new strategy brings a new description, not new explanation code.
2. **One evidence shape** in every setup: common fields (entry type, entry, stop, **exit type**:
   `target` / `trailing` / `time`, the time window, the strategy id and version, the day's volatility
   outlook) and a list of strategy-specific facts, each `{key, value, label_ar, label_en}` (for
   example the level's name). Template, LLM and checker read only this shape.
3. **A generic number checker:** every number in a text must be a number of the setup or its
   evidence; it knows nothing about any one strategy.
4. **A general contract change:** instead of "tp may be null for the five", every setup carries an
   `exit_type` (`target`, `trailing`, `time`); `tp` is required only with `target`; `sl` may move
   while `ACTIVE` (a `sl_moved` transition). One negotiation with Yazan covers later strategies.

Any new strategy still passes the research first (registration, test, unseen data) before it enters
the registry; an explanation never makes a strategy without an edge look convincing.

## Steps

### F1. Serve the five in `/v1/evaluate` (needs Yazan's agreement on the contract)

A new profile, `gold_levels`, with the frozen rules of `GOLD_V1.md` + shadows + ROUND (the code the
EA is matched to: `gold_combo.levels`, `gold_shadow`, `gold_round`, M8).

- **Setup shape:** one setup per level and day. `DEVELOPING` at the day's start (the level is known,
  02:00 New York); `ARMED` while the stop order would wait (entry = the level, sl = level ∓ D);
  `ACTIVE` at the touch; `CLOSED` at the trailing stop or 16:45; `EXPIRED` at 16:00 untouched.
  The stop's moves under M8 are transitions with the new sl.
- **Contract changes to agree with Yazan (proposal):**
  1. `tp` may be null in `ARMED` / `ACTIVE` for a profile whose exit is a trailing stop (today it is
     required); `r_multiple` null with it.
  2. A setup's `sl` may change while `ACTIVE` (a `sl_moved` transition with the new value).
  3. The `gold_levels` profile receives **5m bars** (about 3,000 = 10 days) besides 1h / 4h / 1d:
     the five touch and trail on 5m.
- **Gate:** the service's setups for a past week equal the EA's trades on the same days (the
  `gold-demo check` match, at least 95%).

### F2. The template (no LLM; ships first)

`/v1/explain` for a `gold_levels` setup returns a fixed Arabic and English template filled only
with the setup's own fields and its `evidence` (the level's name and price, D, the stop, the time
window, the management rule, and the day's volatility outlook, which `evaluate` copies into
`evidence`, so the explain request needs nothing new). `template_used: true`, `verified: true`.
L1 setups get the same treatment with their own template.

### F3. The Gemini explanation and the number checker

- The model receives the setup and evidence as data and writes a short explanation (what the level
  is, why the order sits there, what the stop means, what today's news and volatility say), in the
  requested language. Prompt versioned (`PROMPT_VERSION`, never edited in place); low temperature;
  a timeout under the contract's 30 s.
- **Checker (`app/agent/verify.py`):** every number in the text (prices, distances, percentages,
  times, counts, in Western or Arabic-Indic digits) must equal a number in the setup or evidence,
  after the same rounding; a number that is not there, or a direction / level name that contradicts
  the setup, fails the text. Pass: `verified: true`. Fail: the template is returned
  (`template_used: true`) and the failure is logged without the text.
- **No advice words:** the prompt and the checker reject "buy now", "guaranteed", and similar; the
  text describes, it does not recommend.

### F4. The P7 gate

An evaluation set of 50 `gold_levels` setups (mixed levels, both directions, news and quiet days,
both languages): **zero invented numbers** (the checker on all 50, and Fadi's reading of the
Arabic ones), the checker's own test set of planted wrong numbers (it must catch every one), and the
fallback rate reported.

### F5. Later: the chat agent (`/v1/agent/chat`)

Read-only tools (today's setups, a setup, the volatility outlook, the news, the monitor's health,
the research's definitions) with Gemini function calling and the same checker on every answer. Its
contract is agreed with Yazan after F1-F4.

## Order and what can start now

F1's engine and tests can be built now; the contract change goes to Yazan in the same week. F2
follows F1's setup shape. F3 needs `GEMINI_API_KEY`. Nothing here changes the EA or the five's
rules.

## Progress

- **2026-11-13, F1 engine built, not served.** Registry and descriptions (`app/catalog/`), the
  engine (`app/live/gold_levels.py`: one setup per strategy, level and day, its lifecycle and the
  proposed payload), tests on synthetic bars (`tests/test_gold_levels_live.py`). Checked on the
  store (`gold_levels_check.md`): 138 days of 2025-07 to 2026-01, request-sized frames, **650 of 650
  trades matched**, no look-ahead (1,932 of 1,932 paths at 10:00 start the 16:55 path); one trade
  differs, on a bar where two levels of one strategy were touched: the engine takes the nearer
  level, as the EA's stop orders fill, while the research code's unstable sort took the farther
  one's entry (research code unchanged). Contract proposal for Yazan: `CONTRACT_PROPOSAL.md`.
  Serving waits for it.

