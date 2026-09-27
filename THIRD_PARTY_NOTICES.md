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


## Design acknowledgements for v0.3.0 (no bundled code)

MangoMe v0.3.0 also acknowledges external ideas that informed architecture discussions without becoming runtime dependencies or copied source code.

### Anthropic Agent Skills

Anthropic's Agent Skills model informed the distinction between reusable procedural guidance and durable project truth, particularly progressive disclosure of instructions/resources. MangoMe does not bundle Anthropic Skill code. In MangoMe, a Playbook/Skill remains procedural and non-normative; it cannot define WorkIdentity, effective Specification truth, or assurance.

### OpenSpec ecosystem

OpenSpec-style separation between specifications (what should become true) and execution procedure informed MangoMe's decision to keep Specifications as evolving normative inputs while Plans/Playbooks remain execution concerns. MangoMe does not copy or vendor OpenSpec source code in this release.

### External architecture review

Review feedback supplied through Grok was considered for deterministic effective views, assurance/evidence policy, and read-path performance. It is treated as advisory design input, not a dependency, library, or source-code contribution.

The project distinguishes **INSPIRED BY** from **DEPENDS ON**, **BUNDLES CODE FROM**, and **OPTIONALLY INTEGRATES WITH**. v0.3.0 adds no new third-party runtime dependency for WorkIdentity, persistence levels, Playbooks, or normative baselines.

## Laya design acknowledgement for v0.3.3 (no bundled code)

Project: **NandhaKishorM/laya**
Repository: https://github.com/NandhaKishorM/laya
License: Apache License 2.0

Laya's public typed-decision approach informed the discussion that led to MangoMe FJD/1, particularly the usefulness of bounded choice/score/yes-no style outputs, explicit confidence, and fallback/gating for repeated low-cost decisions.

MangoMe does **not** depend on Laya, does not bundle Laya models or source files, and does not reproduce Laya's API. FJD/1 is an independently implemented MangoMe protocol using `BOOL`, `SCORE`, and `CHOICE` worker judgments, progressive provenance, and MangoMe-specific epistemic/authority boundaries.
