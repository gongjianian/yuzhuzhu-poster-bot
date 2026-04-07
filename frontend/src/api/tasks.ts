import request from './request'

export function getTasks(params?: { status?: string }) {
  return request.get('/tasks', { params })
}

export function triggerSingle(recordId: string) {
  return request.post(`/tasks/${recordId}/trigger`)
}

export function triggerBatch(recordIds: string[]) {
  return request.post('/tasks/batch-trigger', recordIds)
}
