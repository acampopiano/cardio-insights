import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/layout/AppLayout"
import { AuthProvider } from "@/features/auth/AuthContext"
import { LoginPage } from "@/features/auth/LoginPage"
import { AgentePage } from "@/routes/AgentePage"
import { HomePage } from "@/routes/HomePage"
import { KpisPage } from "@/routes/KpisPage"
import { MLPage } from "@/routes/MLPage"
import { ProtectedRoute } from "@/routes/ProtectedRoute"
import { ReportesPage } from "@/routes/ReportesPage"

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
            <Route path="/reportes" element={<ReportesPage />} />
            <Route path="/kpis" element={<KpisPage />} />
            <Route path="/ml" element={<MLPage />} />
            <Route path="/agente" element={<AgentePage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
