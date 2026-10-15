# DSUR Validation Summary

**1 held-out validation case · 7 predefined in-scope GT issues · 3 repeated runs**

The seven ground-truth (GT) issues were frozen before model evaluation. No prompt or content-specific model tuning was performed on this sample. During acceptance testing, the case informed generic consolidation robustness fixes before these three repeated runs. “Held-out” here refers to prompt/content tuning; this is not an untouched benchmark case.

All three runs used the same input hash, recorded clean code revision (`f6ad354`), model/provider, and prompt/configuration. GT issues are counted once per run, regardless of overlapping local and cross-section findings. Partial detections do not count toward strict recall.

| Metric | R1 | R2 | R3 |
|---|---|---|---|
| GT Detected | 7/7 | 6/7 | 7/7 |
| GT Partial | 0 | 1 | 0 |
| Strict GT recall | 100% | 85.71% | 100% |
| Final findings | 16 | 19 | 20 |
| Need review | 1 | 5 | 3 |
| Finalization | completed | completed | completed |
| Fallback | none | none | none |

## GT stability

| GT | Core issue | Detected frequency |
|---|---|---|
| GT-01 | Study status: ongoing vs completed | 3/3 |
| GT-02 | ADR rate: 14/20 is 70%, not 75% | 3/3 |
| GT-03 | Drug-induced liver injury: 1 vs 2 events | 3/3 |
| GT-04 | Maximum tolerated dose: reached vs not reached | 3/3 |
| **GT-05** | **ADR data incorrectly described as TEAE** | **2/3 Detected + 1/3 Partial** |
| GT-06 | Contradictory conclusions on combination-treatment toxicity | 3/3 |
| GT-07 | Inconsistent thyroid-event inclusion in reference safety information | 3/3 |

## What the evaluation exposed

- **GT-05 — consolidation semantic loss.** R2's job-final finding identified the ADR-to-TEAE mislabeling. Consolidation combined it with a rate discrepancy, but the unified final conclusion retained only the percentage difference. R2 is therefore Partial for GT-05, despite successful upstream detection.
- **GT-03 — detection is not correction accuracy.** R3 identified the 1-versus-2 inconsistency, but one local finding recommended the wrong correction direction. Detecting a contradiction does not establish that its proposed correction is right.

All three flows completed, conserved source finding IDs, and preserved evidence alias unions. **Successful execution and provenance conservation do not guarantee semantic completeness of the consolidated conclusion.**

Final finding counts ranged from 16 to 20 (mean 18.33); need_review counts were 1, 5, and 3. Additional findings included a directly verifiable study-ID inconsistency and medical or interpretive claims requiring review. They were classified separately rather than forced into a precision score.

## Interpretation and provenance

These results support case-level GT recall and repeated-run stability evidence: six GT issues were fully detected in every run, while GT-05 exposed a consolidation weakness. One document and three repeated runs do not establish general clinical-document accuracy; the runs are not independent validation samples. Additional findings have not been fully expert-adjudicated, so precision and F1 are not reported.

The reported revision contains unclosed JSON-fence handling, no-op execution for fewer than two input findings, and passthrough of ungrouped findings. It still rejects a returned consolidation group with only one conclusion alias; a separate “singleton-group acceptance fix” is not established by this revision.

See [full evaluation details (中文)](validation_details.md) for run IDs, complete provenance, final-finding GT mappings, the consolidation trace, and additional-finding classifications. Raw runtime artifacts are not bundled with these public documents.
