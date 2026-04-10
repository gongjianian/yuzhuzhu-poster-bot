import request from './request'

export function getCurrent() {
  return request.get('/category-runs/current')
}

export function getBatchDetail(batchId: string) {
  return request.get(`/category-runs/${batchId}`)
}

export function listBatches(params?: { date?: string }) {
  return request.get('/category-runs', { params })
}

export function triggerPipeline() {
  return request.post('/category-runs/trigger')
}

export function stopPipeline() {
  return request.post('/category-runs/stop')
}
