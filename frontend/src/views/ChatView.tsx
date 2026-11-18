import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  Loader2,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Smartphone,
  Terminal,
  Trash2,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ApiError, api } from '../lib/api';
import { formatRelativeDate, formatTimeShort } from '../lib/format';
import type { ChatMessage, ChatThread, TailorPrefillContext } from '../types/api';
import { RichPayloadCard } from '../components/RichPayloadCard';
import { SkeletonBlock } from '../components/ui/ScoreBadge';
import { useToast } from '../components/ui/Toast';

const QUICK_COMMANDS: Array<{ cmd: string; label: string }> = [
  { cmd: '/ajuda', label: 'Ajuda' },
  { cmd: '/perfil', label: 'Meu Perfil' },
  { cmd: '/vagas', label: 'Buscar Vagas' },
  { cmd: '/cv', label: 'Avaliar CV' },
  { cmd: '/entrevista', label: 'Entrevista' },
  { cmd: '/limpar', label: 'Limpar Memória' },
];

type WsStatus = 'connecting' | 'connected' | 'disconnected';

interface ChatViewProps {
  onOpenCvStudio: (prefill: TailorPrefillContext) => void;
  onNavigateTab: (tab: 'jobs' | 'cv' | 'profile' | 'applications' | 'system') => void;
}

