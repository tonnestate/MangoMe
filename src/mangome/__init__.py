"""MangoMe: persistent work-state truth for multi-agent systems."""

import os

# v0.3.20 managed single-host invariant:
# LOCAL_HOST is a cooperative host trust boundary, not a tamper-resistant verifier
# boundary. MangoMe carries no MongoDB credential lifecycle in this mode. If an
# older local deployment still has MongoDB authorization enabled, zero-touch may
# perform the one-time fail-closed host migration only after proving loopback.
os.environ.setdefault("MANGOME_TRUST_BOUNDARY", "LOCAL_HOST")
os.environ.setdefault("MANGOME_ZERO_TOUCH_BOOTSTRAP", "1")
os.environ.setdefault("MANGOME_ZERO_TOUCH_HOST_MIGRATION", "1")
os.environ.setdefault("MANGOME_ALLOW_EVAL_DATABASE", "0")

__version__ = "0.3.20"
