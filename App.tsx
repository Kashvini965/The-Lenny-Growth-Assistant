import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertCircle, ArrowLeft, ArrowUpRight, BookOpen, Check, Copy, FileText, LoaderCircle, Menu,
  MessageSquarePlus, PanelLeftClose, Plus, RefreshCw, RotateCcw, Search, Send, Settings2, Sparkles, Square, Trash2, X,
} from "lucide-react";
import {
  api, cspSrcDoc, formatDate,
} from "./api";
import type {
  Artifact, ArtifactResponse, Citation, ChatResponse, ModelListResponse, PreviewResponse,
  RetrievalInfo, Session, SessionDetail, SkillRunResponse,
} from "./api";
import WorkspaceBackground from "./WorkspaceBackground";
import HeroSection from "./HeroSection";
import type { FeatureCard } from "./HeroSection";

type ArtifactView = { artifact: Artifact; citations: Citation[]; retrieval?: RetrievalInfo };
type SkillView = SkillRunResponse;
type RetryRequest = { message: string; session_id?: string; provider?: string; model?: string; use_rag: boolean };

function sessionIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/chat\/([^/]+)\/?$/);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

function Markdown({ children }: { children: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>;
}

function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <details className="citations">
      <summary><BookOpen size={14} /> Sources <span>{citations.length}</span></summary>
      <ol>
        {citations.map((citation, index) => (
          <li key={`${citation.doc_id}-${citation.chunk_id}-${index}`}>
            <a href={citation.youtube_url || citation.url} target="_blank" rel="noreferrer">
              <strong>[{citation.index}] {citation.title}</strong>
              <span>{[citation.guest, citation.timestamp, citation.chunk_index != null ? `Chunk ${citation.chunk_index + 1}` : null, citation.published_at].filter(Boolean).join(" · ") || citation.source}</span>
            </a>
            {citation.snippet && <p>{citation.snippet}</p>}
          </li>
        ))}
      </ol>
    </details>
  );
}

