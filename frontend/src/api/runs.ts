import request from './request'

export function getRuns(params?: {
  page?: number
  page_size?: number
  status?: string
  product_name?: string
  date?: string
}) {
  return request.get('/runs', { params })
}

export function getRunDetail(runId: string) {
  return request.get(`/runs/${runId}`)
}
