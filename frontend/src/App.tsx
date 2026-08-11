import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/layout/AppLayout"
import { AuthProvider } from "@/features/auth/AuthContext"
import { LoginPage } from "@/features/auth/LoginPage"
import { AgentePage } from "@/routes/AgentePage"
import { HomePage } from "@/routes/HomePage"
import { KpisPage } from "@/routes/KpisPage"
import { MethodologyPage } from "@/routes/MethodologyPage"
import { MLPage } from "@/routes/MLPage"
import { ML_ACCESS_ROLES } from "@/lib/navigation"
import { ProtectedRoute } from "@/routes/ProtectedRoute"
import { RoleRoute } from "@/routes/RoleRoute"

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LoginPage />} />

          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<HomePage />} />
            <Route path="/kpis" element={<KpisPage />} />
            <Route
              path="/ml"
              element={
                <RoleRoute roles={ML_ACCESS_ROLES}>
                  <MLPage />
                </RoleRoute>
              }
            />
            <Route
              path="/ml/metodologia"
              element={
                <RoleRoute roles={ML_ACCESS_ROLES}>
                  <MethodologyPage />
                </RoleRoute>
              }
            />
            <Route path="/agente" element={<AgentePage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
