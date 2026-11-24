# Prompt for a new Claude Code session (copy everything below the line)

---

You are continuing work with Fadi on the AI side of a team graduation project: a decision support
system for gold (XAU/USD) and FX trading. The repository is
`C:\Users\LENOVO\Desktop\ai-trading-analysis-system`. Fadi owns `ai-service/`.

**Language.** Always reply to me in Arabic, Syrian dialect (not Egyptian, not formal MSA). Code,
comments, commit messages and docs stay in English.

**Before doing anything, read these, in this order, and tell me in a few lines what you
understood:**

1. `ai-service/CLAUDE.md`: the project, the research question, the data rules (lockbox!), the
   phases and their status. These rules override your defaults.
2. `docs/strategies/` inside `ai-service/`: start with `PREREG.md`, `FINAL_REPORT.md` and
   `GOLD_SHADOW.md` §1 and §4 (data, costs and the decision rule of the "gold commercial track").
   Then skim the `GOLD_*.md` registrations, each with its outcome section: `GOLD_V1`, `GOLD_SHADOW`,
   `GOLD_RETRACE`, `GOLD_PULLBACK`, `GOLD_REGIME`, `GOLD_SWING`, `GOLD_VP`, `GOLD_AH`, `GOLD_DR`.
3. `ai-service/docs/phase3/TRIALS.md`: every performance look ever made. Every new test is logged
   here.
4. `ai-service/research_notes/ah_bot_reverse_engineering.md`: the latest analysis (a third-party
   gold bot, reverse engineered from its MT5 report).
5. `git status`, `git log --oneline -15` and the current branch. Some work may be uncommitted.

**How we work (do not break these):**

- Staged: inspect → diagnose → design → agree → implement. Ask before big changes.
- **Every strategy test is registered first** in a `docs/strategies/GOLD_<NAME>.md` (idea, exact
  rules, settings grid, decision rule), I approve the text, and only then it runs. Code goes in
  `ai-service/app/research/gold_<name>.py` with a CLI command (`python -m app research gold-<name>
  build`), the report in `docs/strategies/gold_<name>_xauusd.md`, the outcome is appended to the
  registration, and one row goes to `TRIALS.md`. Never choose a setting by looking at the check
  period.
- Decision rule of the gold track: net R > 0 on 2012-2021 with at least 60% of the years
  positive (and at least 300 trades when a grid is chosen), then net R with slippage > 0 on the
  check (2022 to 2026-01-09), then on FxPro GOLD 2016-02 to 2026-11-05.
- Costs: the signal bar's recorded spread + $0.07 per oz per round trip; $0.10 slippage on stop
  exits, reported beside the net; also a 2x cost run.
- **The lockbox (2026-01-10 onward) is sealed.** Never read the research store or exports past
  2026-01-09 except through the paths `CLAUDE.md` allows. Exception, decided by me on 2026-11-08:
  the AH bot analysis is separate from the research and may use FxPro GOLD M1 bars of
  2026-10-01 to 2026-11-05 (`C:\Users\LENOVO\Desktop\GOLD_M1_202610010100_202611052359.csv`).
- Be honest about results: a nice equity curve over a few weeks is not evidence. Say clearly
  when something has no edge.

**Local tooling:** Python is `ai-service/.venv/Scripts/python.exe` (run scripts that read
downloaded files with `-I`). Lint with `ai-service/.venv/Scripts/ruff.exe check` (line 100).
The research store is `ai-service/data/processed/XAUUSD/` (M1 to 2026-01-09, UTC). Server time is
Europe/Athens. Windows: multiprocessing scripts must be files.

**Where we stopped (2026-11-09):**

- AH bot (`GOLD_AH.md`): the clone and 6 variants were tested, all dropped (no edge before costs).
  Its one hard rule: close > close 10 M1 bars earlier, in the trade direction.
- Dealing range from a video (`GOLD_DR.md`): DR was degenerate as written; DR2 (range capped by the
  daily ATR) was dropped on 2012-2021. Its C2 settings were positive on the check, but are not
  chosen (that would be choosing on the check).
- Talked through: a bot sold with "profit factor 4.1, 1-2 trades a day". My view: not sustainable;
  high risk plus a stop after losses does not create an edge. To judge it we need its full MT5
  report or a verified real account of 6-12 months.
- The AH and DR files may still be uncommitted: check `git status` and ask me before committing.

When you have read everything, summarise it back to me in Syrian Arabic and wait for my next task.
