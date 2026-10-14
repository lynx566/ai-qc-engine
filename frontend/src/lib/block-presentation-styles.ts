import type { CSSProperties } from 'react'

import type { BlockPresentation } from '@/types/document-review'
import { normalizeTocOutlineLevel } from '@/lib/toc-entry'
import { cn } from '@/lib/utils'

const ALIGNMENT_CLASS_NAMES: Record<
  NonNullable<BlockPresentation['alignment']>,
  string
> = {
  left: 'text-left',
  center: 'text-center',
  right: 'text-right',
  justify: 'text-justify',
}

const TOC_LEVEL_INDENT_PT = 12

export function resolvePresentationAlignmentClassName(
  presentation?: BlockPresentation,
): string | undefined {
  if (!presentation?.alignment) {
    return undefined
  }

  return ALIGNMENT_CLASS_NAMES[presentation.alignment]
}

export function resolvePresentationStyle(
  presentation?: BlockPresentation,
): CSSProperties | undefined {
  if (!presentation) {
    return undefined
  }

  const style: CSSProperties = {}

  if (presentation.font_size_pt !== undefined) {
    style.fontSize = `${presentation.font_size_pt}pt`
  }

  if (presentation.bold === true) {
    style.fontWeight = 'bold'
  } else if (presentation.bold === false) {
    style.fontWeight = 'normal'
  }

  if (presentation.italic === true) {
    style.fontStyle = 'italic'
  } else if (presentation.italic === false) {
    style.fontStyle = 'normal'
  }

  if (presentation.indent_first_line_pt !== undefined) {
    style.textIndent = `${presentation.indent_first_line_pt}pt`
  }

  if (presentation.indent_left_pt !== undefined) {
    style.marginLeft = `${presentation.indent_left_pt}pt`
  }

  if (presentation.line_spacing_multiple !== undefined) {
    style.lineHeight = String(presentation.line_spacing_multiple)
  }

  if (presentation.space_before_pt !== undefined) {
    style.marginTop = `${presentation.space_before_pt}pt`
  }

  if (presentation.space_after_pt !== undefined) {
    style.marginBottom = `${presentation.space_after_pt}pt`
  }

  return Object.keys(style).length > 0 ? style : undefined
}

export function resolveTocLevelIndentStyle(
  presentation?: BlockPresentation,
): CSSProperties | undefined {
  const outlineLevel = normalizeTocOutlineLevel(presentation?.toc_level)
  if (outlineLevel <= 1) {
    return undefined
  }

  const indentPt = (outlineLevel - 1) * TOC_LEVEL_INDENT_PT
  if (indentPt <= 0) {
    return undefined
  }

  return { paddingLeft: `${indentPt}pt` }
}

export function mergePresentationVisuals(
  presentation: BlockPresentation | undefined,
  options?: { includeTocLevelIndent?: boolean },
): { className?: string; style?: CSSProperties } {
  const alignmentClassName = resolvePresentationAlignmentClassName(presentation)
  const style = {
    ...resolvePresentationStyle(presentation),
    ...(options?.includeTocLevelIndent
      ? resolveTocLevelIndentStyle(presentation)
      : undefined),
  }

  const hasStyle = Object.keys(style).length > 0

  return {
    className: alignmentClassName,
    style: hasStyle ? style : undefined,
  }
}

export function applyPresentationToClassName(
  semanticClassName: string,
  presentation?: BlockPresentation,
  options?: { includeTocLevelIndent?: boolean },
): { className: string; style?: CSSProperties } {
  const visuals = mergePresentationVisuals(presentation, options)

  return {
    className: cn(semanticClassName, visuals.className),
    style: visuals.style,
  }
}
