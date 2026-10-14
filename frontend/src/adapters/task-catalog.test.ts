import { describe, expect, it } from 'vitest'

import { adaptTaskCatalog } from '@/adapters/task-catalog'

describe('adaptTaskCatalog', () => {
  it('maps API task catalog entries to frontend read model', () => {
    const catalog = adaptTaskCatalog({
      tasks: [
        {
          task_id: 'internal_dsur_qc',
          display_name: 'DSUR',
          description: 'desc',
          slots: [
            {
              slot_id: 'source',
              expected_document_type: 'dsur',
              upload_label: 'upload',
              help_text: 'help',
            },
          ],
        },
        {
          task_id: 'dsur_updated_ib_qc',
          display_name: 'Cross',
          description: 'cross',
          slots: [
            {
              slot_id: 'source_a',
              expected_document_type: 'dsur',
              upload_label: 'a',
              help_text: 'a',
            },
            {
              slot_id: 'source_b',
              expected_document_type: 'ib',
              upload_label: 'b',
              help_text: 'b',
            },
          ],
        },
      ],
    })

    expect(catalog.tasks).toHaveLength(2)
    expect(catalog.tasks[0]?.slots).toHaveLength(1)
    expect(catalog.tasks[1]?.slots.map((slot) => slot.slotId)).toEqual([
      'source_a',
      'source_b',
    ])
    expect(catalog.tasks[0]?.taskId).toBe('internal_dsur_qc')
  })
})
