import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  MessageSquareCode,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ApiError, api } from '../lib/api';

type AuthMode = 'otp' | 'password';

export const AuthPage: React.FC = () => {
  const { loginWithToken, sessionNotice, clearSessionNotice } = useAuth();
  const [mode, setMode] = useState<AuthMode>('otp');

  // OTP state
  const [phoneOrJid, setPhoneOrJid] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [otpMessage, setOtpMessage] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);

  // Password login state
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const id = window.setInterval(() => {
      setSecondsLeft((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => window.clearInterval(id);
  }, [secondsLeft]);

  const formatTimer = (totalSec: number) => {
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const switchMode = (next: AuthMode) => {
    setMode(next);
    setErrorMsg(null);
    clearSessionNotice();
  };

  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = phoneOrJid.trim();
    if (cleaned.length < 6) {
      setErrorMsg('Informe seu número de WhatsApp (com DDD/DDI) ou JID.');
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);
    clearSessionNotice();
    try {
      const res = await api.auth.requestOtp(cleaned);
      if (res.status === 'unavailable' || res.delivery === 'unconfigured') {
        setOtpSent(false);
        setErrorMsg(
          res.message
            ? `${res.message} Utilize a aba "Senha Web" ou configure a Evolution API.`
            : 'Envio de OTP via WhatsApp indisponível. Utilize a aba "Senha Web" ou configure a Evolution API.',
        );
        return;
      }
      setOtpSent(true);
      setOtpCode('');
      setOtpMessage(res.message);
      setSecondsLeft(res.expires_in_seconds || 300);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Falha ao solicitar código OTP.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const code = otpCode.replace(/\s+/g, '').trim();
    if (code.length < 4) {
      setErrorMsg('Digite o código de 6 dígitos recebido.');
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await api.auth.verifyOtp(phoneOrJid.trim(), code);
      loginWithToken(res.access_token, res.user);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Código inválido ou expirado.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLoginPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password) {
      setErrorMsg('Informe seu identificador e senha web.');
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);
    clearSessionNotice();
    try {
      const res = await api.auth.loginPassword(identifier.trim(), password);
      loginWithToken(res.access_token, res.user);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Não foi possível entrar.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-[#0b0e14] text-slate-100 lg:grid lg:grid-cols-[1.05fr_0.95fr]">
      {/* Left context column */}
      <aside className="flex flex-col justify-between border-b border-slate-800/80 bg-[#0f141e] px-6 py-8 sm:px-10 lg:border-b-0 lg:border-r lg:px-14 lg:py-12">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10">
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M5 7h14M5 12h9M5 17h14"
                stroke="#34d399"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
              <circle cx="18.5" cy="12" r="2.2" fill="#38bdf8" />
            </svg>
          </div>
          <div>
            <span className="text-base font-semibold tracking-tight text-slate-100">C3PO</span>
            <span className="ml-2 rounded border border-slate-700 bg-slate-800/80 px-1.5 py-0.5 font-mono text-[11px] text-slate-300">
              Career Studio
            </span>
          </div>
        </div>

        <div className="my-10 max-w-lg space-y-6 lg:my-0">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-slate-50 sm:text-4xl">
            Central de Carreira, Vagas e Automação Omnichannel
          </h1>
          <p className="text-sm leading-relaxed text-slate-300 sm:text-base">
            Converse em tempo real com o agente C3PO sincronizado com seu WhatsApp, descubra vagas
            compatíveis em fontes gratuitas e otimize currículos com análise ATS antes e depois —
            com geração imediata de PDF e DOCX em Português ou Inglês.
          </p>

          <dl className="grid grid-cols-1 gap-3 border-t border-slate-800 pt-6 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-800/90 bg-[#131926] p-3.5">
              <dt className="text-xs font-medium text-emerald-400">Radar &amp; Match Score</dt>
              <dd className="mt-1 text-xs leading-relaxed text-slate-300">
                GitHub BR, Remotive, Arbeitnow, Himalayas, Greenhouse e Lever com filtro de
                dealbreakers.
              </dd>
            </div>
            <div className="rounded-lg border border-slate-800/90 bg-[#131926] p-3.5">
              <dt className="text-xs font-medium text-sky-400">CV Studio Anti-Alucinação</dt>
              <dd className="mt-1 text-xs leading-relaxed text-slate-300">
                Avaliação ATS transparente, editor Markdown e exportação em PDF/DOCX sem inventar
                experiências.
              </dd>
            </div>
          </dl>
        </div>

        <div className="flex items-center gap-2 text-xs text-[#8896ab]">
          <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-400" />
          <span>
            Primeiro acesso? Registre-se no WhatsApp enviando{' '}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-slate-200">
              /registrar &lt;senha&gt; &lt;nome&gt;
            </code>
          </span>
        </div>
      </aside>

      {/* Right auth form column */}
      <main className="flex flex-1 items-center justify-center px-6 py-10 sm:px-10">
        <div className="w-full max-w-md space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Acessar painel C3PO</h2>
            <p className="mt-1 text-sm text-slate-400">
              Escolha entre receber um código único no WhatsApp ou usar sua senha web.
            </p>
          </div>

          {sessionNotice && (
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/35 bg-amber-500/10 px-3.5 py-3 text-xs text-amber-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
              <span>{sessionNotice}</span>
            </div>
          )}

          {/* Auth mode tabs */}
          <div
            role="tablist"
            aria-label="Método de autenticação"
            className="grid grid-cols-2 gap-1 rounded-lg border border-slate-800 bg-[#111621] p-1"
          >
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'otp'}
              onClick={() => switchMode('otp')}
              className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors sm:text-sm ${
                mode === 'otp'
                  ? 'bg-slate-800 text-slate-50 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquareCode className="h-4 w-4 text-emerald-400" />
              Código WhatsApp
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'password'}
              onClick={() => switchMode('password')}
              className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors sm:text-sm ${
                mode === 'password'
                  ? 'bg-slate-800 text-slate-50 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <KeyRound className="h-4 w-4 text-sky-400" />
              Senha Web
            </button>
          </div>

          {errorMsg && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3.5 py-3 text-xs leading-relaxed text-rose-200"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
              <span>{errorMsg}</span>
            </div>
          )}

          {mode === 'otp' ? (
            !otpSent ? (
              <form onSubmit={handleRequestOtp} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="otp-phone" className="block text-xs font-medium text-slate-300">
                    Telefone WhatsApp ou Remote JID
                  </label>
                  <input
                    id="otp-phone"
                    type="text"
                    autoComplete="tel"
                    value={phoneOrJid}
                    onChange={(e) => setPhoneOrJid(e.target.value)}
                    placeholder="Ex: 5511999999999 ou 5511999999999@s.whatsapp.net"
                    className="w-full rounded-lg border border-slate-700/80 bg-[#111621] px-3.5 py-2.5 text-sm text-slate-100 placeholder-[#8896ab] transition-colors focus:border-emerald-500/70 focus:outline-none"
                    required
                  />
                  <p className="text-[11px] text-[#8896ab]">
                    Enviaremos um código temporário de 6 dígitos válido por 5 minutos.
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Enviando código...
                    </>
                  ) : (
                    <>
                      Enviar código no WhatsApp
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </form>
            ) : (
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                {otpMessage && (
                  <div className="flex items-start gap-2.5 rounded-lg border border-emerald-500/35 bg-emerald-500/10 px-3.5 py-3 text-xs leading-relaxed text-emerald-100">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    <div className="space-y-1">
                      <p>{otpMessage}</p>
                      <p className="font-mono text-[11px] opacity-80">
                        Destino: {phoneOrJid} · Expira em{' '}
                        <span className="tabular-nums font-semibold">
                          {formatTimer(secondsLeft)}
                        </span>
                      </p>
                    </div>
                  </div>
                )}

                <div className="space-y-1.5">
                  <label htmlFor="otp-code" className="block text-xs font-medium text-slate-300">
                    Código de 6 dígitos
                  </label>
                  <input
                    id="otp-code"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={8}
                    autoFocus
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    placeholder="000000"
                    className="w-full rounded-lg border border-slate-700/80 bg-[#111621] px-4 py-3 text-center font-mono text-2xl font-semibold tracking-[0.4em] text-slate-50 placeholder-[#8896ab] tabular-nums focus:border-emerald-500/70 focus:outline-none"
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Validando...
                    </>
                  ) : (
                    <>
                      Validar e entrar
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>

                <div className="flex items-center justify-between pt-1 text-xs">
                  <button
                    type="button"
                    onClick={() => {
                      setOtpSent(false);
                      setOtpCode('');
                      setErrorMsg(null);
                    }}
                    className="text-slate-400 underline-offset-4 hover:text-slate-200 hover:underline"
                  >
                    Alterar telefone
                  </button>
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={(e) => void handleRequestOtp(e as unknown as React.FormEvent)}
                    className="inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 disabled:opacity-50"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Reenviar código
                  </button>
                </div>
              </form>
            )
          ) : (
            <form onSubmit={handleLoginPassword} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="pwd-identifier" className="block text-xs font-medium text-slate-300">
                  Telefone, JID ou Nome cadastrado
                </label>
                <input
                  id="pwd-identifier"
                  type="text"
                  autoComplete="username"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="Ex: 5511999999999 ou Arthur"
                  className="w-full rounded-lg border border-slate-700/80 bg-[#111621] px-3.5 py-2.5 text-sm text-slate-100 placeholder-[#8896ab] transition-colors focus:border-sky-500/70 focus:outline-none"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="pwd-secret" className="block text-xs font-medium text-slate-300">
                  Senha Web
                </label>
                <div className="relative">
                  <input
                    id="pwd-secret"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Sua senha web configurada"
                    className="w-full rounded-lg border border-slate-700/80 bg-[#111621] py-2.5 pl-3.5 pr-10 text-sm text-slate-100 placeholder-[#8896ab] transition-colors focus:border-sky-500/70 focus:outline-none"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:text-slate-200"
                    aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-[#8896ab]">
                  Defina ou altere sua senha web dentro da aba Sistema após o primeiro login via OTP.
                </p>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Entrando...
                  </>
                ) : (
                  <>
                    Entrar com senha web
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </main>
    </div>
  );
};
