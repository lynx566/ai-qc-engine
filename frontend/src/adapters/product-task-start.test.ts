import { describe, expect, it } from 'vitest'

import { adaptProductTaskStartResult } from '@/adapters/product-task-start'

describe('adaptProductTaskStartResult', () => {
  it('maps task_run_id to taskRunId', () => {
    const result = adaptProductTaskStartResult({
      task_run_id: 'task_run_test',
    })

    expect(result.taskRunId).toBe('task_run_test')
  })
})
