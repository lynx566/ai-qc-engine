import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('ResultShell source annotation wiring', () => {
  it('loads source annotations in parallel with result and review state', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')

    expect(source).toContain('fetchSourceAnnotations')
    expect(source).toContain('createSourceHighlight')
    expect(source).toContain('createSourceComment')
    expect(source).toContain('patchSourceAnnotationContent')
    expect(source).toContain('deleteSourceAnnotation')
    expect(source).toContain('sourceAnnotations={sourceAnnotations}')
    expect(source).not.toContain('localStorage')
  })

  it('uses product wording for revision and comment actions', () => {
    const interactionSource = readFileSync(
      resolve(import.meta.dirname, 'source-document-interaction.tsx'),
      'utf8',
    )
    const toolbarSource = readFileSync(
      resolve(import.meta.dirname, 'source-selection-toolbar.tsx'),
      'utf8',
    )
    const popoverSource = readFileSync(
      resolve(import.meta.dirname, 'source-comment-popover.tsx'),
      'utf8',
    )
    const deleteActionSource = readFileSync(
      resolve(import.meta.dirname, 'source-mark-action.tsx'),
      'utf8',
    )

    expect(toolbarSource).toContain('修订')
    expect(toolbarSource).toContain('批注')
    expect(popoverSource).toContain('删除')
    expect(popoverSource).toContain("'保存'")
    expect(popoverSource).not.toContain('删除批注')
    expect(popoverSource).not.toContain('保存修改')
    expect(deleteActionSource).toContain("'删除标注'")
    expect(interactionSource).toContain('label="删除标注"')
    expect(toolbarSource).not.toContain('标记')
    expect(toolbarSource).not.toContain('高亮')
    expect(toolbarSource).not.toContain('取消高亮')
    expect(popoverSource).not.toContain('备注')
  })

  it('passes activeSourceAnnotationId into DocumentReader for navigator emphasis', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')

    expect(source).toContain('activeSourceAnnotationId={activeSourceAnnotationId}')
  })

  it('reconciles create/update by merge and individual delete by local removal', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')

    expect(source).toContain('mergeSourceAnnotation')
    expect(source).toContain('removeSourceAnnotationFromMap')
    expect(source).toContain('shouldReconcileCapturedSourceAnnotationCreate')
    expect(source).toContain('shouldReconcileCapturedSourceAnnotationMutation')
    expect(source).not.toContain('latestCreateCommentRequestRef')
    expect(source).not.toContain('latestCreateEditRequestRef')
    expect(source).not.toContain('latestCreateHighlightRequestRef')
    expect(source).not.toContain('setSourceAnnotations(nextState.annotationsById)')
  })

  it('resets annotation busy state when the active flow changes', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')
    const flowEffect = source.match(
      /useEffect\(\(\) => \{\s*activeFlowRunIdRef\.current = flowRunId[\s\S]*?\}, \[flowRunId\]\)/,
    )?.[0]

    expect(flowEffect).toBeTruthy()
    expect(flowEffect).toContain('setSavingAnnotationId(null)')
    expect(flowEffect).toContain('setActiveSourceAnnotationId(null)')
    expect(flowEffect).toContain('annotationMutationEpochRef.current += 1')
    expect(flowEffect).toContain('createSourceAnnotationMutationSession()')
    expect(source).toContain('captureSourceAnnotationMutation')
    expect(source).toContain('releaseCapturedSourceAnnotationMutation')
  })

  it('keeps new highlights inactive and activates newly created comments', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')
    const createHighlight = source.match(
      /const handleCreateHighlight = useCallback\([\s\S]*?\n  \)/,
    )?.[0]
    const createComment = source.match(/const handleCreateComment = useCallback\([\s\S]*?\n  \)/)?.[0]

    expect(createHighlight).toBeTruthy()
    expect(createComment).toBeTruthy()
    expect(createHighlight).not.toContain('setActiveSourceAnnotationId(created.annotationId)')
    expect(createComment).toContain('setActiveSourceAnnotationId(created.annotationId)')
  })
})
