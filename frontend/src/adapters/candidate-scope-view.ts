import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'
import { composeDocumentBlockId } from '@/adapters/extract-document'
import type {
  CandidateChapterSection,
  CandidateHeading,
  CandidateScopeContentDomainGroup,
  CandidateScopeFlowState,
  CandidateScopeSlotState,
  CandidateSidebarEntry,
  DocumentTypeDiagnostic,
} from '@/types/candidate-scope'

type ApiCandidateHeading = {
  doc_id: string
  filter_job_id: string
  anchor_block_id: string
  title: string
  heading_path: string[]
  level: number
  doc_order_index: number
}

type ApiCandidateScopeSlotState = {
  slot_id: string
  doc_id: string
  automatic_anchor_block_ids: string[]
  current_anchor_block_ids: string[]
  headings: ApiCandidateHeading[]
  document_type_diagnostic?: {
    status: DocumentTypeDiagnostic['status']
    expected_document_type: DocumentTypeDiagnostic['expectedDocumentType']
    reason?: string
  } | null
}

type ApiCandidateScopeContentDomainGroup = {
  content_domain_id: string
  display_label: string
  filter_job_ids: string[]
}

type ApiCandidateScopeState = {
  flow_id: string
  flow_run_id: string
  capability_id: string
  capability_title: string
  flow_status: string
  can_resume: boolean
  content_domain_groups: ApiCandidateScopeContentDomainGroup[]
  slots: ApiCandidateScopeSlotState[]
}

export function adaptCandidateScopeState(payload: ApiCandidateScopeState): CandidateScopeFlowState {
  if (!Array.isArray(payload.content_domain_groups)) {
    throw new DocumentConsistencyQcApiError('candidate scope state is missing content_domain_groups')
  }

  return {
    flowId: payload.flow_id,
    flowRunId: payload.flow_run_id,
    capabilityId: payload.capability_id,
    capabilityTitle: payload.capability_title,
    flowStatus: payload.flow_status,
    canResume: payload.can_resume,
    contentDomainGroups: payload.content_domain_groups.map(adaptContentDomainGroup),
    slots: payload.slots.map(adaptCandidateScopeSlot),
  }
}

function adaptContentDomainGroup(
  raw: ApiCandidateScopeContentDomainGroup,
): CandidateScopeContentDomainGroup {
  return {
    contentDomainId: raw.content_domain_id,
    displayLabel: raw.display_label,
    filterJobIds: [...raw.filter_job_ids],
  }
}

function adaptCandidateScopeSlot(raw: ApiCandidateScopeSlotState): CandidateScopeSlotState {
  return {
    slotId: raw.slot_id,
    docId: raw.doc_id,
    automaticAnchorBlockIds: [...raw.automatic_anchor_block_ids],
    currentAnchorBlockIds: [...raw.current_anchor_block_ids],
    headings: raw.headings.map(adaptCandidateHeading),
    ...(raw.document_type_diagnostic ? {
      documentTypeDiagnostic: {
        status: raw.document_type_diagnostic.status,
        expectedDocumentType: raw.document_type_diagnostic.expected_document_type,
        reason: raw.document_type_diagnostic.reason,
      },
    } : {}),
  }
}

function adaptCandidateHeading(raw: ApiCandidateHeading): CandidateHeading {
  if (!Number.isInteger(raw.doc_order_index) || raw.doc_order_index < 0) {
    throw new DocumentConsistencyQcApiError(
      `invalid candidate heading doc_order_index for ${raw.anchor_block_id}`,
    )
  }

  return {
    docId: raw.doc_id,
    filterJobId: raw.filter_job_id,
    anchorBlockId: raw.anchor_block_id,
    title: raw.title,
    headingPath: [...raw.heading_path],
    level: raw.level,
    docOrderIndex: raw.doc_order_index,
  }
}

function compareDocOrderIndex(left: number, right: number): number {
  return left - right
}

function sortHeadingsByDocOrder(headings: CandidateHeading[]): CandidateHeading[] {
  return [...headings].sort((left, right) =>
    compareDocOrderIndex(left.docOrderIndex, right.docOrderIndex),
  )
}

function findGroupParentHeading(
  slotState: CandidateScopeSlotState,
  groupTitle: string,
): CandidateHeading | undefined {
  return slotState.headings.find(
    (heading) =>
      heading.level === 1 &&
      (heading.headingPath[0] === groupTitle || heading.title === groupTitle),
  )
}

function groupEntryDocOrderIndex(
  slotState: CandidateScopeSlotState,
  groupTitle: string,
  children: CandidateHeading[],
): number {
  const parent = findGroupParentHeading(slotState, groupTitle)
  if (parent !== undefined) {
    return parent.docOrderIndex
  }
  return Math.min(...children.map((child) => child.docOrderIndex))
}

