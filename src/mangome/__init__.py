"""MangoMe: persistent work-state truth for multi-agent systems."""

import os

# v0.3.15 keeps the v0.3.14 deployment invariant:
# local-host MongoDB is the trust boundary for the managed single-host profile.
# No MongoDB credential/user bootstrap is performed by MangoMe.
os.environ.setdefault("MANGOME_TRUST_BOUNDARY", "LOCAL_HOST")
os.environ.setdefault("MANGOME_ZERO_TOUCH_BOOTSTRAP", "1")
os.environ.setdefault("MANGOME_ZERO_TOUCH_LOCAL_PROVISION", "0")
os.environ.setdefault("MANGOME_ALLOW_EVAL_DATABASE", "0")

__version__ = "0.3.15"
