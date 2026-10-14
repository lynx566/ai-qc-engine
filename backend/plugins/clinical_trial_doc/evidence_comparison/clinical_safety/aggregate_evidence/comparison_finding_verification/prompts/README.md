# Comparison Finding Verification formal prompts

Verification prompts check proposed Comparison Finding Assessment findings against
the supplied evidence and return structured verification outcomes for reconciliation.

Formal prompt content lives in per-prompt directories as `system.txt` and `user.txt`.
Version metadata lives in `manifest.json`.

Formal runtime prompt identities use the `comparison_finding_verification.<mode>` namespace
and are resolved to package-local storage directories via an explicit mapping.

## Version bump rules

Bump a prompt's `manifest.json` version only when that prompt's
`system.txt` or `user.txt` text changes.

Do **not** bump prompt version for renderer, planner, provider, model/profile,
thinking, seed, response parser, or runtime-only changes.

Each formal prompt (`comparison_finding_verification.scope_local`,
`comparison_finding_verification.focus_comparison`, `comparison_finding_verification.ib_to_dsur`,
`comparison_finding_verification.dsur_to_ib`) is versioned independently. There is no shared
global Comparison Finding Verification prompt version.
