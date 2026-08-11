import { apiRequest } from "@/lib/api"

export interface ChatMessageDTO {
  role: "user" | "assistant"
  content: string
}

export interface ChatRequest {
  question: string
  history: ChatMessageDTO[]
}

export interface ChatResponse {
  question: string
  answer: string
  resolved: boolean
  sql: string | null
  rows: Record<string, unknown>[]
  row_count: number
  error: string | null
}

export function askChat(payload: ChatRequest) {
  return apiRequest<ChatResponse>("/chat", {
    method: "POST",
    body: payload,
  })
}
