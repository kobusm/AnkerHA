"""S5000 (AS510) support profile for the vendored anker-solix-api library.

The library already knows the S5000 as model AS510, but ships no MQTT message
map for it. The S5000 is the larger sibling of the S2000 (AS220), so we reuse
the S2000 map until S5000-specific fields are decoded. Registration happens at
runtime so the vendored library stays an unmodified copy.
"""
from __future__ import annotations

import copy

from .solixapi import mqtt_pps
from .solixapi.mqttmap import SOLIXMQTTMAP

S5000_PN = "AS510"
S2000_PN = "AS220"

SUPPORTED_MODELS: dict[str, str] = {
    S5000_PN: "SOLIX S5000",
    S2000_PN: "SOLIX S2000",
}


def register_s5000_profile() -> bool:
    """Teach the library to decode and control the S5000 using the S2000 schema.

    Returns True if the profile was newly added, False if already present
    (either from an earlier call or because the library gained native support).
    """
    added = False
    if S5000_PN not in SOLIXMQTTMAP:
        # Deep copy so S5000-specific overrides never leak into the S2000 map
        SOLIXMQTTMAP[S5000_PN] = copy.deepcopy(SOLIXMQTTMAP[S2000_PN])
        added = True
    # MODELS is the same set object referenced by FEATURES and the device
    # factory, so adding here enables every PPS control for the S5000.
    mqtt_pps.MODELS.add(S5000_PN)
    return added
