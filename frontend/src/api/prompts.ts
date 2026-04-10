import request from './request'

export interface PromptMeta {
  name: string
  title: string
  description: string
  placeholders: string[]
  size_bytes: number
  modified_at: string | null
}

export interface PromptDetail extends PromptMeta {
  content: string
}

export function listPrompts() {
  return request.get<PromptMeta[]>('/prompts')
}

export function getPrompt(name: string) {
  return request.get<PromptDetail>(`/prompts/${name}`)
}

export function updatePrompt(name: string, content: string) {
  return request.put<PromptDetail>(`/prompts/${name}`, { content })
}

// ---------------- Test step 1: scheme_prompt ----------------

export interface SchemeTestResult {
  product_name: string
  scheme: Record<string, any>
  duration_ms: number
  error: string
}

export function testSchemePrompt(record_id: string) {
  return request.post<SchemeTestResult>(
    '/prompts/test/scheme',
    { record_id },
    { timeout: 120000 }
  )
}

// ---------------- Test step 2: image_prompt ----------------

export interface ImagePromptTestResult {
  product_name: string
  image_prompt: string
  duration_ms: number
  error: string
}

export function testImagePrompt(record_id: string, scheme: Record<string, any>) {
  return request.post<ImagePromptTestResult>(
    '/prompts/test/image-prompt',
    { record_id, scheme },
    { timeout: 120000 }
  )
}

// ---------------- Test step 3: final image generation ----------------

export interface ImageTestResult {
  product_name: string
  image_b64: string
  image_size_bytes: number
  asset_process_ms: number
  image_gen_ms: number
  overlay_ms: number
  total_ms: number
  error: string
}

export function testImage(
  record_id: string,
  image_prompt: string
) {
  return request.post<ImageTestResult>(
    '/prompts/test/image',
    { record_id, image_prompt },
    { timeout: 300000 }
  )
}
