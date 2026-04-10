import request from './request'

export interface ModelInfo {
  id: string
  owned_by: string
  object: string
}

export interface AvailableModelsResponse {
  text_models: ModelInfo[]
  image_models: ModelInfo[]
  all_models: ModelInfo[]
}

export interface ModelSettings {
  gemini_copy_model: string
  gemini_image_model: string
}

export function listAvailableModels() {
  return request.get<AvailableModelsResponse>('/settings/models/available', {
    timeout: 30000,
  })
}

export function getModelSettings() {
  return request.get<ModelSettings>('/settings/models')
}

export function updateModelSettings(settings: Partial<ModelSettings>) {
  return request.put<ModelSettings>('/settings/models', settings)
}
