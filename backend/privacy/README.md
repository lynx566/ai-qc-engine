# Privacy engine

## UIE schema labels

UIE schema labels must describe **concrete value fields**, not role/generic terms.

**Good** (value spans):

- `受试者姓名`
- `研究中心名称`
- `申办方名称`

**Bad** (role/generic terms — do not add to UIE schema):

- `受试者`
- `研究中心`
- `申办方`
- `试验药物`
- `试验药`
- `研究药物`

`STUDY_DRUG` and related registry types are handled by **RegistryDetector**
(clinical program registry) by default, not UIE.

Clinical-trial zh schema and denylist live in
`plugins/clinical_trial_doc/privacy/uie_schema_zh.py`.

## Mask detector sources (`mapping.json` `sources`)

Production `CompositeDetector` (clinical trial POC) uses `registry` / `regex` / `uie`
only (`run_summary.detectors_used`).

| Source | Role |
|--------|------|
| `registry` | Stable predefined identity (`clinical_trial_doc.privacy.registry`) |
| `regex` | Pattern rules (`regex_rules_zh`) |
| `uie` | Model extraction when UIE is available |

Merger overlap priority (same span): `registry` > `regex` > `uie`.

Empty or missing hit source is exported as `["unknown"]` (defensive fallback only).
