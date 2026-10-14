import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'

const failureMessage = '报告生成失败，请稍后重试。'

function responseFilename(header: string | null): string {
  const encoded = header?.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)?.[1]?.trim()
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      // Fall back to filename.
    }
  }
  const plain = header?.match(/(?:^|;)\s*filename\s*=\s*(?:"([^"]*)"|([^;]+))/i)
  return plain?.[1]?.trim() || plain?.[2]?.trim() || '质控审查报告.pdf'
}

export async function downloadQcReport(taskRunId: string): Promise<{ blob: Blob; filename: string }> {
  try {
    const response = await fetch(`/api/clinical-trial-doc-qc/task-runs/${encodeURIComponent(taskRunId)}/qc-report`)
    if (!response.ok) {
      // Consume the existing JSON envelope without exposing backend internals.
      await response.json().catch(() => null)
      const message = ({
        404: '任务不存在或无法访问。',
        409: '报告状态正在更新，请稍后重试。',
        400: '当前质控结果暂无法生成报告。',
      } as Record<number, string>)[response.status] ?? failureMessage
      throw new DocumentConsistencyQcApiError(message)
    }
    return {
      blob: await response.blob(),
      filename: responseFilename(response.headers.get('Content-Disposition')),
    }
  } catch (error) {
    if (error instanceof DocumentConsistencyQcApiError) throw error
    throw new DocumentConsistencyQcApiError(failureMessage)
  }
}