function renderFormattedLine(line: string, keyPrefix: string): React.ReactNode {
  // Split inline code `...`, bold *...* or **...**, and http(s) URLs safely
  const tokenRegex = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`|https?:\/\/[^\s)]+)/g;
  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(line)) !== null) {
    if (match.index > lastIdx) {
      parts.push(line.slice(lastIdx, match.index));
    }
    const token = match[0];
    const tokenKey = `${keyPrefix}-${match.index}`;
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={tokenKey} className="font-semibold text-slate-50">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <strong key={tokenKey} className="font-semibold text-slate-50">
          {token.slice(1, -1)}
        </strong>,
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={tokenKey}
          className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[12px] text-emerald-300"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith('http://') || token.startsWith('https://')) {
      parts.push(
        <a
          key={tokenKey}
          href={token}
          target="_blank"
          rel="noopener noreferrer"
          className="break-all text-sky-400 underline underline-offset-2 hover:text-sky-300"
        >
          {token}
        </a>,
      );
    }
    lastIdx = match.index + token.length;
  }

  if (lastIdx < line.length) {
    parts.push(line.slice(lastIdx));
  }
  return parts.length ? parts : line;
}

function renderFormattedMessage(content: string): React.ReactNode {
  const lines = content.split('\n');
  return lines.map((line, idx) => (
    <React.Fragment key={idx}>
      {renderFormattedLine(line, `l-${idx}`)}
      {idx < lines.length - 1 && <br />}
    </React.Fragment>
  ));
}

export const ChatView: React.FC<ChatViewProps> = ({ onOpenCvStudio, onNavigateTab }) => {
  const { token, user } = useAuth();
  const { pushToast } = useToast();

  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(true);
  const [threadsError, setThreadsError] = useState<string | null>(null);
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState<string | null>(null);

  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [botThinking, setBotThinking] = useState(false);
  const [wsStatus, setWsStatus] = useState<WsStatus>('disconnected');

  const wsRef = useRef<WebSocket | null>(null);
  const activeThreadRef = useRef<number | null>(activeThreadId);
  const skipNextMessageLoadRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    activeThreadRef.current = activeThreadId;
  }, [activeThreadId]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, botThinking, scrollToBottom]);

  const loadThreads = useCallback(async (selectFirstIfNone = false) => {
    setThreadsError(null);
    try {
      const res = await api.chat.listThreads();
      setThreads(res.items);
      if (selectFirstIfNone && res.items.length > 0 && activeThreadRef.current === null) {
        setActiveThreadId(res.items[0].id);
      }
    } catch (err) {
      setThreadsError(err instanceof ApiError ? err.detail : 'Erro ao carregar conversas.');
    } finally {
      setThreadsLoading(false);
    }
  }, []);

  const loadMessages = useCallback(async (threadId: number) => {
    setMessagesLoading(true);
    setMessagesError(null);
    try {
      const res = await api.chat.listMessages(threadId);
      setMessages(res.items);
    } catch (err) {
      setMessagesError(err instanceof ApiError ? err.detail : 'Erro ao carregar mensagens.');
    } finally {
      setMessagesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadThreads(true);
  }, [loadThreads]);

  useEffect(() => {
    if (activeThreadId !== null) {
      if (skipNextMessageLoadRef.current === activeThreadId) {
        skipNextMessageLoadRef.current = null;
        return;
      }
      void loadMessages(activeThreadId);
    } else {
      setMessages([]);
    }
  }, [activeThreadId, loadMessages]);

  // WebSocket connection with first-frame auth, heartbeat & automatic reconnect
  useEffect(() => {
    if (!token) return;

    let closedByCleanup = false;
    let reconnectTimer: number | undefined;
    let pingTimer: number | undefined;
    let attempt = 0;

    const connect = () => {
      if (closedByCleanup) return;
      setWsStatus('connecting');
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${protocol}//${window.location.host}/ws/chat`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        attempt = 0;
        ws.send(JSON.stringify({ type: 'auth', token }));
        pingTimer = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as Record<string, unknown>;
          const type = String(data.type || '');
          if (type === 'connected') {
            setWsStatus('connected');
          } else if (type === 'status' && data.status === 'thinking') {
            setBotThinking(true);
          } else if (type === 'assistant_message') {
            setBotThinking(false);
            setSending(false);
            const respThreadId =
              typeof data.thread_id === 'number' ? data.thread_id : activeThreadRef.current;

            if (respThreadId && activeThreadRef.current === null) {
              skipNextMessageLoadRef.current = respThreadId;
              setActiveThreadId(respThreadId);
            }

            const assistantMsg: ChatMessage = {
              id: Date.now() + Math.floor(Math.random() * 1000),
              thread_id: respThreadId || 0,
              role: 'assistant',
              channel: 'web',
              content: String(data.content || ''),
              rich_payload:
                data.rich_payload && typeof data.rich_payload === 'object'
                  ? (data.rich_payload as Record<string, unknown>)
                  : null,
              created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
            void loadThreads(false);
          } else if (type === 'error') {
            setBotThinking(false);
            setSending(false);
            pushToast(String(data.detail || 'Erro no WebSocket do chat.'), 'error');
          }
        } catch {
          // Ignora frame malformado
        }
      };

      ws.onerror = () => {
        setWsStatus('disconnected');
      };

      ws.onclose = () => {
        if (pingTimer) window.clearInterval(pingTimer);
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        setWsStatus('disconnected');
        setBotThinking(false);
        setSending(false);
        if (!closedByCleanup) {
          const delay = Math.min(12000, 1500 * Math.pow(2, attempt));
          attempt += 1;
          reconnectTimer = window.setTimeout(connect, delay);
        }
      };
    };

    connect();

    return () => {
      closedByCleanup = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (pingTimer) window.clearInterval(pingTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [token, loadThreads, pushToast]);

  const handleCreateThread = async () => {
    try {
      const created = await api.chat.createThread('Nova conversa', 'career');
      skipNextMessageLoadRef.current = created.id;
      setThreads((prev) => [created, ...prev]);
      setActiveThreadId(created.id);
      setMessages([]);
      if (window.innerWidth < 768) setSidebarOpen(false);
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao criar conversa.', 'error');
    }
  };

  const handleDeleteThread = async (threadId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.chat.deleteThread(threadId);
      setThreads((prev) => {
        const remaining = prev.filter((t) => t.id !== threadId);
        if (activeThreadId === threadId) {
          setActiveThreadId(remaining[0]?.id ?? null);
        }
        return remaining;
      });
      pushToast('Conversa removida.', 'info');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao remover conversa.', 'error');
    }
  };

  const sendTextMessage = async (rawText: string) => {
    const content = rawText.trim();
    if (!content || sending) return;

    setSending(true);
    setInput('');

    let targetThreadId = activeThreadId;
    if (targetThreadId === null) {
      try {
        const created = await api.chat.createThread(content.slice(0, 60), 'career');
        targetThreadId = created.id;
        activeThreadRef.current = created.id;
        skipNextMessageLoadRef.current = created.id;
        setActiveThreadId(created.id);
        setThreads((prev) => [created, ...prev]);
      } catch (err) {
        setSending(false);
        pushToast(err instanceof ApiError ? err.detail : 'Erro ao iniciar conversa.', 'error');
        return;
      }
    }

    const optimisticUserMsg: ChatMessage = {
      id: Date.now(),
      thread_id: targetThreadId,
      role: 'user',
      channel: 'web',
      content,
      rich_payload: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN && wsStatus === 'connected') {
      try {
        setBotThinking(true);
        ws.send(
          JSON.stringify({
            type: 'message',
            thread_id: targetThreadId,
            content,
          }),
        );
        return;
      } catch {
        setBotThinking(false);
        // Segue para fallback HTTP
      }
    }

    // Fallback HTTP automático caso WebSocket esteja desconectado
    try {
      setBotThinking(true);
      const res = await api.chat.sendMessageHttp(targetThreadId, content);
      if (res.messages && res.messages.length > 0) {
        const assistantMsgs = res.messages.filter((m) => m.role === 'assistant');
        if (assistantMsgs.length > 0) {
          setMessages((prev) => [...prev, ...assistantMsgs]);
        }
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            thread_id: targetThreadId!,
            role: 'assistant',
            channel: 'web',
            content: res.reply_text,
            rich_payload: res.rich_payload,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      void loadThreads(false);
    } catch (err) {
      pushToast(
        err instanceof ApiError ? err.detail : 'Erro ao enviar mensagem ao agente.',
        'error',
      );
    } finally {
      setBotThinking(false);
      setSending(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void sendTextMessage(input);
  };

  const activeThread = threads.find((t) => t.id === activeThreadId) || null;

  return (
    <div className="flex h-full min-h-0 flex-col md:flex-row">
      {/* Threads sidebar */}
      {sidebarOpen && (
        <aside className="flex max-h-64 w-full shrink-0 flex-col border-b border-slate-800/90 bg-[#0e131c] md:max-h-none md:w-72 md:border-b-0 md:border-r">
          <div className="flex items-center justify-between border-b border-slate-800/80 px-3.5 py-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Conversas
            </h2>
            <button
              type="button"
              onClick={() => void handleCreateThread()}
              className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-500/25"
            >
              <MessageSquarePlus className="h-3.5 w-3.5" />
              Nova
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {threadsLoading ? (
              <div className="space-y-2 p-2">
                <SkeletonBlock className="h-11" />
                <SkeletonBlock className="h-11" />
                <SkeletonBlock className="h-11" />
              </div>
            ) : threadsError ? (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">
                <p>{threadsError}</p>
                <button
                  type="button"
                  onClick={() => void loadThreads(true)}
                  className="mt-2 font-medium text-rose-100 underline"
                >
                  Tentar novamente
                </button>
              </div>
            ) : threads.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-[#8896ab]">
                Nenhuma conversa salva ainda. Envie uma mensagem ou clique em um atalho para
                iniciar.
              </div>
            ) : (
              threads.map((thread) => {
                const selected = thread.id === activeThreadId;
                return (
                  <div
                    key={thread.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setActiveThreadId(thread.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setActiveThreadId(thread.id);
                      }
                    }}
                    className={`group flex cursor-pointer items-center justify-between gap-2 rounded-lg px-2.5 py-2 transition-colors ${
                      selected
                        ? 'bg-slate-800/90 text-slate-50 ring-1 ring-inset ring-slate-700'
                        : 'text-slate-300 hover:bg-slate-800/45'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-xs font-medium">{thread.title}</div>
                      <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-[#8896ab]">
                        {thread.channel_origin === 'whatsapp' && (
                          <span className="inline-flex items-center gap-0.5 rounded bg-emerald-500/15 px-1 text-emerald-300">
                            <Smartphone className="h-2.5 w-2.5" />
                            WhatsApp
                          </span>
                        )}
                        <span>{formatRelativeDate(thread.updated_at)}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => void handleDeleteThread(thread.id, e)}
                      className="rounded p-1 text-slate-500 opacity-0 transition-opacity hover:bg-rose-500/15 hover:text-rose-300 group-hover:opacity-100 focus:opacity-100"
                      aria-label={`Excluir conversa ${thread.title}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </aside>
      )}

      {/* Active chat workspace */}
      <section className="flex min-h-0 flex-1 flex-col bg-[#0b0e14]">
        {/* Chat top bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 bg-[#0f141e]/70 px-4 py-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              type="button"
              onClick={() => setSidebarOpen((v) => !v)}
              className="rounded-md border border-slate-700/80 bg-slate-800/60 p-1.5 text-slate-300 hover:bg-slate-800 hover:text-slate-100"
              aria-label={sidebarOpen ? 'Ocultar lista de conversas' : 'Mostrar lista de conversas'}
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold text-slate-100">
                {activeThread?.title || 'Command Center C3PO'}
              </h1>
              <p className="text-[11px] text-[#8896ab]">
                Sessão sincronizada com comandos de carreira e automação
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                wsStatus === 'connected'
                  ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300'
                  : wsStatus === 'connecting'
                    ? 'border-amber-500/35 bg-amber-500/10 text-amber-300'
                    : 'border-slate-700 bg-slate-800 text-slate-300'
              }`}
              title={
                wsStatus === 'connected'
                  ? 'WebSocket conectado em tempo real'
                  : 'WebSocket indisponível — fallback HTTP ativo automaticamente'
              }
            >
              {wsStatus === 'connected' ? (
                <>
                  <Wifi className="h-3 w-3" />
                  Tempo real
                </>
              ) : wsStatus === 'connecting' ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Conectando...
                </>
              ) : (
                <>
                  <WifiOff className="h-3 w-3 text-amber-400" />
                  HTTP Fallback
                </>
              )}
            </span>
          </div>
        </div>

        {/* Messages stream */}
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="mx-auto max-w-3xl space-y-4">
            {messagesLoading ? (
              <div className="space-y-4">
                <SkeletonBlock className="ml-auto h-12 w-2/3" />
                <SkeletonBlock className="h-24 w-4/5" />
                <SkeletonBlock className="ml-auto h-10 w-1/2" />
              </div>
            ) : messagesError ? (
              <div className="flex items-center justify-between rounded-lg border border-rose-500/35 bg-rose-500/10 p-4 text-xs text-rose-200">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-rose-400" />
                  <span>{messagesError}</span>
                </div>
                {activeThreadId && (
                  <button
                    type="button"
                    onClick={() => void loadMessages(activeThreadId)}
                    className="rounded border border-rose-400/40 px-2.5 py-1 font-medium hover:bg-rose-500/20"
                  >
                    Recarregar
                  </button>
                )}
              </div>
            ) : messages.length === 0 ? (
              <div className="rounded-xl border border-slate-800 bg-[#111621] p-6 text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                  <Terminal className="h-5 w-5" />
                </div>
                <h2 className="mt-3 text-base font-semibold text-slate-100">
                  Olá, {user?.nome || 'Operador'}
                </h2>
                <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-400">
                  Use linguagem natural ou comandos rápidos abaixo para ver seu perfil, buscar vagas
                  compatíveis, avaliar/otimizar seu currículo para ATS ou treinar para entrevistas.
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {QUICK_COMMANDS.map((item) => (
                    <button
                      key={item.cmd}
                      type="button"
                      onClick={() => void sendTextMessage(item.cmd)}
                      className="rounded-lg border border-slate-700/80 bg-[#161d2b] px-3 py-1.5 text-xs text-slate-200 transition-colors hover:border-emerald-500/40 hover:bg-slate-800"
                    >
                      <span className="font-mono text-emerald-400">{item.cmd}</span>{' '}
                      <span className="text-slate-400">· {item.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => {
                const isUser = msg.role === 'user';
                return (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
                  >
                    <div
                      className={`max-w-[90%] rounded-xl px-4 py-3 text-sm leading-relaxed sm:max-w-[82%] ${
                        isUser
                          ? 'border border-emerald-500/25 bg-emerald-500/12 text-slate-50'
                          : 'border border-slate-800 bg-[#121722] text-slate-200'
                      }`}
                    >
                      <div className="break-words text-[13.5px] leading-relaxed">
                        {renderFormattedMessage(msg.content)}
                      </div>

                      {!isUser && msg.rich_payload && (
                        <RichPayloadCard
                          payload={msg.rich_payload}
                          onOpenCvStudio={onOpenCvStudio}
                          onNavigateTab={onNavigateTab}
                        />
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-1.5 px-1 text-[10px] text-[#8896ab]">
                      <span>{isUser ? 'Você' : 'C3PO'}</span>
                      {msg.channel === 'whatsapp' && (
                        <span className="font-mono text-emerald-400">via WhatsApp</span>
                      )}
                      {msg.created_at && <span>· {formatTimeShort(msg.created_at)}</span>}
                    </div>
                  </div>
                );
              })
            )}

            {botThinking && (
              <div className="flex items-start">
                <div className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-[#121722] px-4 py-2.5 text-xs text-slate-300">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-400" />
                  <span>C3PO processando...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Composer + quick slash shortcuts */}
        <div className="border-t border-slate-800/90 bg-[#0f141e] px-4 py-3 sm:px-6">
          <div className="mx-auto max-w-3xl space-y-2.5">
            <div className="flex flex-wrap items-center gap-1.5">
              {QUICK_COMMANDS.map((q) => (
                <button
                  key={q.cmd}
                  type="button"
                  disabled={sending}
                  onClick={() => void sendTextMessage(q.cmd)}
                  className="rounded-md border border-slate-700/70 bg-[#151c29] px-2 py-1 font-mono text-[11px] text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300 disabled:opacity-50"
                >
                  {q.cmd}
                </button>
              ))}
            </div>

            <form onSubmit={handleSubmit} className="flex items-end gap-2">
              <textarea
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    void sendTextMessage(input);
                  }
                }}
                placeholder="Digite uma mensagem, cole uma URL de vaga com /vaga <url> ou use /avaliar..."
                className="max-h-36 min-h-[42px] flex-1 resize-y rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3.5 py-2.5 text-sm text-slate-100 placeholder-[#8896ab] focus:border-emerald-500/70 focus:outline-none"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="inline-flex h-[42px] shrink-0 items-center gap-2 rounded-lg bg-emerald-500 px-4 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {sending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                <span className="hidden sm:inline">Enviar</span>
              </button>
            </form>
          </div>
        </div>
      </section>
    </div>
  );
};
