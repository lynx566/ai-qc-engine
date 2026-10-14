export type DocumentBlockKind =
  | 'heading'
  | 'paragraph'
  | 'list_item'
  | 'toc'
  | 'table_caption'
  | 'table_note'
  | 'table'

export type SentenceView = {
  sentenceId: string
  rawText: string
  normalizedText: string
}

export type TableView = {
  rows: string[][]
}

export type BlockPresentationAlignment =
  | 'left'
  | 'center'
  | 'right'
  | 'justify'

export type BlockPresentation = {
  alignment?: BlockPresentationAlignment
  font_size_pt?: number
  bold?: boolean
  italic?: boolean
  indent_first_line_pt?: number
  indent_left_pt?: number
  line_spacing_multiple?: number
  space_before_pt?: number
  space_after_pt?: number
  toc_level?: number
}

export type DocumentBlock = {
  blockId: string
  sourceBlockId: string
  kind: DocumentBlockKind
  docOrderIndex: number
  headingLevel?: 1 | 2 | 3 | 4 | 5 | 6 | 7
  headingPath: string[]
  displayText?: string
  sentences?: SentenceView[]
  table?: TableView
  presentation?: BlockPresentation
}

export type DocumentView = {
  docId: string
  fileName: string
  displayName: string
  blocks: DocumentBlock[]
}

export type FilterSection = {
  sectionId: string
  title: string
  anchorBlockId: string
  blockIds: string[]
}

export type FilterOverlay = {
  filterLabel: string
  selectedBlockIds: string[]
  sections: FilterSection[]
}

export type ClinicalSafetyReviewFixture = {
  document: DocumentView
  overlay: FilterOverlay
}
