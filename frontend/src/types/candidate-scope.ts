export type CandidateHeadingKey = {
  docId: string
  filterJobId: string
  anchorBlockId: string
}

export type CandidateHeading = CandidateHeadingKey & {
  title: string
  headingPath: string[]
  level: number
  docOrderIndex: number
}

export type DocumentTypeDiagnostic = {
  status: 'match' | 'mismatch' | 'uncertain'
  expectedDocumentType: 'DSUR' | 'CSR' | 'IB'
  reason?: string
}

export type CandidateScopeSlotState = {
  slotId: string
  docId: string
  automaticAnchorBlockIds: string[]
  currentAnchorBlockIds: string[]
  headings: CandidateHeading[]
  documentTypeDiagnostic?: DocumentTypeDiagnostic
}

export type CandidateScopeContentDomainGroup = {
  contentDomainId: string
  displayLabel: string
  filterJobIds: string[]
}

export type CandidateScopeFlowState = {
  flowId: string
  flowRunId: string
  capabilityId: string
  capabilityTitle: string
  flowStatus: string
  canResume: boolean
  contentDomainGroups: CandidateScopeContentDomainGroup[]
  slots: CandidateScopeSlotState[]
}

export type CandidateScopeJobSelection = {
  filterJobId: string
  anchorBlockIds: string[]
}

export type CandidateScopeSlotDecision = {
  slotId: string
  candidateScope: CandidateScopeJobSelection[]
}

export type CandidateScopeNextRequest = {
  flowRunId: string
  slotDecisions: CandidateScopeSlotDecision[]
}

export type CandidateScopeNextResponse = {
  status: 'ready'
  flowId: string
  flowRunId: string
  flowStatus: string
  pausedAtCandidateScope: boolean
  pausedSlotIds: string[]
  completed: boolean
}

export type SlotReviewState = {
  currentSelected: Set<string>
  draftSelected: Set<string>
  isEditing: boolean
}

export type CandidateSidebarLeaf = {
  kind: 'leaf'
  anchorBlockId: string
  title: string
  scrollTargetBlockId: string
}

export type CandidateSidebarGroup = {
  kind: 'group'
  title: string
  childCount: number
  scrollTargetBlockId: string
  children: CandidateSidebarLeaf[]
}

export type CandidateSidebarEntry = CandidateSidebarLeaf | CandidateSidebarGroup

export type CandidateContentDomainSection = {
  kind: 'domain'
  contentDomainId: string
  domainLabel: string
  chapterCount: number
  headings: CandidateHeading[]
  candidateAnchorBlockIds: string[]
}

export type CandidateChapterSection = CandidateContentDomainSection
