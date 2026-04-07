import request from './request'

export function getLogs(params: { date: string; keyword?: string; level?: string }) {
  return request.get('/logs', { params })
}
