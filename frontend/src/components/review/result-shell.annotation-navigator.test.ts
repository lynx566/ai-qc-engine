import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('ResultShell annotation navigator wiring', () => {
  it('builds split revision/comment navigation sequences and toolbar', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')

    expect(source).toContain('buildRevisionNavigationSequence')
    expect(source).toContain('buildCommentNavigationSequence')
    expect(source).toContain('SourceAnnotationNavigatorControls')
    expect(source).toContain('data-document-annotation-toolbar="true"')
    expect(source).not.toMatch(/sourceAnnotationSequence\.length\s*>\s*0\s*\?/)
    expect(source).not.toContain('buildSourceAnnotationNavigationSequence')
    expect(source).not.toContain('onNavigateSourceAnnotation')
    expect(source).toContain('activeSourceAnnotationId')
    expect(source).toContain('scrollToSourceAnnotationElement')
    expect(source).toContain('onSourceAnnotationActivate')
    expect(source).toContain('setFocusedEvidenceLocationKey(null)')
    expect(source).not.toMatch(
      /navigateToSourceAnnotation[\s\S]*sentenceNavigationFocusUpdate/,
    )
    expect(source).toContain('activeSourceAnnotationId={activeSourceAnnotationId}')
    expect(source).toContain('onClearActiveSourceAnnotation={onClearActiveSourceAnnotation}')
    expect(source).toContain('clearActiveSourceAnnotation')
  })
})
