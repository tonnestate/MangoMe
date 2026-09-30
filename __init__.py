"""MangoMe: persistent work-state truth for multi-agent systems."""

import os

# P0 safety invariant: never stop/restart a shared MongoDB service merely because
# MangoMe runs as root. Local no-auth recovery remains available only by explicit
# operator opt-in via MANGOME_ZERO_TOUCH_LOCAL_PROVISION=1.
os.environ.setdefault("MANGOME_ZERO_TOUCH_LOCAL_PROVISION", "0")

__version__ = "0.3.12"
