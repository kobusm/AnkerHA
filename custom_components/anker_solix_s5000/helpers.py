"""Pure helpers shared by entity platforms (no Home Assistant imports, unit-testable)."""
from __future__ import annotations

from typing import Any


def option_label(key: str, zero_label: str | None = None) -> str:
    """Turn a library option key into a UI label.

    "time_of_use" -> "Time Of Use", "30" -> "30", "0" -> zero_label (e.g. "Never").
    """
    if key.lstrip("-").isdigit():
        return zero_label if zero_label and int(key) == 0 else key
    return key.replace("_", " ").title()


def build_option_labels(
    option_map: dict[str, Any], zero_label: str | None = None
) -> dict[str, Any]:
    """Map UI label -> raw device value for a library option map."""
    return {option_label(str(k), zero_label): v for k, v in option_map.items()}


def label_for_value(labels: dict[str, Any], value: Any) -> str | None:
    """Reverse lookup of the UI label for a raw state value (int/str tolerant)."""
    if value is None:
        return None
    for label, raw in labels.items():
        if raw == value or str(raw) == str(value):
            return label
    return None


def to_number(value: Any) -> float | int | None:
    """Coerce an MQTT value to a number, or None if it is not numeric."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        try:
            num = float(value)
        except ValueError:
            return None
        return int(num) if num.is_integer() else num
    return None


def is_on(value: Any) -> bool | None:
    """Interpret an MQTT switch/status value (0/1, "on"/"off", bool)."""
    if value is None:
        return None
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("on", "true"):
            return True
        if low in ("off", "false"):
            return False
    num = to_number(value)
    return None if num is None else num != 0
