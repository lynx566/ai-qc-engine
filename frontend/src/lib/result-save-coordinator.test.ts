import { describe, expect, it } from 'vitest'
import { ResultSaveCoordinator } from '@/lib/result-save-coordinator'

function deferred() {
  let resolve!: () => void
  let reject!: (error: Error) => void
  const promise = new Promise<void>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

describe('Result export save boundary', () => {
  it('commits active editors before waiting for all review and annotation saves', async () => {
    const coordinator = new ResultSaveCoordinator()
    const review = deferred(), annotation = deferred(), draft = deferred()
    const order: string[] = []
    coordinator.track('review:F1', review.promise)
    coordinator.track('annotation:A1', annotation.promise)
    coordinator.registerEditor(() => {
      order.push('commit draft')
      return coordinator.track('note:F2', draft.promise)
    })
    const exporting = coordinator.flush().then(() => order.push('report request'))
    expect(order).toEqual(['commit draft'])
    review.resolve(); annotation.resolve()
    await Promise.resolve()
    expect(order).not.toContain('report request')
    draft.resolve()
    await exporting
    expect(order).toEqual(['commit draft', 'report request'])
  })

  it('blocks export after any failed save until that save is successfully retried', async () => {
    const coordinator = new ResultSaveCoordinator()
    const failed = coordinator.track('review:F1', Promise.reject(new Error('failed save')))
    await expect(failed).rejects.toThrow('failed save')
    await coordinator.track('annotation:A1', Promise.resolve())
    await expect(coordinator.flush()).rejects.toThrow()
    await coordinator.track('review:F1', Promise.resolve())
    await expect(coordinator.flush()).resolves.toBeUndefined()
  })

  it('awaits saves added while an earlier save is settling', async () => {
    const coordinator = new ResultSaveCoordinator()
    const first = deferred(), second = deferred()
    const pending = coordinator.track('first', first.promise)
    void pending.then(() => coordinator.track('second', second.promise))
    let flushed = false
    const flush = coordinator.flush().then(() => { flushed = true })
    first.resolve()
    await Promise.resolve(); await Promise.resolve()
    expect(flushed).toBe(false)
    second.resolve()
    await flush
    expect(flushed).toBe(true)
  })

  it('does not commit an editor after it is explicitly closed', async () => {
    const coordinator = new ResultSaveCoordinator()
    const close = coordinator.registerEditor(() => { throw new Error('closed draft') })
    close()
    await expect(coordinator.flush()).resolves.toBeUndefined()
  })

  it('does not let an older save success clear a newer failure for the same target', async () => {
    const coordinator = new ResultSaveCoordinator()
    const old = deferred(), latest = deferred()
    const a = coordinator.track('review:F1', old.promise)
    const b = coordinator.track('review:F1', latest.promise)
    latest.reject(new Error('latest failed'))
    await expect(b).rejects.toThrow()
    old.resolve(); await a
    await expect(coordinator.flush()).rejects.toThrow()
  })
})
