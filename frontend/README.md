# Frontend

Browser UI for the current **Clinical Trial Document QC** product in **AI QC Engine**. It provides upload/setup, evidence-linked Result review, Full Document navigation, saved review actions, and single-document PDF export.

The currently implemented QC function is **Writing Accuracy & Consistency Review（撰写准确性与一致性核查）**, with **Investigational Product Clinical Safety** as its current analysis scope.

See the [project README](../README.md) for the primary browser Quick Start and [Architecture](../ARCHITECTURE.md) for system boundaries.

## Prerequisites

- **Node.js 24.x** is recommended for the current locked frontend toolchain.
- npm.
- The backend product HTTP server running at `http://127.0.0.1:8765`.

The UI uses React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui components, and lucide-react.

## Local Development

Start the backend in a separate terminal using the [backend server instructions](../backend/README.md#product-http-server).

From `frontend/`:

```powershell
npm install
npm run dev
```

Vite binds to `127.0.0.1` and normally serves `http://127.0.0.1:5173`. If that port is occupied, use the URL Vite prints. The port is not configured as strict.

## Backend Integration

Client requests use relative `/api` paths. [vite.config.ts](vite.config.ts) proxies them to `http://127.0.0.1:8765`.

- `/api/clinical-trial-doc-qc/...` exposes product catalog, Task, and report operations.
- `/api/document-consistency-qc/...` exposes Flow-level setup, Result, review, and source operations.
- API modules handle transport; adapters normalize backend DTOs into frontend types.
- The backend owns Task/Flow execution, LLM calls, result persistence, and review/annotation persistence.

The Vite proxy is part of local development configuration; a built static frontend needs appropriate API routing in its serving environment.

## Product Journey

```text
Launcher / Upload → QC Setup → execute / resume → Result
→ Full Document / evidence review → saved reviewer actions → PDF export
```

1. Select a Product Task and upload its document inputs.
2. Product Start prepares candidate chapter scopes and opens QC Setup.
3. Inspect/apply scope selections, then continue execution.
4. Review the finding queue and linked source evidence in Result.
5. Confirm or ignore findings, flag items, and save notes; inspect the parsed Full Document and add source annotations.
6. Export the single-document PDF report after pending review state and annotations are saved.

Finding labels `fail` / `need_review` are separate from reviewer decisions. Full Document is a parsed-document review surface, not an editor for the original Word file.

## Current Boundaries

The current **Writing Accuracy & Consistency Review** supports single-document DSUR, IB, and CSR review in the browser. Backend DSUR ↔ updated-IB execution is also implemented, and launcher/setup can represent multi-document inputs.

The current Result workspace is intentionally focused on single-document review. A complete cross-document Result UI and A/B evidence review are not implemented; current PDF report composition is single-document.

PDF export is implemented and generated on demand from saved state. There is no immutable report archival, export version history, or previously exported PDF history/download UI.

Current browser workflows focus on Chinese `.docx` clinical-trial documents and the currently implemented **Investigational Product Clinical Safety** analysis scope. Privacy preprocessing is optional/default off; the browser does not expose a privacy-configuration workflow.

## Commands and Tests

Run from `frontend/`:

```powershell
npm run dev
npm test
npm run build
npm run lint
```

| Command | Purpose |
| --- | --- |
| `npm run dev` | Vite development server with API proxy |
| `npm test` | Vitest in run mode |
| `npm run build` | TypeScript project build and Vite production bundle |
| `npm run lint` | Oxlint checks |

[vitest.config.ts](vitest.config.ts) discovers `src/**/*.test.ts` with Node as the default environment. DOM-oriented tests also exercise UI interactions using Happy DOM. Frontend tests do not run the backend QC pipeline.

## Source Structure

| Path | Purpose |
| --- | --- |
| `src/App.tsx` | Browser route composition |
| `src/pages/` | Launcher and Task-owned setup/Result pages |
| `src/components/` | Launcher, QC Setup, review, and shared UI components |
| `src/api/` | API calls and transport error handling |
| `src/adapters/` | Backend DTO-to-frontend-model normalization |
| `src/lib/` | Review/navigation helpers and React hooks |
| `src/types/` | Product, Flow, document, review, and annotation types |
| `src/fixtures/`, `src/test-fixtures/` | Supporting fixture data |
