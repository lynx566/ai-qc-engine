import { describe, expect, it } from 'vitest'

import {
  DocumentConsistencyQcApiError,
  throwDocumentConsistencyQcResponseError,
} from '@/api/document-consistency-qc-error'

async function captureResponseError(response: Response, fallbackMessage: string): Promise<unknown> {
  try {
    await throwDocumentConsistencyQcResponseError(response, fallbackMessage)
  } catch (error) {
    return error
  }
  throw new Error('Expected response error helper to throw')
}

describe('throwDocumentConsistencyQcResponseError', () => {
  it('throws a DocumentConsistencyQcApiError with the backend message', async () => {
    const error = await captureResponseError(
      new Response(JSON.stringify({ message: '具体错误' }), { status: 400 }),
      'fallback error',
    )

    expect(error).toBeInstanceOf(DocumentConsistencyQcApiError)
    expect(error).toMatchObject({ message: '具体错误' })
  })

  it('uses the fallback when valid JSON has no message', async () => {
    const error = await captureResponseError(
      new Response(JSON.stringify({ status: 'failed' }), { status: 400 }),
      'fallback error',
    )

    expect(error).toMatchObject({ message: 'fallback error' })
  })

  it('uses the fallback when the response body is not valid JSON', async () => {
    const error = await captureResponseError(
      new Response('not-json', { status: 500 }),
      'fallback error',
    )

    expect(error).toMatchObject({ message: 'fallback error' })
  })

  it('uses the fallback when the JSON body is null', async () => {
    const error = await captureResponseError(
      new Response('null', { status: 500 }),
      'fallback error',
    )

    expect(error).toMatchObject({ message: 'fallback error' })
  })
})