export function buildSidebarEntries(
  slotState: CandidateScopeSlotState,
  selectedAnchors: Set<string>,
): CandidateSidebarEntry[] {
  const docId = slotState.docId
  const selected = slotState.headings.filter((heading) =>
    selectedAnchors.has(heading.anchorBlockId),
  )

  const topLevel = selected.filter((heading) => heading.level === 1)
  const nested = selected.filter((heading) => heading.level > 1)

  const groupedNested = new Map<string, CandidateHeading[]>()
  for (const heading of nested) {
    const groupKey = heading.headingPath[0] ?? heading.title
    const bucket = groupedNested.get(groupKey) ?? []
    bucket.push(heading)
    groupedNested.set(groupKey, bucket)
  }

  const entries: Array<{ entry: CandidateSidebarEntry; docOrderIndex: number }> = []

  for (const heading of topLevel) {
    entries.push({
      docOrderIndex: heading.docOrderIndex,
      entry: {
        kind: 'leaf',
        anchorBlockId: heading.anchorBlockId,
        title: heading.title,
        scrollTargetBlockId: composeDocumentBlockId(docId, heading.anchorBlockId),
      },
    })
  }

  for (const [groupTitle, children] of groupedNested) {
    if (children.length === 1 && children[0]!.level === 1) {
      continue
    }
    const orderedChildren = sortHeadingsByDocOrder(children)
    entries.push({
      docOrderIndex: groupEntryDocOrderIndex(slotState, groupTitle, orderedChildren),
      entry: {
        kind: 'group',
        title: groupTitle,
        childCount: orderedChildren.length,
        scrollTargetBlockId: composeDocumentBlockId(
          docId,
          orderedChildren[0]!.anchorBlockId,
        ),
        children: orderedChildren.map((child) => ({
          kind: 'leaf' as const,
          anchorBlockId: child.anchorBlockId,
          title: child.title,
          scrollTargetBlockId: composeDocumentBlockId(docId, child.anchorBlockId),
        })),
      },
    })
  }

  entries.sort((left, right) =>
    compareDocOrderIndex(left.docOrderIndex, right.docOrderIndex),
  )
  return entries.map((item) => item.entry)
}

function selectedAnchorsForContentDomain(
  slotState: CandidateScopeSlotState,
  selectedAnchors: Set<string>,
  filterJobIds: ReadonlySet<string>,
): Set<string> {
  const selected = new Set<string>()
  for (const heading of slotState.headings) {
    if (
      filterJobIds.has(heading.filterJobId) &&
      selectedAnchors.has(heading.anchorBlockId)
    ) {
      selected.add(heading.anchorBlockId)
    }
  }
  return selected
}

function minDocOrderIndexForHeadings(headings: CandidateHeading[]): number {
  if (headings.length === 0) {
    return Number.MAX_SAFE_INTEGER
  }
  return Math.min(...headings.map((heading) => heading.docOrderIndex))
}

function assertSelectedHeadingsAreGrouped(
  slotState: CandidateScopeSlotState,
  selectedAnchors: Set<string>,
  contentDomainGroups: CandidateScopeContentDomainGroup[],
): void {
  const groupedFilterJobIds = new Set(
    contentDomainGroups.flatMap((group) => group.filterJobIds),
  )
  const ungrouped = slotState.headings.filter(
    (heading) =>
      selectedAnchors.has(heading.anchorBlockId) &&
      !groupedFilterJobIds.has(heading.filterJobId),
  )
  if (ungrouped.length > 0) {
    const sample = ungrouped[0]!
    throw new DocumentConsistencyQcApiError(
      `candidate heading ${sample.anchorBlockId} with filter job ${sample.filterJobId} is not assigned to any content domain group`,
    )
  }
}

export function buildCandidateChapterSections(
  slotState: CandidateScopeSlotState,
  selectedAnchors: Set<string>,
  contentDomainGroups: CandidateScopeContentDomainGroup[],
): CandidateChapterSection[] {
  if (contentDomainGroups.length === 0) {
    throw new DocumentConsistencyQcApiError('candidate scope state has no content domain groups')
  }

  assertSelectedHeadingsAreGrouped(slotState, selectedAnchors, contentDomainGroups)

  const sections: Array<{ section: CandidateChapterSection; order: number }> = []

  for (const group of contentDomainGroups) {
    const filterJobIds = new Set(group.filterJobIds)
    const domainHeadings = sortHeadingsByDocOrder(
      slotState.headings.filter((heading) => filterJobIds.has(heading.filterJobId)),
    )
    if (domainHeadings.length === 0) {
      continue
    }

    const selectedForDomain = selectedAnchorsForContentDomain(
      slotState,
      selectedAnchors,
      filterJobIds,
    )

    sections.push({
      order: minDocOrderIndexForHeadings(domainHeadings),
      section: {
        kind: 'domain',
        contentDomainId: group.contentDomainId,
        domainLabel: group.displayLabel,
        chapterCount: selectedForDomain.size,
        headings: domainHeadings,
        candidateAnchorBlockIds: [...selectedForDomain],
      },
    })
  }

  sections.sort((left, right) => left.order - right.order)
  return sections.map((item) => item.section)
}
