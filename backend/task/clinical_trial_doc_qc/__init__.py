"""Clinical-trial document QC Product Task domain."""

from task.clinical_trial_doc_qc.catalog import (
    build_product_task_catalog,
    product_task_catalog_entry_to_mapping,
    product_task_catalog_to_mapping,
)
from task.clinical_trial_doc_qc.catalog_read_model import (
    ProductTaskCatalogEntry,
    ProductTaskInputSlotCatalogEntry,
)
from task.clinical_trial_doc_qc.definitions import (
    PRODUCT_TASK_DEFINITION_BY_ID,
    PRODUCT_TASK_DEFINITIONS,
    ProductTaskDefinition,
    ProductTaskInputSlot,
)
from task.clinical_trial_doc_qc.installation import (
    INSTALLED_PRODUCT_TASK_BY_ID,
    INSTALLED_PRODUCT_TASKS,
    InstalledChildFlowBinding,
    InstalledProductTask,
    TaskInputToFlowParticipantBinding,
    validate_installed_product_task_installation,
    validate_installed_product_task_installations,
)
from task.clinical_trial_doc_qc.presentation import (
    PRODUCT_TASK_PRESENTATION_BY_ID,
    ProductTaskInputSlotPresentationMetadata,
    ProductTaskPresentationMetadata,
    validate_product_task_presentation_registry,
)
from task.clinical_trial_doc_qc.start import (
    PlannedProductTaskStart,
    StartInstalledProductTaskResult,
    plan_installed_product_task_start,
    product_task_start_result_to_mapping,
    start_installed_product_task,
    start_installed_product_task_result_to_mapping,
    validate_installed_task_start_intent,
)
from task.clinical_trial_doc_qc.start_resolution import (
    DOCUMENT_CONSISTENCY_QC_INSTALLED_FLOW_ID,
    ResolvedInstalledChildFlow,
    ResolvedInstalledTaskStart,
    resolve_installed_task_start,
)
from task.clinical_trial_doc_qc.task_ids import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INTERNAL_CSR_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
    INTERNAL_IB_QC_TASK_ID,
)
from task.clinical_trial_doc_qc.task_input_binding import (
    bind_task_inputs_to_child_flow_participants,
    bind_task_slot_values_to_flow_participants,
)
from task.clinical_trial_doc_qc.task_run_read import (
    TaskRunFlowRefRecord,
    TaskRunPageContext,
    TaskRunPageReadError,
    TaskRunPageReadNotFoundError,
    TaskRunPageReadUnknownTaskIdError,
    load_task_run_page_context,
    task_run_page_context_to_mapping,
)

__all__ = [
    "DOCUMENT_CONSISTENCY_QC_INSTALLED_FLOW_ID",
    "DSUR_UPDATED_IB_QC_TASK_ID",
    "INSTALLED_PRODUCT_TASKS",
    "INSTALLED_PRODUCT_TASK_BY_ID",
    "INTERNAL_CSR_QC_TASK_ID",
    "INTERNAL_DSUR_QC_TASK_ID",
    "INTERNAL_IB_QC_TASK_ID",
    "PRODUCT_TASK_DEFINITIONS",
    "PRODUCT_TASK_DEFINITION_BY_ID",
    "PRODUCT_TASK_PRESENTATION_BY_ID",
    "InstalledChildFlowBinding",
    "InstalledProductTask",
    "PlannedProductTaskStart",
    "ProductTaskCatalogEntry",
    "ProductTaskDefinition",
    "ProductTaskInputSlot",
    "ProductTaskInputSlotCatalogEntry",
    "ProductTaskInputSlotPresentationMetadata",
    "ProductTaskPresentationMetadata",
    "ResolvedInstalledChildFlow",
    "ResolvedInstalledTaskStart",
    "StartInstalledProductTaskResult",
    "TaskInputToFlowParticipantBinding",
    "TaskRunFlowRefRecord",
    "TaskRunPageContext",
    "TaskRunPageReadError",
    "TaskRunPageReadNotFoundError",
    "TaskRunPageReadUnknownTaskIdError",
    "bind_task_inputs_to_child_flow_participants",
    "bind_task_slot_values_to_flow_participants",
    "build_product_task_catalog",
    "load_task_run_page_context",
    "plan_installed_product_task_start",
    "product_task_start_result_to_mapping",
    "product_task_catalog_entry_to_mapping",
    "product_task_catalog_to_mapping",
    "resolve_installed_task_start",
    "start_installed_product_task",
    "start_installed_product_task_result_to_mapping",
    "task_run_page_context_to_mapping",
    "validate_installed_product_task_installation",
    "validate_installed_product_task_installations",
    "validate_installed_task_start_intent",
    "validate_product_task_presentation_registry",
]
