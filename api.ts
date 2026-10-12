const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api").replace(/\/+$/, "");
const DEFAULT_API_TIMEOUT_MS = 300_000;
const MIN_API_TIMEOUT_MS = 1_000;
const MAX_API_TIMEOUT_MS = 300_000;
const configuredTimeout = Number(import.meta.env.VITE_API_TIMEOUT_MS);
const API_TIMEOUT_MS = Number.isFinite(configuredTimeout) && configuredTimeout > 0
  ? Math.min(MAX_API_TIMEOUT_MS, Math.max(MIN_API_TIMEOUT_MS, configuredTimeout))
  : DEFAULT_API_TIMEOUT_MS;

export type ProviderName = "ollama" | "openai" | "anthropic";
export interface Citation {
  index: number;
  doc_id: string;
  chunk_id: string;
  title: string;
  url: string;
  source: string;
  guest?: string | null;
  youtube_url?: string | null;
  chunk_index?: number | null;
  timestamp?: string | null;
  published_at?: string | null;
  snippet: string;
  score: number;
}
export interface Message {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  provider?: string | null;
  model?: string | null;
  latency_ms?: number | null;
  citations: Citation[];
  message_metadata: Record<string, unknown>;
  created_at: string;
}
export interface Session {
  id: string;
  title: string;
  provider: string;
  model: string | null;
  use_rag: boolean;
  message_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  last_message_preview?: string | null;
}
export interface SessionDetail extends Session {
  messages: Message[];
}
export interface ProviderInfo {
  name: ProviderName;
  configured: boolean;
  available: boolean;
  kind: "local" | "cloud";
  chat_model: string;
  embed_model?: string | null;
  detail?: string | null;
}
export interface ModelListResponse {
  default_provider: string;
  embedding_provider: string;
  providers: ProviderInfo[];
}
export interface RetrievalInfo {
  used: boolean;
  top_k: number;
  results: number;
  best_score?: number | null;
  sufficient: boolean;
  note?: string | null;
  embedding_model?: string | null;
}
export interface ChatResponse {
  session: Session;
  user_message: Message;
  assistant_message: Message;
  citations: Citation[];
  retrieval: RetrievalInfo;
  provider: string;
  model: string;
}

export interface Artifact {
  id: string;
  session_id: string;
  kind: string;
  title: string;
  format: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
  message_id: string | null;
  word_count: number;
}
export interface ArtifactResponse {
  artifact: Artifact;
  citations: Citation[];
  retrieval: RetrievalInfo;
  provider: string;
  model: string;
}
export interface PreviewResponse {
  artifact_id: string;
  title: string;
  html: string;
  sandbox: string;
  csp: string;
  warnings: string[];
}
export interface SkillRunResponse {
  skill: string;
  title: string;
  markdown: string;
  word_count: number;
  outline: string[];
  citations: Citation[];
  retrieval: RetrievalInfo;
  provider: string;
  model: string;
  grounded: boolean;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const controller = new AbortController();
  let timedOut = false;
  const callerSignal = init?.signal;
  const abortFromCaller = () => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) abortFromCaller();
  else callerSignal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, API_TIMEOUT_MS);
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (reason) {
    if (timedOut) {
      throw new Error(`The request timed out after ${Math.round(API_TIMEOUT_MS / 1000)} seconds. Please retry.`);
    }
    if (callerSignal?.aborted) throw new Error("The request was cancelled.");
    throw new Error(`Can't reach the assistant API at ${API_BASE_URL}. Check that the backend is running.`);
  } finally {
    clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", abortFromCaller);
  }

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      const structured = body?.error;
      if (typeof structured?.message === "string") {
        detail = structured.message;
        const validation = structured.details;
        if (Array.isArray(validation)) {
          const issues = validation.map((item: unknown) => {
            if (!item || typeof item !== "object") return String(item);
            const issue = item as { loc?: unknown[]; msg?: unknown };
            const location = Array.isArray(issue.loc) ? issue.loc.map(String).join(".") : "";
            const message = typeof issue.msg === "string" ? issue.msg : "";
            return [location, message].filter(Boolean).join(": ");
          }).filter(Boolean);
          if (issues.length) detail += ` (${issues.join("; ")})`;
        } else if (typeof validation === "string" && validation) {
          detail += ` (${validation})`;
        } else if (validation && typeof validation === "object") {
          detail += ` (${JSON.stringify(validation)})`;
        }
      } else {
        detail = typeof body?.detail === "string" ? body.detail : body?.message;
      }
    } catch {
      // The API may return a plain-text or empty error response.
    }
    throw new Error(detail || `Request failed (${response.status} ${response.statusText}).`);
  }
  if (response.status === 204) return undefined as T;
  const bodyText = await response.text();
  if (!bodyText.trim()) {
    throw new Error("The assistant API returned an empty response. Please retry.");
  }
  let body: unknown;
  try {
    body = JSON.parse(bodyText);
  } catch {
    throw new Error("The assistant API returned an invalid response. Please retry.");
  }
  if (body === null || typeof body !== "object" || (!Array.isArray(body) && Object.keys(body).length === 0)) {
    throw new Error("The assistant API returned an invalid response. Please retry.");
  }
  return body as T;
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function cspSrcDoc(html: string, csp: string, title: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${csp.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;")}">`;
  if (/<head(?:\s[^>]*)?>/i.test(html)) return html.replace(/<head(?:\s[^>]*)?>/i, (head) => `${head}${meta}`);
  if (/<html(?:\s[^>]*)?>/i.test(html)) return html.replace(/<html(?:\s[^>]*)?>/i, (root) => `${root}<head><title>${title.replace(/[<>&"]/g, "")}</title>${meta}</head>`);
  return `<!doctype html><html><head><meta charset="utf-8"><title>${title.replace(/[<>&"]/g, "")}</title>${meta}</head><body>${html}</body></html>`;
}
