# Backend

Python backend for **AI QC Engine** and its current **Clinical Trial Document QC** product. It contains the Product Task/Flow execution stack, installed clinical plugins, artifact persistence, HTTP transport, and report rendering.

The currently installed QC function is **Writing Accuracy & Consistency Review（撰写准确性与一致性核查）**, with **Investigational Product Clinical Safety** (`clinical_safety`) as its current analysis scope.

See the [project README](../README.md) for the browser Quick Start and [Architecture](../ARCHITECTURE.md) for system ownership and execution design.

## Requirements and Installation

**Python 3.11** is the tested development environment. Commands in this guide run from the repository root unless stated otherwise.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For development, tests, and PDF QA, additionally install:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

| Manifest | Purpose |
| --- | --- |
| [requirements.txt](../requirements.txt) | Default product runtime |
| [requirements-dev.txt](../requirements-dev.txt) | Development/TestClient and PDF QA dependencies; install alongside base requirements |
| [requirements-privacy.txt](../requirements-privacy.txt) | Optional UIE privacy runtime |

The base manifest currently includes pytest. The optional Paddle pins are separate from the default workflow.

## Provider Configuration

The current installed Qwen/Bailian workflow requires both:

```dotenv
DASHSCOPE_API_KEY=...
BAILIAN_BASE_URL=...
```

Set private environment variables or create an ignored root `.env` using [.env.example](../.env.example). Supply your full provider base URL privately.

Provider construction calls `python-dotenv` discovery through `load_dotenv()`; it does not hardcode a root `.env` path. The normal repository-root and backend-directory invocation contexts discover the root file. Existing environment variables take precedence.

The provider layer also supports DeepSeek, which requires `DEEPSEEK_API_KEY` when selected. That key is not required by the current installed Qwen configuration.

## Main Entrypoints

### Product HTTP Server

```powershell
.\.venv\Scripts\python.exe backend/scripts/clinical_trial_doc_qc_server.py
```

[clinical_trial_doc_qc_server.py](scripts/clinical_trial_doc_qc_server.py) starts the full product API at `http://127.0.0.1:8765`, with reload disabled. It is the backend for the browser workflow, including Task creation, QC Setup, Result, saved review/annotation state, and single-document PDF download.

Its default runtime workspace is `backend/`, derived from the source location. The frontend's Vite proxy targets this address.

### Product Task CLI

[run_product_task.py](scripts/run_product_task.py) owns a persisted Product Task journey.

| Command | Behavior |
| --- | --- |
| `start` | Admit inputs, persist the Task, and execute to the Candidate Scope pause |
| `resume` | Continue an existing Task using `--candidate-scope unchanged` |
| `run` | Start and resume with unchanged automatic scope selections; load the result summary by default |

```powershell
.\.venv\Scripts\python.exe backend/scripts/run_product_task.py --help
.\.venv\Scripts\python.exe backend/scripts/run_product_task.py run --help
```

Single-document Task IDs are `internal_dsur_qc`, `internal_ib_qc`, and `internal_csr_qc`; they accept `--source`. The implemented cross-document Task is `dsur_updated_ib_qc`, with `--source-a` for DSUR and `--source-b` for updated IB. Current source-language selection is `zh`.

CLI `run` does not reproduce interactive browser scope editing. Invoking execution commands uses the configured LLM provider.

### Flow-level CLI

[run_consistency_qc.py](scripts/run_consistency_qc.py) runs the installed Document Consistency QC Flow below Product Task ownership.

This development CLI accepts source paths for convenience and invokes neutral Request File Intake to build admitted source bindings before allocating the Flow. The installed Flow consumes those bindings; this CLI does not perform Product Task input admission or create Task-owned input storage.

```powershell
.\.venv\Scripts\python.exe backend/scripts/run_consistency_qc.py --help
```

Select `--capability internal_dsur|internal_ib|internal_csr|dsur_updated_ib`. One-slot capabilities take `--source`; the cross-document capability takes `--source-a` (DSUR) and `--source-b` (updated IB).

The default Candidate Scope policy is `automatic_continue`; `--candidate-scope-mode pause_at_candidate_scope` requests a resumable checkpoint. Relative source paths use the caller's working directory. The default artifact workspace is `backend/`; `--project-root` can override it.

## Stage Runners

These are standalone development/inspection runners for execution stages, phases, and reusable operations. Their presence here does not imply that every runner corresponds to a stage owned by the QC Flow. Product execution calls the shared Python contracts directly rather than invoking these runners as subprocesses.

Paths below are repository-root relative:

| Operation/stage group | Path |
| --- | --- |
| Request File Intake (used during Product Task source admission) | `backend/scripts/stage_runners/request_file_intake_runner.py` |
| Extract | `backend/scripts/stage_runners/extract_runner.py` |
| Prepare Analysis | `backend/scripts/stage_runners/prepare_analysis_runner.py` |
| Doc Meta | `backend/scripts/stage_runners/doc_meta_runner.py` |
| Filter | `backend/scripts/stage_runners/filter_runner.py` |
| Candidate Scope | `backend/scripts/stage_runners/candidate_scope_runner.py` |
| Filter Output Projection | `backend/scripts/stage_runners/filter_output_projection_runner.py` |
| Route | `backend/scripts/stage_runners/route_runner.py` |
| ESP prepare/assess/eligibility/assemble | `backend/scripts/stage_runners/evidence_source_preparation/aggregate_evidence/` |
| Comparison materialization/assessment/verification/inspection | `backend/scripts/stage_runners/evidence_comparison/clinical_trial_doc/clinical_safety/aggregate_evidence/` |

