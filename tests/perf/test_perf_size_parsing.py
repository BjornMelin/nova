"""Tests for shared perf size parsing helpers."""

from __future__ import annotations

import pytest

from scripts.perf.file_transfer_observability_baseline import parse_sizes_gib


def test_parse_sizes_gib_filters_empty_entries_and_strips_whitespace() -> None:
    assert parse_sizes_gib("6, 50,") == [
        6 * 1024 * 1024 * 1024,
        50 * 1024 * 1024 * 1024,
    ]


def test_parse_sizes_gib_filters_empty_entries_between_values() -> None:
    assert parse_sizes_gib("6, ,50") == [
        6 * 1024 * 1024 * 1024,
        50 * 1024 * 1024 * 1024,
    ]


def test_parse_sizes_gib_rejects_all_empty_entries() -> None:
    with pytest.raises(ValueError, match="at least one size must be provided"):
        parse_sizes_gib(",,")
