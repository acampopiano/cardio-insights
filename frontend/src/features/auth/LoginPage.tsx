import { useEffect, useRef, useState } from "react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { useForm } from "react-hook-form"
import {
  Activity,
  AlertCircle,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  ShieldCheck,
  User,
} from "lucide-react"

import { BrandMark } from "@/components/BrandMark"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "./useAuth"
import { ApiError } from "@/lib/api"

interface LoginFormValues {
  username: string
  password: string
}

const FEATURES = [
  {
    icon: Activity,
    title: "Analisis clinico en tiempo real",
    description: "KPIs de cirugia cardiaca y hemodinamia centralizados.",
  },
  {
    icon: ShieldCheck,
    title: "Datos seguros y trazables",
    description: "Acceso autenticado y auditable para el equipo medico.",
  },
  {
    icon: Lock,
    title: "Solo personal autorizado",
    description: "Plataforma interna del Instituto Nacional de Cirugia Cardiaca.",
  },
]

export function LoginPage() {
  const { login: doLogin, status } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const usernameRef = useRef<HTMLInputElement | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    defaultValues: { username: "", password: "" },
  })

  const { ref: registerUsernameRef, ...usernameProps } = register("username", {
    required: "Ingresa tu usuario",
  })

  useEffect(() => {
    usernameRef.current?.focus()
  }, [])

  if (status === "authenticated") {
    const redirectTo =
      (location.state as { from?: { pathname?: string } } | null)?.from
        ?.pathname ?? "/dashboard"
    return <Navigate to={redirectTo} replace />
  }

  async function onSubmit(values: LoginFormValues) {
    setServerError(null)
    try {
      await doLogin(values)
      navigate("/dashboard", { replace: true })
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.status === 0
            ? "No se pudo conectar con el servidor. Revisa tu conexion."
            : err.message
          : "Ocurrio un error inesperado. Intentalo nuevamente."
      setServerError(message)
    }
  }

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.05fr_1fr]">
      {/* Brand panel */}
      <aside className="relative hidden overflow-hidden bg-[--color-incc-deep] text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-gradient-to-br from-[#0d3b66] via-[#11497d] to-[#2e8bce]" />
        <div className="absolute -right-24 -top-24 size-[420px] rounded-full bg-white/5 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 size-[360px] rounded-full bg-[var(--color-incc-accent)]/15 blur-3xl" />

        <div className="relative flex h-full flex-col justify-between p-12">
          <BrandMark size={56} />

          <div className="max-w-md space-y-6">
            <h1 className="text-4xl font-bold leading-tight tracking-tight">
              Bienvenido a la plataforma de analisis clinico del INCC
            </h1>
            <p className="text-base text-white/75">
              Centralizamos los datos de cirugia cardiaca, hemodinamia y
              cuidados intensivos para apoyar la toma de decisiones del equipo
              medico.
            </p>

            <ul className="space-y-4 pt-2">
              {FEATURES.map(({ icon: Icon, title, description }) => (
                <li key={title} className="flex items-start gap-3">
                  <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg bg-white/10 ring-1 ring-white/15">
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold">{title}</p>
                    <p className="text-xs text-white/65">{description}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <p className="text-xs text-white/50">
            Instituto Nacional de Cirugia Cardiaca - Cardio Insights v0.1.0
          </p>
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex items-center justify-center bg-background px-6 py-12 sm:px-10">
        <div className="w-full max-w-md">
          {/* Mobile brand */}
          <div className="mb-8 flex items-center justify-center lg:hidden">
            <BrandMark className="text-[--color-incc-deep]" size={44} />
          </div>

          <Card className="border-border/70 shadow-md">
            <CardHeader className="space-y-2">
              <CardTitle className="text-2xl">Iniciar sesion</CardTitle>
              <CardDescription>
                Ingresa con tu usuario del INCC para acceder a los dashboards.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={handleSubmit(onSubmit)}
                noValidate
                className="space-y-5"
              >
                <div className="space-y-2">
                  <Label htmlFor="username">Usuario</Label>
                  <div className="relative">
                    <User className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      id="username"
                      type="text"
                      autoComplete="username"
                      placeholder="tu usuario"
                      aria-invalid={!!errors.username || undefined}
                      aria-describedby={
                        errors.username ? "username-error" : undefined
                      }
                      className="pl-10"
                      {...usernameProps}
                      ref={(el) => {
                        registerUsernameRef(el)
                        usernameRef.current = el
                      }}
                    />
                  </div>
                  {errors.username && (
                    <p
                      id="username-error"
                      className="text-xs text-destructive"
                    >
                      {errors.username.message}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password">Contrasena</Label>
                    <button
                      type="button"
                      className="text-xs text-muted-foreground hover:text-foreground"
                      onClick={(e) => {
                        e.preventDefault()
                      }}
                      tabIndex={-1}
                    >
                      Olvidaste tu contrasena?
                    </button>
                  </div>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      placeholder="********"
                      aria-invalid={!!errors.password || undefined}
                      aria-describedby={
                        errors.password ? "password-error" : undefined
                      }
                      className="pl-10 pr-10"
                      {...register("password", {
                        required: "Ingresa tu contrasena",
                      })}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
                      aria-label={
                        showPassword
                          ? "Ocultar contrasena"
                          : "Mostrar contrasena"
                      }
                    >
                      {showPassword ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  </div>
                  {errors.password && (
                    <p
                      id="password-error"
                      className="text-xs text-destructive"
                    >
                      {errors.password.message}
                    </p>
                  )}
                </div>

                {serverError && (
                  <Alert variant="destructive">
                    <AlertCircle aria-hidden="true" />
                    <AlertDescription>{serverError}</AlertDescription>
                  </Alert>
                )}

                <Button
                  type="submit"
                  className="w-full"
                  size="lg"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Ingresando...
                    </>
                  ) : (
                    "Entrar"
                  )}
                </Button>

                <p className="text-center text-xs text-muted-foreground">
                  Demo:{" "}
                  <code className="rounded bg-muted px-1 py-0.5 text-[11px]">
                    clinician
                  </code>{" "}
                  /{" "}
                  <code className="rounded bg-muted px-1 py-0.5 text-[11px]">
                    Demo1234!
                  </code>
                </p>
              </form>
            </CardContent>
          </Card>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            Acceso restringido al personal autorizado del INCC.
          </p>
        </div>
      </main>
    </div>
  )
}
