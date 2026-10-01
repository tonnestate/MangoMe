"""MangoMe: persistent work-state truth for multi-agent systems."""

import os

# v0.3.18 managed single-host invariant:
# the Linux host/loopback boundary is the MongoDB trust boundary. MangoMe carries
# no MongoDB credential lifecycle. If an older local deployment still has MongoDB
# authorization enabled, zero-touch may perform the one-time fail-closed host
# migration after proving the active listener is loopback-only.
os.environ.setdefault("MANGOME_TRUST_BOUNDARY", "LOCAL_HOST")
os.environ.setdefault("MANGOME_ZERO_TOUCH_BOOTSTRAP", "1")
os.environ.setdefault("MANGOME_ZERO_TOUCH_HOST_MIGRATION", "1")
os.environ.setdefault("MANGOME_ALLOW_EVAL_DATABASE", "0")

__version__ = "0.3.18"
