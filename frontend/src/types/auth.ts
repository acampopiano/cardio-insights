export interface UserPublic {
  id: number
  username: string
  full_name: string
  role: string
  permissions: string[]
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: "bearer"
  expires_in: number
  user: UserPublic
}

export interface LogoutResponse {
  success: boolean
  message: string
}

export interface MeResponse {
  user: UserPublic
}
