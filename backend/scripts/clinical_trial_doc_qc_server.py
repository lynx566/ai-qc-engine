"""Run the local Clinical Trial Document QC HTTP bridge."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn

from bridge.clinical_trial_doc_qc.pipeline_logging import (
    configure_product_server_pipeline_logging,
)


def main() -> None:
    configure_product_server_pipeline_logging()
    uvicorn.run(
        "bridge.clinical_trial_doc_qc.app:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )


if __name__ == "__main__":
    main()
