# Comparison Finding Assessment formal prompts

Formal prompt content lives in per-prompt directories as `system.txt` and `user.txt`.
Version metadata lives in `manifest.json`.

Formal runtime prompt identities use the `comparison_finding_assessment.<mode>` namespace
and are resolved to package-local storage directories via an explicit mapping.

## Version bump rules

Bump a prompt's `manifest.json` version only when that prompt's
`system.txt` or `user.txt` text changes.

Do **not** bump prompt version for renderer, planner, provider, model/profile,
thinking, seed, response parser, or runtime-only changes.

Each formal prompt (`comparison_finding_assessment.scope_local`,
`comparison_finding_assessment.focus_comparison`, `comparison_finding_assessment.ib_to_dsur`,
`comparison_finding_assessment.dsur_to_ib`) is versioned independently. There is no shared
global Comparison Finding Assessment prompt version.
