import request from './request'

export function getStatsSummary(params?: { date?: string }) {
  return request.get('/stats/summary', { params })
}

export function getStatsTrend(params?: { days?: number }) {
  return request.get('/stats/trend', { params })
}
