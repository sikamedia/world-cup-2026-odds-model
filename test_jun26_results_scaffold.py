#!/usr/bin/env python3
"""Regression for the June-26 result extension scaffold."""

from __future__ import annotations

from match_context import context_key
from worldcup_2026_data_jun26 import JUNE_26_MATCHES, JUNE_26_RESULTS, MATCHES_60, MATCHES_66


def main() -> None:
    fixture_keys = {context_key(home, away) for home, away, *_ in JUNE_26_MATCHES}
    result_keys = {context_key(home, away) for home, away, *_ in JUNE_26_RESULTS}

    assert len(MATCHES_60) == 60
    assert len(MATCHES_66) == 60 + len(JUNE_26_RESULTS)
    assert result_keys <= fixture_keys

    for home, away, hg, ag, _host_home, batch in JUNE_26_RESULTS:
        assert isinstance(hg, int) and hg >= 0, f"{home} v {away}: invalid home score"
        assert isinstance(ag, int) and ag >= 0, f"{home} v {away}: invalid away score"
        assert batch == 5, f"{home} v {away}: June-26 results must use batch 5"

    if JUNE_26_RESULTS:
        assert len(JUNE_26_RESULTS) == len(JUNE_26_MATCHES)

    print("JUN26_RESULTS_SCAFFOLD PASS")


if __name__ == "__main__":
    main()