function ErrorMessage({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="error-message" role="alert">
      <AlertCircle size={17} />
      <span>{message}</span>
      {retry && <button className="text-button" onClick={retry}><RefreshCw size={14} /> Retry</button>}
    </div>
  );
}

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [isHomeView, setIsHomeView] = useState(() => !sessionIdFromPath(window.location.pathname));
  const [models, setModels] = useState<ModelListResponse | null>(null);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [useRag, setUseRag] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [busySessions, setBusySessions] = useState(false);
  const [error, setError] = useState("");
  const [retryRequest, setRetryRequest] = useState<RetryRequest | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [action, setAction] = useState<"essay" | "skill" | null>(null);
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [wordTarget, setWordTarget] = useState(1250);
  const [outputFormat, setOutputFormat] = useState<"markdown" | "html">("markdown");
  const [generating, setGenerating] = useState(false);
  const [artifactView, setArtifactView] = useState<ArtifactView | null>(null);
  const [skillView, setSkillView] = useState<SkillView | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [zoomLevel, setZoomLevel] = useState<number>(() => {
    try {
      const saved = localStorage.getItem("lenny_assistant_zoom_level") || localStorage.getItem("fieldnotes_zoom_level");
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= 100 && parsed <= 200) {
          return parsed;
        }
      }
    } catch {
      // ignore storage errors
    }
    return 100;
  });

  const messageEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const homeViewRef = useRef(isHomeView);

  const setHomeView = useCallback((isHome: boolean) => {
    homeViewRef.current = isHome;
    setIsHomeView(isHome);
  }, []);

  const navigateHome = useCallback((replace = false) => {
    if (window.location.pathname !== "/" || window.location.search) {
      window.history[replace ? "replaceState" : "pushState"]({}, "", "/");
    }
    setHomeView(true);
    setMobileOpen(false);
  }, [setHomeView]);

  const navigateChat = useCallback((id: string, historyMode: "push" | "replace" | "none" = "push") => {
    const path = `/chat/${encodeURIComponent(id)}`;
    if (historyMode !== "none" && window.location.pathname !== path) {
      window.history[historyMode === "push" ? "pushState" : "replaceState"]({}, "", path);
    }
    setHomeView(false);
    setMobileOpen(false);
  }, [setHomeView]);

  useEffect(() => {
    const baseFontSize = (18 * (zoomLevel / 100)).toFixed(2);
    document.documentElement.style.fontSize = `${baseFontSize}px`;
    try {
      localStorage.setItem("lenny_assistant_zoom_level", zoomLevel.toString());
    } catch {
      // ignore storage errors
    }
  }, [zoomLevel]);

  const handleZoomIn = () => {
    setZoomLevel((prev) => Math.min(200, prev + 10));
  };

  const handleZoomOut = () => {
    setZoomLevel((prev) => Math.max(100, prev - 10));
  };

  const handleZoomReset = () => {
    setZoomLevel(100);
  };

  const availableProviders = useMemo(() => models?.providers ?? [], [models]);
  const currentProvider = availableProviders.find((item) => item.name === provider);
  const orderedSessions = useMemo(
    () => [...sessions].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()),
    [sessions],
  );
  const visibleSessions = useMemo(() => {
    const query = historySearch.trim().toLocaleLowerCase();
    return query ? orderedSessions.filter((session) => session.title.toLocaleLowerCase().includes(query)) : orderedSessions;
  }, [historySearch, orderedSessions]);

  const refreshSessions = useCallback(async () => {
    setBusySessions(true);
    try {
      const data = await api<Session[]>("/sessions");
      setSessions(data);
      return data;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load conversation history.");
      return null;
    } finally {
      setBusySessions(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    let apiReachable = false;
    const markOnline = () => {
      apiReachable = true;
      if (active) setApiStatus("online");
    };
    const markOfflineIfUnreachable = () => {
      if (active && !apiReachable) setApiStatus("offline");
    };

    void api<{ status: string }>("/health").then(markOnline).catch(markOfflineIfUnreachable);
    void api<ModelListResponse>("/models").then((data) => {
      markOnline();
      if (!active) return;
      setModels(data);
      const chosen = data.providers.find((item) => item.name === data.default_provider)
        ?? data.providers[0];
      if (chosen) {
        setProvider(chosen.name);
        setModel(chosen.chat_model);
      }
    }).catch((reason: unknown) => {
      markOfflineIfUnreachable();
      if (active) setError(reason instanceof Error ? reason.message : "Unable to load configured providers.");
    });
    void api<Session[]>("/sessions").then((data) => {
      markOnline();
      if (active) {
        setSessions(data);
        const searchParams = new URLSearchParams(window.location.search);
        const targetSessionId = sessionIdFromPath(window.location.pathname) || searchParams.get("session");
        if (targetSessionId && data.some((s) => s.id === targetSessionId)) {
          void selectSession(targetSessionId, "replace");
        } else if (sessionIdFromPath(window.location.pathname)) {
          navigateHome(true);
        }
      }
    }).catch((reason: unknown) => {
      markOfflineIfUnreachable();
      if (active) setError(reason instanceof Error ? reason.message : "Unable to load conversation history.");
    });
    return () => { active = false; };
  }, []);

  const selectSession = useCallback(async (id: string, historyMode: "push" | "replace" | "none" = "push") => {
    navigateChat(id, historyMode);
    setSelectedId(id);
    setError("");
    setLoadingSession(true);
    try {
      const session = await api<SessionDetail>(`/sessions/${encodeURIComponent(id)}`);
      setDetail(session);
      setProvider(session.provider);
      if (session.model) setModel(session.model);
      setUseRag(session.use_rag);
    } catch (reason) {
      setDetail(null);
      setError(reason instanceof Error ? reason.message : "Unable to open this conversation.");
    } finally {
      setLoadingSession(false);
    }
  }, [navigateChat]);

  useEffect(() => {
    const handlePopState = () => {
      const searchParams = new URLSearchParams(window.location.search);
      const targetSessionId = sessionIdFromPath(window.location.pathname) || searchParams.get("session");
      if (targetSessionId) {
        void selectSession(targetSessionId, "none");
      } else {
        navigateHome(true);
      }
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [navigateHome, selectSession]);

  const createSession = async () => {
    setError("");
    try {
      const session = await api<Session>("/sessions", {
        method: "POST",
        body: JSON.stringify({ title: "New conversation", provider: provider || undefined, model: model || undefined, use_rag: useRag }),
      });
      setSessions((items) => [session, ...items.filter((item) => item.id !== session.id)]);
      setSelectedId(session.id);
      setDetail({ ...session, messages: [] });
      navigateChat(session.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start a conversation.");
    }
  };

  const deleteSession = async (session: Session) => {
    if (!window.confirm(`Delete “${session.title}” and its conversation history?`)) return;
    setError("");
    try {
      await api<void>(`/sessions/${encodeURIComponent(session.id)}`, { method: "DELETE" });
      const remaining = sessions.filter((item) => item.id !== session.id);
      setSessions(remaining);
      if (selectedId === session.id) {
        setSelectedId(null);
        setDetail(null);
        navigateHome(true);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to delete this conversation.");
    }
  };

  const saveSettings = async (next: { provider?: string; model?: string; use_rag?: boolean }) => {
    if (!detail) return;
    const patch = { ...next };
    try {
      const updated = await api<Session>(`/sessions/${encodeURIComponent(detail.id)}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      setSessions((items) => items.map((item) => item.id === updated.id ? updated : item));
      setDetail((current) => current ? { ...current, ...updated } : current);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save conversation settings.");
    }
  };

  const applyChatResponse = (response: ChatResponse) => {
    setSessions((items) => [response.session, ...items.filter((item) => item.id !== response.session.id)]);
    setSelectedId(response.session.id);
    setDetail((current) => {
      const existing = current?.id === response.session.id ? current.messages : [];
      const newMessages = [response.user_message, response.assistant_message];
      const known = new Set(existing.map((message) => message.id));
      return { ...response.session, messages: [...existing, ...newMessages.filter((message) => !known.has(message.id))] };
    });
    setProvider(response.provider);
    setModel(response.model);
    if (!homeViewRef.current) navigateChat(response.session.id);
  };

  const stopResponse = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setSending(false);
  };

  const sendMessage = async (input: string, retry?: RetryRequest) => {
    const message = input.trim();
    if (!message || sending) return;
    if (homeViewRef.current) setHomeView(false);
    setError("");
    setDraft(""); // Clear input immediately
    setSending(true);

    // Optimistically render user message immediately in the chat
    const tempUserMessageId = `temp-user-${Date.now()}`;
    const optimisticUserMessage = {
      id: tempUserMessageId,
      session_id: selectedId || "temp-session",
      role: "user" as const,
      content: message,
      provider: provider || null,
      model: model || null,
      latency_ms: null,
      citations: [],
      message_metadata: {},
      created_at: new Date().toISOString(),
    };

    setDetail((current) => {
      if (current) {
        return {
          ...current,
          message_count: current.message_count + 1,
          messages: [...current.messages, optimisticUserMessage],
        };
      }
      return {
        id: selectedId || "temp-session",
        title: message.slice(0, 40),
        provider: provider || "ollama",
        model: model || null,
        use_rag: useRag,
        message_count: 1,
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [optimisticUserMessage],
      };
    });

    const request: RetryRequest = retry ?? {
      message,
      session_id: selectedId ?? undefined,
      provider: provider || undefined,
      model: model || undefined,
      use_rag: useRag,
    };
    setRetryRequest(request);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await api<ChatResponse>("/chat", {
        method: "POST",
        body: JSON.stringify({ ...request, stream: false }),
        signal: controller.signal,
      });
      if (typeof response.assistant_message?.content !== "string" || !response.assistant_message.content.trim()) {
        throw new Error("The assistant returned an empty response. Please retry.");
      }
      applyChatResponse(response);
      setRetryRequest(null);
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === "AbortError") {
        // User stopped generation intentionally
        return;
      }
      // Revert optimistic user message on error so user can retry
      setDetail((current) => {
        if (!current) return current;
        return {
          ...current,
          messages: current.messages.filter((m) => m.id !== tempUserMessageId),
        };
      });
      setDraft(message); // restore draft
      setError(reason instanceof Error ? reason.message : "Your message could not be sent.");
    } finally {
      abortControllerRef.current = null;
      setSending(false);
    }
  };

  const retry = () => retryRequest && void sendMessage(retryRequest.message, retryRequest);

  // The hero is only shown before a conversation is opened; sending the first message creates the session.
  const beginNewChat = () => {
    setMobileOpen(false);
    document.querySelector(".composer-wrap")?.scrollIntoView({ behavior: "smooth", block: "end" });
    document.getElementById("message-input")?.focus();
  };

  const activateFeature = (card: FeatureCard) => {
    if (card.action) {
      setAction(card.action);
      setTopic("");
      setAudience("");
      setOutputFormat("markdown");
      return;
    }
    if (card.prompt) {
      setDraft(card.prompt);
    }
    setMobileOpen(false);
    document.querySelector(".composer-wrap")?.scrollIntoView({ behavior: "smooth", block: "end" });
    window.setTimeout(() => {
      const input = document.getElementById("message-input") as HTMLTextAreaElement | null;
      input?.focus();
      input?.setSelectionRange(input.value.length, input.value.length);
    }, 240);
  };

  const openArtifact = async (view: ArtifactView) => {
    setArtifactView(view);
    setPreview(null);
    setPreviewError("");
    if (view.artifact.format.toLowerCase() !== "html") return;
    try {
      const payload = await api<PreviewResponse>(`/artifacts/${encodeURIComponent(view.artifact.id)}/preview`);
      setPreview(payload);
    } catch (reason) {
      setPreviewError(reason instanceof Error ? reason.message : "Unable to load the HTML preview.");
    }
  };

  const submitGeneration = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanTopic = topic.trim();
    if (cleanTopic.length < 3 || generating) return;
    setGenerating(true);
    setError("");
    setArtifactView(null);
    setSkillView(null);
    setPreview(null);
    try {
      if (action === "skill") {
        const result = await api<SkillRunResponse>("/skills/ship-30-for-30", {
          method: "POST",
          body: JSON.stringify({
            session_id: selectedId ?? undefined,
            topic: cleanTopic,
            audience: audience.trim() || "product leaders",
            word_target: Math.max(600, Math.min(2500, wordTarget)),
            provider: provider || undefined,
            model: model || undefined,
            use_rag: useRag,
          }),
        });
        setSkillView(result);
      } else {
        const result = await api<ArtifactResponse>("/artifacts", {
          method: "POST",
          body: JSON.stringify({
            session_id: selectedId ?? undefined,
            kind: "essay",
            format: outputFormat,
            topic: cleanTopic,
            prompt: audience.trim() ? `Write for ${audience.trim()}.` : undefined,
            provider: provider || undefined,
            model: model || undefined,
            use_rag: useRag,
            word_target: Math.max(200, Math.min(4000, wordTarget)),
          }),
        });
        await openArtifact({ artifact: result.artifact, citations: result.citations, retrieval: result.retrieval });
        if (!selectedId) {
          const updatedSessions = await refreshSessions();
          const createdSession = updatedSessions?.find((item) => item.id === result.artifact.session_id);
          if (createdSession) {
            setSelectedId(createdSession.id);
            setDetail({ ...createdSession, messages: [] });
          }
        }
      }
      setAction(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The writing task could not be completed.");
    } finally {
      setGenerating(false);
    }
  };

  const changeProvider = (next: string) => {
    setProvider(next);
    const info = availableProviders.find((item) => item.name === next);
    const nextModel = info?.chat_model ?? "";
    setModel(nextModel);
    if (detail) void saveSettings({ provider: next, model: nextModel });
  };

  const handleComposerKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(draft);
    }
  };
  const copyMessage = async (message: SessionDetail["messages"][number]) => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedMessageId(message.id);
      window.setTimeout(() => setCopiedMessageId((current) => current === message.id ? null : current), 1800);
    } catch {
      setError("Could not copy this response. Check clipboard permissions and try again.");
    }
  };
  const regenerateFrom = (messageIndex: number) => {
    const previousUserMessage = [...messages.slice(0, messageIndex)].reverse().find((message) => message.role === "user");
    if (previousUserMessage) void sendMessage(previousUserMessage.content);
  };
  const ActionIcon = action === "essay" ? FileText : Sparkles;

  const messages = detail?.messages ?? [];
  useEffect(() => {
    const onShortcut = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.querySelector<HTMLButtonElement>(".new-chat-button")?.click();
      }
    };
    window.addEventListener("keydown", onShortcut);
    return () => window.removeEventListener("keydown", onShortcut);
  }, []);
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, sending]);

  return (
    <div className="app-shell">
      {mobileOpen && <button aria-label="Close navigation" className="mobile-scrim" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? "mobile-open" : ""} ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="brand-row">
          <button type="button" className="brand-home" aria-label="Back to home" onClick={() => navigateHome()}>
            <span className="brand-mark" aria-hidden="true"><span><Sparkles size={17} /></span></span>
            {!sidebarCollapsed && <span className="brand-copy"><strong>The Lenny<br />Growth Assistant</strong><span>GROWTH INTELLIGENCE</span></span>}
          </button>
          <button className="icon-button sidebar-collapse" aria-label="Collapse sidebar" onClick={() => setSidebarCollapsed((value) => !value)}>
            <PanelLeftClose size={17} />
          </button>
          <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button>
        </div>
        <button className="new-chat-button" onClick={() => void createSession()} title="Start a new conversation">
          <Plus size={17} /><span>New conversation</span><kbd>⌘ K</kbd>
        </button>
        <div className="sidebar-history-scroll">
          <div className="history-heading">
            {!sidebarCollapsed && <span>RECENT WORK</span>}
            {busySessions && <LoaderCircle className="spin" size={13} aria-label="Refreshing conversations" />}
          </div>
          {!sidebarCollapsed && <label className="history-search">
            <Search size={15} />
            <input aria-label="Search conversations" value={historySearch} onChange={(event) => setHistorySearch(event.target.value)} placeholder="Find a conversation" />
            {historySearch && <button type="button" aria-label="Clear conversation search" onClick={() => setHistorySearch("")}><X size={13} /></button>}
          </label>}
          <nav className="session-list" aria-label="Conversation history">
            {visibleSessions.length === 0 && !sidebarCollapsed && (
              <p className="empty-history">{historySearch ? "No conversations match that search." : busySessions ? "Loading conversations…" : "Your conversations will appear here."}</p>
            )}
            {visibleSessions.map((session) => (
              <div className={`session-entry ${selectedId === session.id ? "selected" : ""}`} key={session.id}>
                <button className="session-select" onClick={() => void selectSession(session.id)} title={session.title}>
                  <MessageSquarePlus size={17} />
                  {!sidebarCollapsed && <span className="session-label"><strong>{session.title}</strong><small>{formatDate(session.updated_at)}</small></span>}
                </button>
                {!sidebarCollapsed && <button className="delete-session" aria-label={`Delete ${session.title}`} onClick={() => void deleteSession(session)}><Trash2 size={16} /></button>}
              </div>
            ))}
          </nav>
        </div>
        <div className="sidebar-bottom">
          <div className={`api-indicator ${apiStatus}`}>
            <span className="status-dot" />
            {!sidebarCollapsed && <span>{apiStatus === "checking" ? "Connecting to API" : apiStatus === "online" ? "API connected" : "API offline"}</span>}
          </div>
          {!sidebarCollapsed && <span className="sidebar-footnote">A research partner for better growth decisions</span>}
        </div>
      </aside>

      <main className="main-area">
        <WorkspaceBackground />
        <header className="topbar">
          <div className="topbar-title">
            <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
            {!isHomeView && <button type="button" className="secondary-button back-home-button" aria-label="Back to home" onClick={() => navigateHome()}>
              <ArrowLeft size={18} /><span className="back-home-desktop">Back to Home</span><span className="back-home-mobile">Home</span>
            </button>}
            <div className="crumb"><span>LENNY GROWTH ASSISTANT</span><span className="crumb-divider">/</span><strong>{detail?.title || "Growth workspace"}</strong></div>
          </div>
          <div className="topbar-actions">
            <div className="zoom-controls" role="group" aria-label="Text zoom controls">
              <button
                type="button"
                className="zoom-btn"
                onClick={handleZoomOut}
                disabled={zoomLevel <= 100}
                aria-label="Decrease text size"
                title="Decrease font size"
              >
                A−
              </button>
              <button
                type="button"
                className="zoom-level-btn"
                onClick={handleZoomReset}
                title="Reset zoom to 100%"
                aria-label={`Current zoom ${zoomLevel}%. Click to reset to 100%`}
              >
                {zoomLevel}%
              </button>
              <button type="button" className="zoom-reset-btn" onClick={handleZoomReset} disabled={zoomLevel === 100}>
                Reset
              </button>
              <button
                type="button"
                className="zoom-btn"
                onClick={handleZoomIn}
                disabled={zoomLevel >= 200}
                aria-label="Increase text size"
                title="Increase font size"
              >
                A+
              </button>
            </div>
            <button className="secondary-button skill-button" onClick={() => { setAction("skill"); setTopic(""); setAudience(""); setOutputFormat("markdown"); }}>
              <Sparkles size={15} /><span>30-for-30</span>
            </button>
            <button className="primary-button essay-button" onClick={() => { setAction("essay"); setTopic(""); setAudience(""); setOutputFormat("markdown"); }}>
              <FileText size={15} /><span>Write an essay</span>
            </button>
          </div>
        </header>

        <section className="settings-bar" aria-label="Conversation settings">
          <div className="setting-control">
            <Settings2 size={15} />
            <label htmlFor="provider-select">Provider</label>
            <select id="provider-select" aria-label="Provider" value={provider} onChange={(event) => changeProvider(event.target.value)} disabled={!availableProviders.length}>
              {availableProviders.length === 0 && <option value="">Loading…</option>}
              {availableProviders.map((item) => (
                <option key={item.name} value={item.name} disabled={!item.configured || !item.available}>
                  {item.name} · {item.configured && item.available ? "ready" : item.configured ? "unavailable" : "not configured"}
                </option>
              ))}
            </select>
          </div>
          <span className={`provider-state ${currentProvider?.configured && currentProvider.available ? "ready" : "muted"}`}>
            <span className="status-dot" />{currentProvider ? currentProvider.configured && currentProvider.available ? "Ready" : "Not ready" : "Checking"}
          </span>
          {currentProvider?.detail && <span className="provider-detail" title={currentProvider.detail}>{currentProvider.detail}</span>}
          <div className="setting-divider" />
          <div className="setting-control model-control">
            <label htmlFor="model-select">Model</label>
            <select id="model-select" aria-label="Model" value={model} onChange={(event) => {
              setModel(event.target.value);
              if (detail) void saveSettings({ model: event.target.value });
            }} disabled={!currentProvider?.chat_model}>
              {currentProvider?.chat_model && <option value={currentProvider.chat_model}>{currentProvider.chat_model}</option>}
            </select>
          </div>
          <label className="rag-toggle">
            <input type="checkbox" checked={useRag} onChange={(event) => {
              setUseRag(event.target.checked);
              if (detail) void saveSettings({ use_rag: event.target.checked });
            }} />
            <span className="toggle-track"><span /></span>
            <span>Use sources</span>
          </label>
          {sidebarCollapsed && <button className="icon-button sidebar-expand" aria-label="Expand sidebar" onClick={() => setSidebarCollapsed(false)}><PanelLeftClose size={17} /></button>}
        </section>

        {error && <div className="global-error"><ErrorMessage message={error} retry={retryRequest ? retry : undefined} /><button className="icon-button" aria-label="Dismiss error" onClick={() => setError("")}><X size={16} /></button></div>}

        <div className={`chat-body ${isHomeView && !loadingSession ? "landing-body" : ""}`}>
          <section className="conversation-area">
            {loadingSession ? (
              <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>Opening conversation…</span></div>
            ) : isHomeView || !detail || messages.length === 0 ? (
              <div className={`welcome ${isHomeView || !detail ? "welcome-hero" : ""}`}>
                {isHomeView || !detail ? (
                  <HeroSection onStart={beginNewChat} onFeature={activateFeature} startLabel="Start Exploring" />
                ) : (
                  <div className="session-lead">
                    <div className="welcome-orbit" aria-hidden="true"><span /><span /><div className="welcome-mark"><Sparkles size={18} /></div></div>
                    <p className="eyebrow">WORKING SESSION · READY</p>
                    <h1>What are you working on?</h1>
                    <p className="welcome-copy">A focused space to explore product challenges, pressure-test strategy, and turn hard-won lessons into your next move.</p>
                  </div>
                )}
                {!loadingSession && <div className="suggestion-grid" aria-label="Suggested prompts">
                  {[
                    { label: "Diagnose a growth plateau", prompt: "Help me diagnose a growth plateau. What information should I gather, and which levers should I examine first?" },
                    { label: "Pressure-test an idea", prompt: "Pressure-test this product idea with me. Help me surface assumptions, risks, and the fastest useful experiment." },
                    { label: "Find a better metric", prompt: "Help me identify a meaningful product growth metric for my team. Ask what context you need before recommending one." },
                  ].map((suggestion) => <button className="suggestion-card" key={suggestion.label} onClick={() => { setDraft(suggestion.prompt); document.getElementById("message-input")?.focus(); }}>
                    <span>{suggestion.label}</span><ArrowUpRight className="suggestion-arrow" size={15} aria-hidden="true" />
                  </button>)}
                </div>}
              </div>
            ) : (
              <div className="messages" aria-live="polite">
                {messages.map((message, index) => (
                  <article className={`message-row ${message.role}`} key={message.id}>
                    <div className={`avatar ${message.role}`}>{message.role === "assistant" ? <Sparkles size={15} /> : "Y"}</div>
                    <div className="message-content">
                      <div className="message-meta"><strong>{message.role === "assistant" ? "Assistant" : "You"}</strong><time>{formatDate(message.created_at)}</time></div>
                      <div className="markdown-body"><Markdown>{message.content}</Markdown></div>
                      {message.role === "assistant" && <CitationList citations={message.citations ?? []} />}
                      {message.role === "assistant" && <div className="message-actions">
                        <button onClick={() => void copyMessage(message)} title="Copy response" aria-label="Copy response">{copiedMessageId === message.id ? <Check size={14} /> : <Copy size={14} />}<span>{copiedMessageId === message.id ? "Copied" : "Copy"}</span></button>
                        {index === messages.length - 1 && <button onClick={() => regenerateFrom(index)} title="Ask the same question again" aria-label="Ask the same question again" disabled={sending}><RotateCcw size={14} /><span>Ask again</span></button>}
                      </div>}
                    </div>
                  </article>
                ))}
                {sending && <div className="message-row assistant pending-message"><div className="avatar assistant"><Sparkles size={15} /></div><div className="message-content"><div className="message-meta"><strong>Assistant</strong><span className="thinking"><span />Thinking</span></div><div className="typing-indicator"><i /><i /><i /></div></div></div>}
                <div ref={messageEndRef} />
              </div>
            )}
          </section>

          <div className="composer-wrap">
          {isHomeView && !sessions.length && <button className="composer-new-session" onClick={() => void createSession()}><MessageSquarePlus size={14} /> Start a conversation</button>}
          <form className="composer" onSubmit={(event) => { event.preventDefault(); void sendMessage(draft); }}>
            <label className="sr-only" htmlFor="message-input">Message the assistant</label>
            <textarea
              id="message-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleComposerKey}
              placeholder="Ask a question, explore a challenge, or think out loud…"
              rows={2}
              disabled={sending}
            />
            <div className="composer-footer">
              <span className="composer-hint">Shift + Enter for a new line</span>
              <div className="composer-actions">
                {sending && (
                  <button
                    className="stop-button"
                    type="button"
                    onClick={stopResponse}
                    title="Stop generating"
                    aria-label="Stop response"
                  >
                    <Square size={14} fill="currentColor" />
                    <span>Stop</span>
                  </button>
                )}
                <button
                  className="send-button"
                  type="submit"
                  disabled={!draft.trim() || sending}
                >
                  {sending ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />}
                  <span>{sending ? "Sending" : "Send"}</span>
                </button>
              </div>
            </div>
          </form>
          <p className="disclaimer">AI can make mistakes. Check important details against the sources.</p>
          </div>
        </div>
      </main>

      {(artifactView || skillView) && (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) { setArtifactView(null); setSkillView(null); } }}>
          <section className="result-panel" role="dialog" aria-modal="true" aria-labelledby="result-title">
            <header className="result-header">
              <div><span className="eyebrow">{artifactView ? "GENERATED ESSAY" : "SHIP 30 FOR 30"}</span><h2 id="result-title">{artifactView?.artifact.title ?? skillView?.title}</h2></div>
              <button className="icon-button" aria-label="Close result" onClick={() => { setArtifactView(null); setSkillView(null); }}><X size={19} /></button>
            </header>
            <div className="result-meta">
              {artifactView && <span>{artifactView.artifact.word_count} words</span>}
              {skillView && <span>{skillView.word_count} words</span>}
              {(artifactView?.retrieval || skillView?.retrieval) && <span>{(artifactView?.retrieval ?? skillView?.retrieval)?.used ? "Source-grounded" : "Generated without retrieval"}</span>}
              {skillView && <span>{skillView.grounded ? "Grounded" : "Not fully grounded"}</span>}
            </div>
            {artifactView?.artifact.format.toLowerCase() === "html" ? (
              <div className="preview-frame">
                {previewError ? <ErrorMessage message={previewError} /> : preview ? <iframe title={preview.title} sandbox="" srcDoc={cspSrcDoc(preview.html, preview.csp, preview.title)} /> : <div className="loading-state"><LoaderCircle className="spin" size={20} />Loading safe preview…</div>}
                {!!preview?.warnings.length && <ul className="preview-warnings">{preview.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
              </div>
            ) : (
              <div className="result-content markdown-body">
                <Markdown>{artifactView?.artifact.content ?? skillView?.markdown ?? ""}</Markdown>
                {!!skillView?.outline.length && <details className="outline"><summary>Essay outline</summary><ol>{skillView.outline.map((item, index) => <li key={index}>{item}</li>)}</ol></details>}
              </div>
            )}
            <CitationList citations={artifactView?.citations ?? skillView?.citations ?? []} />
            <footer className="result-footer"><button className="secondary-button" onClick={() => { setArtifactView(null); setSkillView(null); }}><Check size={15} /> Done</button></footer>
          </section>
        </div>
      )}

      {action && (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !generating) setAction(null); }}>
          <section className="generation-dialog" role="dialog" aria-modal="true" aria-labelledby="generation-title">
            <header className="dialog-header">
              <div className="dialog-icon"><ActionIcon size={19} /></div>
              <div><span className="eyebrow">{action === "essay" ? "CREATE A LONG-FORM PIECE" : "WRITING SKILL"}</span><h2 id="generation-title">{action === "essay" ? "Generate an essay" : "Run Ship 30 for 30"}</h2></div>
              <button className="icon-button" aria-label="Close dialog" onClick={() => setAction(null)} disabled={generating}><X size={19} /></button>
            </header>
            <p className="dialog-description">{action === "essay" ? "Turn a topic into a source-grounded essay, saved as an artifact." : "Use the Ship 30 for 30 writing workflow to shape a grounded essay."}</p>
            <form onSubmit={(event) => void submitGeneration(event)}>
              <label className="form-field"><span>Topic <b>*</b></span><textarea autoFocus minLength={3} maxLength={400} required rows={3} value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="What should the essay explore?" /></label>
              <label className="form-field"><span>Audience <small>Optional</small></span><input value={audience} onChange={(event) => setAudience(event.target.value)} maxLength={200} placeholder="e.g. early-stage founders" /></label>
              {action === "essay" && <label className="form-field"><span>Format</span><select value={outputFormat} onChange={(event) => setOutputFormat(event.target.value as "markdown" | "html")}><option value="markdown">Markdown document</option><option value="html">HTML preview</option></select></label>}
              <label className="form-field"><span>Word target <small>{action === "skill" ? "600–2,500" : "200–4,000"}</small></span><input type="number" min={action === "skill" ? 600 : 200} max={action === "skill" ? 2500 : 4000} step={50} value={wordTarget} onChange={(event) => setWordTarget(Number(event.target.value))} /></label>
              <div className="dialog-actions"><button type="button" className="secondary-button" onClick={() => setAction(null)} disabled={generating}>Cancel</button><button type="submit" className="primary-button" disabled={generating || topic.trim().length < 3}>{generating ? <><LoaderCircle className="spin" size={16} /> Working…</> : <><Sparkles size={15} /> {action === "essay" ? "Generate essay" : "Run skill"}</>}</button></div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
