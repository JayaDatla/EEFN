"""Status strings persisted by the nightly real-data syncs (real_sync.py) and read back by the
API. One definition, so a typo can't silently create a state nothing reads."""

MEASURED = "measured"
VETTED = "vetted"
MATCHED = "matched"
NO_EPOCH = "no_epoch"
NO_MEASUREMENT = "no_measurement"
NO_LIGHTCURVE = "no_lightcurve"
NO_MATCH = "no_match"
UNUSABLE = "unusable"
ERROR = "error"
