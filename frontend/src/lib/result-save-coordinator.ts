/** Tracks existing persistence promises; never serializes or writes business data. */
export class ResultSaveCoordinator {
  private pending = new Set<Promise<unknown>>()
  private failed = new Set<string>()
  private latest = new Map<string, symbol>()
  private editors = new Set<() => void | Promise<void>>()

  track<T>(key: string, operation: Promise<T>): Promise<T> {
    const token = Symbol(key)
    this.latest.set(key, token)
    const tracked = operation.then((value) => {
      if (this.latest.get(key) === token) this.failed.delete(key)
      return value
    }, (error: unknown) => {
      this.failed.add(key)
      throw error
    }).finally(() => this.pending.delete(tracked))
    this.pending.add(tracked)
    // The caller still receives rejection; tracking itself creates no unhandled promise.
    void tracked.catch(() => {})
    return tracked
  }

  registerEditor(commit: () => void | Promise<void>): () => void {
    this.editors.add(commit)
    return () => { this.editors.delete(commit) }
  }

  async flush(): Promise<void> {
    const commits = Array.from(this.editors, (commit) => {
      try {
        return Promise.resolve(commit())
      } catch (error) {
        return Promise.reject(error)
      }
    })
    const results = await Promise.allSettled(commits)
    while (this.pending.size) await Promise.allSettled(Array.from(this.pending))
    if (this.failed.size || results.some(result => result.status === 'rejected')) {
      throw new Error('保存失败，暂无法导出报告。')
    }
  }
}
