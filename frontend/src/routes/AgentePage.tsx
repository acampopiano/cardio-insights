import { useEffect, useRef, useState } from "react"
import {
  AlertCircle,
  Code2,
  Loader2,
  MessageSquare,
  Send,
  Table2,
} from "lucide-react"

import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ApiError } from "@/lib/api"
import { askChat, type ChatMessageDTO } from "@/features/chat/chatApi"
import { cn } from "@/lib/utils"

interface ChatTurn {
  role: "user" | "assistant"
  content: string
  sql?: string | null
  rows?: Record<string, unknown>[]
  rowCount?: number
  isError?: boolean
}

const SUGGESTIONS = [
  "¿Cuántas cirugías se realizaron en 2024?",
  "Mostrame la mortalidad por mes en 2025",
  "¿Cuál fue el tiempo de espera promedio el año pasado?",
  "¿Qué proporción de procedimientos fueron PTCA?",
]

export function AgentePage() {
  const [messages, setMessages] = useState<ChatTurn[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, loading])

  async function send(question: string) {
    const trimmed = question.trim()
    if (!trimmed || loading) return

    const history: ChatMessageDTO[] = messages
      .filter((m) => !m.isError)
      .map((m) => ({ role: m.role, content: m.content }))

    setMessages((prev) => [...prev, { role: "user", content: trimmed }])
    setInput("")
    setLoading(true)

    try {
      const res = await askChat({ question: trimmed, history })
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          sql: res.sql,
          rows: res.rows,
          rowCount: res.row_count,
          isError: !res.resolved,
        },
      ])
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "No se pudo contactar al asistente."
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: message, isError: true },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageShell className="flex h-[calc(100vh-3.5rem-3rem)] flex-col">
      <header className="mb-6 flex items-center gap-3">
        <div
          className="grid size-11 place-items-center rounded-xl bg-[var(--color-incc-primary)]/10 text-[var(--color-incc-primary)]"
          aria-hidden="true"
        >
          <MessageSquare className="size-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Asistente IA</h1>
          <p className="text-sm text-muted-foreground">
            Consultá los datos del INCC en lenguaje natural.
          </p>
        </div>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 space-y-4 overflow-y-auto rounded-xl border bg-muted/20 p-4"
      >
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-5 text-center">
            <div className="grid size-14 place-items-center rounded-2xl bg-[var(--color-incc-primary)]/10 text-[var(--color-incc-primary)]">
              <MessageSquare className="size-7" />
            </div>
            <div className="space-y-1">
              <p className="font-medium">Preguntale a tus datos</p>
              <p className="max-w-md text-sm text-muted-foreground">
                Hacé preguntas sobre cirugías, PTCA, tiempos de espera o mortalidad.
                El asistente consulta la base en modo solo lectura.
              </p>
            </div>
            <div className="grid w-full max-w-lg gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-lg border bg-background px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:border-[var(--color-incc-primary)]/40 hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} turn={m} />
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Analizando los datos…
          </div>
        )}
      </div>

      <form
        className="mt-4 flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Escribí tu pregunta…"
          disabled={loading}
          autoFocus
        />
        <Button type="submit" size="icon" disabled={loading || !input.trim()}>
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Send className="size-4" />
          )}
          <span className="sr-only">Enviar</span>
        </Button>
      </form>
    </PageShell>
  )
}

function MessageBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user"

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] space-y-2 rounded-2xl px-4 py-2.5 text-sm",
          isUser
            ? "bg-[var(--color-incc-primary)] text-white"
            : turn.isError
              ? "border border-destructive/30 bg-destructive/5 text-foreground"
              : "border bg-background text-foreground"
        )}
      >
        {turn.isError && !isUser && (
          <div className="flex items-center gap-1.5 text-xs font-medium text-destructive">
            <AlertCircle className="size-3.5" />
            No se pudo resolver
          </div>
        )}
        <p className="whitespace-pre-wrap leading-relaxed">{turn.content}</p>

        {!isUser && (turn.sql || (turn.rows && turn.rows.length > 0)) && (
          <div className="space-y-2 pt-1">
            {turn.sql && (
              <details className="group">
                <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
                  <Code2 className="size-3.5" />
                  Ver consulta SQL
                </summary>
                <pre className="mt-1.5 overflow-x-auto rounded-md bg-muted p-2 text-xs">
                  <code>{turn.sql}</code>
                </pre>
              </details>
            )}
            {turn.rows && turn.rows.length > 0 && (
              <details className="group" open={turn.rows.length > 1}>
                <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
                  <Table2 className="size-3.5" />
                  Ver datos ({turn.rowCount})
                </summary>
                <div className="mt-1.5">
                  <ResultTable rows={turn.rows} />
                </div>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  const preview = rows.slice(0, 20)
  const columns = Object.keys(preview[0] ?? {})

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-left text-xs">
        <thead className="bg-muted">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-2 py-1.5 font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.map((row, i) => (
            <tr key={i} className="border-t">
              {columns.map((col) => (
                <td key={col} className="px-2 py-1.5">
                  {formatCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > preview.length && (
        <p className="px-2 py-1.5 text-xs text-muted-foreground">
          Mostrando {preview.length} de {rows.length} filas.
        </p>
      )}
    </div>
  )
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}
