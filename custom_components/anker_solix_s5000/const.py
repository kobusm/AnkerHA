"""Constants for the Anker SOLIX S5000 integration."""
DOMAIN = "anker_solix_s5000"

CONF_COUNTRY = "country"
CONF_DEVICE_SN = "device_sn"

# The device stops publishing real-time (0421) status messages this many seconds
# after a trigger, so the coordinator re-arms it on every poll before it expires.
REALTIME_TRIGGER_TIMEOUT = 300  # seconds
SCAN_INTERVAL = 240  # seconds between trigger re-arm / reconnect checks

# Fallback when the device has not yet reported ac_input_limit_max
DEFAULT_AC_INPUT_LIMIT_MAX = 1200  # W
