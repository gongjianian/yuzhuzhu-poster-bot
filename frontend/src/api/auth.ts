import request from './request'

export function login(data: Record<string, string>) {
  return request.post('/auth/login', data)
}

export function refreshToken() {
  return request.post('/auth/refresh')
}
