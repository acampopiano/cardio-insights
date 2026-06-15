const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1"

const TOKEN_STORAGE_KEY = "cardio_insights.token"

export class ApiError extends Error {
  status: number
  detail?: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }
}

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setStoredToken(token: string | null) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    /* swallow: localStorage may not be available */
  }
}

type UnauthorizedHandler = () => void

let onUnauthorized: UnauthorizedHandler | null = null

export function registerUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  onUnauthorized = handler
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown
  auth?: boolean
}

export async function apiRequest<T>(
  path: string,
  { body, auth = true, headers, ...rest }: RequestOptions = {}
): Promise<T> {
  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string> | undefined),
  }

  if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json"
  }

  if (auth) {
    const token = getStoredToken()
    if (token) {
      finalHeaders.Authorization = `Bearer ${token}`
    }
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...rest,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    throw new ApiError(0, "No se pudo conectar con el servidor", err)
  }

  if (response.status === 401 && auth) {
    onUnauthorized?.()
  }

  const isJson = response.headers
    .get("content-type")
    ?.includes("application/json")

  const payload: unknown = isJson ? await response.json().catch(() => null) : null

  if (!response.ok) {
    const detail =
      (payload &&
        typeof payload === "object" &&
        "detail" in payload &&
        (payload as { detail?: unknown }).detail) ||
      undefined
    const message =
      typeof detail === "string"
        ? detail
        : `Error ${response.status} ${response.statusText}`
    throw new ApiError(response.status, message, detail)
  }

  return payload as T
}