Use each runner's `--help` for its input artifacts and output options. Extract has `inspect`, `export`, and `validate` modes. The installed Comparison path includes assessment, verification, configured second-pass behavior, applicable consolidation, and finalization.

## Tools

| Tool | Purpose |
| --- | --- |
| [inspect_runs.py](scripts/tools/inspect_runs.py) | Browse recent runs, search recorded identities, or find document runs |
| [register_sample.py](scripts/tools/register_sample.py) | Register content-hashed sample snapshots; look up or show their records |
| [qc_report_runner.py](scripts/tools/qc_report_runner.py) | Produce report JSON, presentation JSON, or PDF development previews for a saved Task |
| [qc_report_pdf_qa.py](scripts/tools/qc_report_pdf_qa.py) | Inspect/rasterize representative PDF preview output for development QA |

Report preview defaults are `renders/qc_report/<task_run_id>/`, relative to the working directory; `--output` can override them. These development files do not provide product report archival.

## Runtime Data

Generated local execution data under `backend/runs/` is ignored by Git.

- `task_runs/<task_run_id>/`: Task identity, lifecycle, admitted input manifest, and Task-owned source files.
- `document_consistency_qc/<flow_run_id>/`: Flow lineage and participant/stage outputs.
- Stage directories: formal artifacts, operation summaries, and permitted debug metadata.
- Review/annotation records: saved review decisions, flags, notes, and source annotations.
- `upload_staging/`: Bridge-owned HTTP upload materialization/session records prior to Product Task admission.

Downstream readers follow recorded identities and artifact references, not the latest timestamp. Optional privacy mappings/audits and original inputs are local private data; they are not demo assets.

## Samples and Fixtures

Public/demo documents are in [samples/clinical_trial_doc](samples/clinical_trial_doc/), grouped by format, language, and clinical program. The current program contains reference CSR, IB, and DSUR documents, plus an error-simulation DSUR.

“Reference” identifies the sample role; it does not assert error-free content or clinical validation. The [root walkthrough](../README.md#try-the-bundled-sample) identifies the demo input.

Regression-only DOCX inputs live under [tests/fixtures/clinical_trial_doc](tests/fixtures/clinical_trial_doc/). Formal comparison regression payloads have a separate [fixture guide](tests/fixtures/evidence_comparison/clinical_safety/aggregate_evidence/README.md); they are not newly generated demo results.

## Optional Privacy

Privacy preprocessing is disabled by default. Omitting privacy input selects identity preparation, and the default HTTP/browser workflow does not require Paddle.

For optional UIE-based detection:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-privacy.txt
```

The manifest retains `paddlepaddle==2.6.2` and `paddlenlp==2.6.1` from the project's prior UIE setup. This optional version pair is not part of the default product environment, and broader platform compatibility is not currently claimed.

Product Task and Flow CLIs accept `--privacy-config` for one document, or both `--privacy-config-a` and `--privacy-config-b` for two documents. These JSON options are resolved under the installed clinical Prepare Analysis configuration; the formal fields are defined in [privacy invocation inputs](plugins/clinical_trial_doc/prepare_analysis/inputs.py).

Requested UIE resolves according to availability and existing fallback policy. The current lightweight local fallback returns no candidates and is not equivalent model-based entity detection. Privacy is not validated anonymization or guaranteed de-identification.

See the [privacy guide](privacy/README.md) for schema labels/detector policy and [Architecture](../ARCHITECTURE.md#optional-privacy) for private-artifact boundaries.

## Reporting

The product generates a PDF on demand from saved Task, Result, review, annotation, and configuration state. The HTTP download renders a consistent composed report and returns PDF bytes; it does not archive immutable report versions.

Current report composition is single-document. Backend DSUR ↔ updated-IB execution is implemented, but cross-document report composition and the complete cross-document Result UI are outside the current browser review experience.

Development previews/QA are separate from product downloads. There is no report version history or previously exported PDF history/download UI. The bundled PDF font and packaging requirements are described in the [font resource guide](renderers/qc_report/resources/fonts/README.md).

## Tests

After installing base and development requirements, run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -m "not live_llm"
```

Normal tests use injected mock/fake dependencies and guard against unintended live external-provider calls. Explicit `live_llm` tests are excluded by the command above.

## Backend Structure

| Package/path | Purpose |
| --- | --- |
| `application/` | Installed composition, use cases, and read models |
| `artifacts/` | Persisted schemas, identities, validation, and serialization |
| `bridge/` | HTTP request/response adaptation and upload transport |
| `capability/` | Static product-capability configurations |
| `core/` | Shared document parsing, structure, normalization, and source mechanisms |
| `execution_flow/` | Sequencing, checkpoints, and handoff orchestration |
| `llm/` | Model profiles, providers, execution configurations, and invocation metadata |
| `operations/` | Neutral execution/registry/handoff contracts |
| `plugins/` | Current clinical-domain behavior and prompt packages |
| `privacy/` | Detection, masking, mapping, and transformation mechanisms |
| `renderers/` | QC report PDF rendering/resources |
| `runtime/` | Loading, validation, allocation, persistence, and execution delegation |
| `steps/` | Reusable in-memory transforms |
| `task/` | Product input topology, lifecycle, and Task-owned composition |
| `scripts/` | Product/Flow entrypoints, stage runners, and tools |
| `tests/` | Regression tests, fixtures, and mock execution helpers |
