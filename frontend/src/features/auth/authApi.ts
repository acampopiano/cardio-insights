import { apiRequest } from "@/lib/api"
import type {
  LoginRequest,
  LoginResponse,
  LogoutResponse,
  MeResponse,
} from "@/types/auth"

export function login(payload: LoginRequest) {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: payload,
    auth: false,
  })
}

export function logout() {
  return apiRequest<LogoutResponse>("/auth/logout", { method: "POST" })
}

export function me() {
  return apiRequest<MeResponse>("/auth/me", { method: "GET" })
}
