export class DocumentConsistencyQcApiError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'DocumentConsistencyQcApiError'
  }
}

export async function throwDocumentConsistencyQcResponseError(
  response: Response,
  fallbackMessage: string,
): Promise<never> {
  const body = (await response.json().catch(() => null)) as { message?: string } | null

  throw new DocumentConsistencyQcApiError(body?.message ?? fallbackMessage)
}
