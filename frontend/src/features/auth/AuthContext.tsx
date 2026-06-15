import { createContext, useCallback, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"

import {
  getStoredToken,
  registerUnauthorizedHandler,
  setStoredToken,
} from "@/lib/api"
import type { LoginRequest, UserPublic } from "@/types/auth"
import * as authApi from "./authApi"

export type AuthStatus = "loading" | "authenticated" | "unauthenticated"

export interface AuthContextValue {
  status: AuthStatus
  user: UserPublic | null
  token: string | null
  login: (credentials: LoginRequest) => Promise<UserPublic>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [token, setTokenState] = useState<string | null>(() => getStoredToken())
  const [user, setUser] = useState<UserPublic | null>(null)
  const [status, setStatus] = useState<AuthStatus>(() =>
    getStoredToken() ? "loading" : "unauthenticated"
  )

  const clearSession = useCallback(() => {
    setStoredToken(null)
    setTokenState(null)
    setUser(null)
    setStatus("unauthenticated")
  }, [])

  useEffect(() => {
    registerUnauthorizedHandler(clearSession)
    return () => registerUnauthorizedHandler(null)
  }, [clearSession])

  useEffect(() => {
    if (!token) {
      setStatus("unauthenticated")
      setUser(null)
      return
    }

    let cancelled = false
    setStatus("loading")

    authApi
      .me()
      .then((res) => {
        if (cancelled) return
        setUser(res.user)
        setStatus("authenticated")
      })
      .catch(() => {
        if (cancelled) return
        clearSession()
      })

    return () => {
      cancelled = true
    }
  }, [token, clearSession])

  const login = useCallback(async (credentials: LoginRequest) => {
    const res = await authApi.login(credentials)
    setStoredToken(res.access_token)
    setTokenState(res.access_token)
    setUser(res.user)
    setStatus("authenticated")
    return res.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      /* ignore: logout always clears local state */
    } finally {
      clearSession()
    }
  }, [clearSession])

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, token, login, logout }),
    [status, user, token, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
