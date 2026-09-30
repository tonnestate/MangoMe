"""MangoMe: persistent work-state truth for multi-agent systems."""

import os

# v0.3.13 P0 invariant: a shared MongoDB service must never be stopped/restarted
# merely because MangoMe runs as root. Explicit operator opt-in remains possible.
os.environ.setdefault("MANGOME_ZERO_TOUCH_LOCAL_PROVISION", "0")

__version__ = "0.3.13"
