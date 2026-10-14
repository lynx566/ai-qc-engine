export function blockDomId(blockId: string) {
  return `document-block-${blockId}`
}

export function sentenceDomId(docId: string, sentenceId: string) {
  return `document-sentence-${docId}:${sentenceId}`
}
