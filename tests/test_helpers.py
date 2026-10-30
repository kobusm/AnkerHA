"""Pure helper functions."""
import pytest

from custom_components.anker_solix_s5000.helpers import (
    build_option_labels,
    is_on,
    label_for_value,
    option_label,
    to_number,
)


@pytest.mark.parametrize(
    ("key", "zero", "expected"),
    [
        ("time_of_use", None, "Time Of Use"),
        ("low", None, "Low"),
        ("30", None, "30"),
        ("0", "Never", "Never"),
        ("0", None, "0"),
    ],
)
def test_option_label(key, zero, expected):
    assert option_label(key, zero) == expected


def test_label_round_trip():
    labels = build_option_labels({"0": 0, "15": 15, "60": 60}, "Never")
    assert list(labels) == ["Never", "15", "60"]
    assert label_for_value(labels, 0) == "Never"
    assert label_for_value(labels, "60") == "60"
    assert label_for_value(labels, 99) is None
    assert label_for_value(labels, None) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(5, 5), (2.5, 2.5), ("12", 12), ("12.5", 12.5), (True, 1), ("x", None), (None, None)],
)
def test_to_number(value, expected):
    assert to_number(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, True), (0, False), ("on", True), ("OFF", False), ("1", True), (None, None), ("?", None)],
)
def test_is_on(value, expected):
    assert is_on(value) is expected
