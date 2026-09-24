# Third-Party Notices

MangoMe is licensed under the Apache License 2.0. The project also acknowledges external work that informed specific design patterns.

## Fable Method / fable-judge

Project: **Sahir619/fable-method**
Repository: https://github.com/Sahir619/fable-method
License: MIT License
Copyright: Copyright (c) 2026 Sahir619

MangoMe v0.1.7's adversarial completion-verification design was informed by `fable-judge`, including these general patterns:

- treat completion reports as claims rather than evidence;
- independently re-observe claimed checks before accepting them;
- compare actual changes with declared scope;
- explicitly inspect changed tests for weakened verification;
- keep unverifiable claims distinct from observed PASS results.

MangoMe implements these concepts independently within its own existing Evidence, Verification and Acceptance model. MangoMe does not incorporate Fable's verdict state machine and does not bundle Fable's source files or evaluation fixtures.

The Fable Method repository is distributed under the MIT License. Its license text is available in the upstream repository at the URL above.
