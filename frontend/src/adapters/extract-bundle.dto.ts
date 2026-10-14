export type ExtractSentenceDto = {
  sentence_id: string
  raw_text: string
  normalized_text: string
}

export type ExtractBlockPresentationDto = {
  alignment?: 'left' | 'center' | 'right' | 'justify'
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

export type ExtractBlockMetaDto = {
  heading_level?: number
  raw_rows?: string[][]
  presentation?: ExtractBlockPresentationDto
  [key: string]: unknown
}

export type ExtractBlockDto = {
  block_id: string
  kind: string
  raw_text: string
  normalized_text: string
  doc_order_index: number | null
  heading_path: string[]
  sentences?: ExtractSentenceDto[]
  meta?: ExtractBlockMetaDto
  order?: number
}

export type ExtractBundleDto = {
  doc_id: string
  file_name: string
  display_name: string
  front_matter_blocks?: ExtractBlockDto[]
  content_blocks?: ExtractBlockDto[]
  table_blocks?: ExtractBlockDto[]
  format_blocks?: ExtractBlockDto[]
}
