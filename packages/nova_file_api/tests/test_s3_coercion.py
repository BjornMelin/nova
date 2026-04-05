"""Tests for nova_file_api.s3_coercion helpers."""

from __future__ import annotations

import pytest

from nova_file_api.s3_coercion import (
    copy_part_etag,
    normalize_prefix,
    opt_str,
    parse_non_negative_int,
    parse_positive_int,
)


def test_normalize_prefix() -> None:
    assert normalize_prefix("") == ""
    assert normalize_prefix("  ") == ""
    assert normalize_prefix("foo") == "foo/"
    assert normalize_prefix("foo/") == "foo/"


def test_opt_str() -> None:
    assert opt_str("x") == "x"
    assert opt_str(1) is None
    assert opt_str(None) is None


def test_parse_positive_int() -> None:
    err = ValueError

    assert parse_positive_int(3, error_message="bad", err=err) == 3
    assert parse_positive_int("5", error_message="bad", err=err) == 5

    with pytest.raises(ValueError, match="bad"):
        parse_positive_int(0, error_message="bad", err=err)
    with pytest.raises(ValueError, match="bad"):
        parse_positive_int(-1, error_message="bad", err=err)
    with pytest.raises(ValueError, match="bad"):
        parse_positive_int("0", error_message="bad", err=err)
    with pytest.raises(ValueError, match="bad"):
        parse_positive_int("nope", error_message="bad", err=err)


def test_parse_non_negative_int() -> None:
    err = ValueError

    assert parse_non_negative_int(0, error_message="bad", err=err) == 0
    assert parse_non_negative_int(2, error_message="bad", err=err) == 2
    assert parse_non_negative_int("0", error_message="bad", err=err) == 0

    with pytest.raises(ValueError, match="bad"):
        parse_non_negative_int(-1, error_message="bad", err=err)


def test_copy_part_etag() -> None:
    err = ValueError

    assert (
        copy_part_etag(
            {"CopyPartResult": {"ETag": '"abc"'}},
            err=err,
        )
        == '"abc"'
    )

    with pytest.raises(ValueError, match="multipart export copy part result"):
        copy_part_etag({}, err=err)
    with pytest.raises(ValueError, match="multipart export copy part etag"):
        copy_part_etag({"CopyPartResult": {}}, err=err)
