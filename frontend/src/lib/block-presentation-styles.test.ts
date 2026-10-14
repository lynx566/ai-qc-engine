import { describe, expect, it } from 'vitest'

import {
  applyPresentationToClassName,
  mergePresentationVisuals,
  resolvePresentationAlignmentClassName,
  resolvePresentationStyle,
  resolveTocLevelIndentStyle,
} from '@/lib/block-presentation-styles'
import type { BlockPresentation } from '@/types/document-review'

describe('block-presentation-styles', () => {
  it('maps center alignment to text-center', () => {
    expect(
      resolvePresentationAlignmentClassName({ alignment: 'center' }),
    ).toBe('text-center')
  })

  it('maps typography and paragraph geometry to CSSProperties', () => {
    const presentation: BlockPresentation = {
      font_size_pt: 24,
      bold: true,
      italic: false,
      indent_first_line_pt: 21,
      line_spacing_multiple: 1.45,
      space_before_pt: 36,
      space_after_pt: 6,
    }

    expect(resolvePresentationStyle(presentation)).toEqual({
      fontSize: '24pt',
      fontWeight: 'bold',
      fontStyle: 'normal',
      textIndent: '21pt',
      lineHeight: '1.45',
      marginTop: '36pt',
      marginBottom: '6pt',
    })
  })

  it('respects explicit bold=false and italic=false', () => {
    expect(
      resolvePresentationStyle({
        bold: false,
        italic: false,
      }),
    ).toEqual({
      fontWeight: 'normal',
      fontStyle: 'normal',
    })
  })

  it('applies toc level indent without parsing style names', () => {
    expect(resolveTocLevelIndentStyle({ toc_level: 2 })).toEqual({
      paddingLeft: '12pt',
    })
    expect(resolveTocLevelIndentStyle({ toc_level: 3 })).toEqual({
      paddingLeft: '24pt',
    })
    expect(resolveTocLevelIndentStyle({ toc_level: 11 })).toBeUndefined()
    expect(resolveTocLevelIndentStyle({ toc_level: 21 })).toEqual({
      paddingLeft: '12pt',
    })
  })

  it('merges semantic class names with optional presentation overlays', () => {
    const result = applyPresentationToClassName('text-base leading-7', {
      alignment: 'center',
      font_size_pt: 10.5,
    })

    expect(result.className).toContain('text-base')
    expect(result.className).toContain('text-center')
    expect(result.style).toEqual({ fontSize: '10.5pt' })
  })

  it('returns empty overlays when presentation is missing', () => {
    expect(mergePresentationVisuals(undefined)).toEqual({
      className: undefined,
      style: undefined,
    })
  })
})
