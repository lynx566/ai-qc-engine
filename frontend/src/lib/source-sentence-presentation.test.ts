import { describe, expect, it } from 'vitest'

import {
  clipHighlightsToSourceBody,
  splitSentenceTerminalPunctuation,
} from '@/lib/source-sentence-presentation'
import type { SourceAnnotation } from '@/types/source-annotation'

const anchor = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0002',
  sentenceId: 'C0002:S001',
}

describe('splitSentenceTerminalPunctuation', () => {
  it('splits Chinese period', () => {
    expect(splitSentenceTerminalPunctuation('接受至少一次VT8802治疗。')).toEqual({
      sourceBody: '接受至少一次VT8802治疗',
      terminalPunctuation: '。',
    })
  })

  it('splits semicolon and exclamation', () => {
    expect(splitSentenceTerminalPunctuation('注意情况；')).toEqual({
      sourceBody: '注意情况',
      terminalPunctuation: '；',
    })
    expect(splitSentenceTerminalPunctuation('存在风险！')).toEqual({
      sourceBody: '存在风险',
      terminalPunctuation: '！',
    })
  })

  it('splits question mark', () => {
    expect(splitSentenceTerminalPunctuation('是否有问题？')).toEqual({
      sourceBody: '是否有问题',
      terminalPunctuation: '？',
    })
  })

  it('keeps text without terminal punctuation intact', () => {
    expect(splitSentenceTerminalPunctuation('感染性肺炎2例')).toEqual({
      sourceBody: '感染性肺炎2例',
      terminalPunctuation: '',
    })
  })
})

describe('clipHighlightsToSourceBody', () => {
  it('clips highlight ranges to source body before punctuation', () => {
    const highlight: SourceAnnotation = {
      annotationId: 'ann_hl',
      anchor,
      kind: 'highlight',
      range: { startOffset: 0, endOffset: 4 },
      createdAt: '2026-09-13T00:00:00Z',
      updatedAt: '2026-09-13T00:00:00Z',
    }

    const clipped = clipHighlightsToSourceBody([highlight], '感染性肺炎2例')
    expect(clipped[0]?.range).toEqual({ startOffset: 0, endOffset: 4 })
  })
})
