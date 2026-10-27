"""``python -m app strategies count`` (docs/strategies/PREREG.md, section 12) on a synthetic store:
the frozen-commit guard, the report files, no outcome code, and the lockbox refusal. Nothing here
reads the research store."""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.strategies import cli, counts
from tests.strategy_data import PRIMARY, market
from tests.test_strategies_counts import FORBIDDEN, ROOT


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """XAUUSD frames of the synthetic primary-period market, as the store's Parquet files."""
    d = tmp_path / "store" / "XAUUSD"
    d.mkdir(parents=True)
    for tf, f in market("XAUUSD", 7, *PRIMARY).items():
        f.to_parquet(d / f"{tf}.parquet", index=False)
    return tmp_path / "store"


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "frozen_commit", lambda: ("a" * 40, "b" * 40))


def test_the_command_never_imports_outcome_code() -> None:
    code = "import sys, app.strategies.cli; print('\\n'.join(sorted(sys.modules)))"
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    assert "app.strategies.cli" in out
    assert [m for m in out if any(m == f or m.startswith(f + ".") for f in FORBIDDEN)] == []


def test_count_writes_the_report_and_the_yearly_table(store, tmp_path, frozen, capsys) -> None:
    out = tmp_path / "out"
    assert cli.main(["count", "--store", str(store), "--out", str(out)]) == 0
    md = (out / "counts.md").read_text(encoding="utf-8")
    assert "a" * 40 in md and "b" * 40 in md  # frozen commit and HEAD
    assert "Descriptive only" in md and counts.HOLDOUT_LABEL in md
    assert "| XAUUSD |" in md.split("## Per instrument")[1]
    for title in ("Armed candidates", "Rejections", "By type", "Allowance"):
        assert f"## {title}" in md
    y = pd.read_csv(out / "counts_by_year.csv")
    counts.check_no_outcomes(y)
    assert set(y["symbol"]) == {"XAUUSD"} and y["candidates"].sum() > 0
    assert "counts.md" in capsys.readouterr().out


def test_count_runs_with_resolve_and_management_replaced_by_raising_functions(
    store, tmp_path, frozen, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.management.engine as engine
    import app.setups.labels as labels

    def boom(*a, **k):
        raise AssertionError("outcome logic called by the count command")

    for mod, name in [(labels, "resolve"), (labels, "label_all"), (engine, "manage")]:
        monkeypatch.setattr(mod, name, boom)
    assert cli.main(["count", "--store", str(store), "--out", str(tmp_path / "o")]) == 0


def test_a_swap_export_gives_s3_its_allowance(store, tmp_path, frozen) -> None:
    sw = {"XAUUSD": dict(mode="POINTS", long=-50.0, short=-50.0, rollover3days=3, point=0.01,
                         contract_size=100.0, currency_base="XAU", currency_profit="USD",
                         currency_margin="XAU")}  # fmt: skip
    path = tmp_path / "swaps.json"
    path.write_text(json.dumps(sw), encoding="utf-8")
    args = ["count", "--store", str(store), "--out", str(tmp_path / "o")]
    assert cli.main(args) == 0
    no_swap = (tmp_path / "o" / "counts.md").read_text(encoding="utf-8")
    assert cli.main([*args, "--swaps", str(path)]) == 0
    with_swap = (tmp_path / "o" / "counts.md").read_text(encoding="utf-8")

    def s3(md: str) -> str:
        return next(x for x in md.split("## Allowance")[1].splitlines() if x.startswith("| S3 |"))

    assert s3(no_swap).endswith("|  |  |")  # a_S and delta* not computed
    assert not s3(with_swap).endswith("|  |  |")


def test_an_end_past_the_lockbox_start_is_refused(store, tmp_path, frozen) -> None:
    with pytest.raises(ValueError, match="lockbox"):
        cli.main(["count", "--store", str(store), "--out", str(tmp_path), "--end", "2026-01-11"])
    assert not (tmp_path / "counts.md").exists()


def test_count_is_refused_while_the_rules_are_not_frozen(store, tmp_path, capsys) -> None:
    """The real preregistration: the field is still empty."""
    assert cli.main(["count", "--store", str(store), "--out", str(tmp_path)]) == 2
    assert "not frozen" in capsys.readouterr().err
    assert not (tmp_path / "counts.md").exists()


# --- the frozen-commit guard on a throwaway repository -----------------------------------------


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


def prereg(path: Path, value: str) -> Path:
    path.write_text(f"| Field | Value |\n| --- | --- |\n| Rules frozen at commit | {value} |\n")
    return path


def test_the_guard_refuses_any_rule_file_that_differs_from_the_frozen_commit(tmp_path) -> None:
    repo = tmp_path / "repo"
    rules = repo / "ai-service" / "app" / "strategies" / "rules.py"
    rules.parent.mkdir(parents=True)
    rules.write_text("A = 1\n")
    (repo / "README.md").write_text("x\n")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "rules")
    head = git(repo, "rev-parse", "HEAD")
    p = tmp_path / "PREREG.md"

    for value in ("_(commit; before any count)_", "0" * 40):
        with pytest.raises(ValueError, match="not frozen|not in this repository"):
            cli.frozen_commit(prereg(p, value), repo)
    assert cli.frozen_commit(prereg(p, head[:12]), repo) == (head, head)

    (repo / "README.md").write_text("y\n")  # not a rule file
    git(repo, "commit", "-q", "-am", "docs")
    assert cli.frozen_commit(p, repo)[0] == head

    rules.write_text("A = 2\n")  # uncommitted change
    with pytest.raises(ValueError, match="differ"):
        cli.frozen_commit(p, repo)
    git(repo, "commit", "-q", "-am", "change")  # committed after the freeze
    with pytest.raises(ValueError, match="differ"):
        cli.frozen_commit(p, repo)
    git(repo, "revert", "--no-edit", "HEAD")
    assert cli.frozen_commit(p, repo)[0] == head
    (repo / "ai-service" / "app" / "config").mkdir(parents=True)
    (repo / "ai-service" / "app" / "config" / "new.toml").write_text("x = 1\n")  # untracked
    with pytest.raises(ValueError, match="differ"):
        cli.frozen_commit(p, repo)
