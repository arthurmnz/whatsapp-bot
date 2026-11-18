import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertCircle,
  Cpu,
  KeyRound,
  Loader2,
  Lock,
  Monitor,
  Power,
  PowerOff,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ApiError, api } from '../lib/api';
import { APPLICATION_STAGES } from '../lib/format';
import type { DeviceActionResponse, SystemOverview } from '../types/api';
import { Modal } from '../components/ui/Modal';
import { SkeletonBlock } from '../components/ui/ScoreBadge';
import { useToast } from '../components/ui/Toast';

type DeviceAction = 'status' | 'wake' | 'restart' | 'shutdown';

const DEVICE_ACTIONS: Array<{
  action: DeviceAction;
  label: string;
  permission: string;
  description: string;
  destructive: boolean;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  {
    action: 'status',
    label: 'Verificar Status',
    permission: 'cmd:status_windows',
    description: 'Consulta via SSH se o PC Windows está online.',
    destructive: false,
    icon: Activity,
  },
  {
    action: 'wake',
    label: 'Ligar (Wake-on-LAN)',
    permission: 'cmd:wake_windows',
    description: 'Envia Magic Packet UDP na rede local.',
    destructive: false,
    icon: Zap,
  },
  {
    action: 'restart',
    label: 'Reiniciar PC',
    permission: 'cmd:restart_windows',
    description: 'Executa reinicialização imediata via SSH.',
    destructive: true,
    icon: RotateCcw,
  },
  {
    action: 'shutdown',
    label: 'Desligar PC',
    permission: 'cmd:shutdown_windows',
    description: 'Executa desligamento imediato via SSH.',
    destructive: true,
    icon: PowerOff,
  },
];

export const SystemView: React.FC = () => {
  const { user, hasPermission, refreshUser } = useAuth();
  const { pushToast } = useToast();

  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [runningAction, setRunningAction] = useState<DeviceAction | null>(null);
  const [deviceOutput, setDeviceOutput] = useState<DeviceActionResponse | null>(null);
  const [confirmAction, setConfirmAction] = useState<DeviceAction | null>(null);

  // Web password inline form
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPwd, setSavingPwd] = useState(false);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await api.system.overview();
      setOverview(data);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Erro ao carregar visão do sistema.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const executeDeviceAction = async (action: DeviceAction) => {
    setConfirmAction(null);
    setRunningAction(action);
    try {
      const res = await api.system.controlDevice(action);
      setDeviceOutput(res);
      pushToast(res.result?.message || `Ação "${action}" concluída.`, 'info');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Falha ao executar ação no dispositivo.', 'error');
    } finally {
      setRunningAction(null);
    }
  };

  const handleSetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) {
      pushToast('A senha deve ter pelo menos 6 caracteres.', 'error');
      return;
    }
    if (password !== confirmPassword) {
      pushToast('As senhas informadas não coincidem.', 'error');
      return;
    }

    setSavingPwd(true);
    try {
      const res = await api.auth.setPassword(
        password,
        currentPassword.trim() ? currentPassword : undefined,
      );
      await refreshUser();
      setCurrentPassword('');
      setPassword('');
      setConfirmPassword('');
      pushToast(res.message || 'Senha web atualizada.', 'success');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao salvar senha web.', 'error');
    } finally {
      setSavingPwd(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl space-y-5 p-6">
        <SkeletonBlock className="h-9 w-72" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-24" />
        </div>
        <SkeletonBlock className="h-64" />
      </div>
    );
  }

  if (errorMsg || !overview) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="flex items-center justify-between rounded-xl border border-rose-500/35 bg-rose-500/10 p-5 text-sm text-rose-200">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="h-5 w-5 text-rose-400" />
            <span>{errorMsg || 'Dados indisponíveis.'}</span>
          </div>
          <button
            type="button"
            onClick={() => void loadOverview()}
            className="rounded-lg border border-rose-400/40 px-3 py-1.5 text-xs font-medium hover:bg-rose-500/20"
          >
            Recarregar
          </button>
        </div>
      </div>
    );
  }

  const { counts, llm } = overview;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">
            Sistema, IA &amp; Controle de Dispositivos
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Visão consolidada do módulo de carreira, provedor LLM ativo, PC Windows e segurança web.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadOverview()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#111621] px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800"
        >
          <RefreshCw className="h-3.5 w-3.5 text-sky-400" />
          Atualizar métricas
        </button>
      </header>

      {/* Metrics summary strip */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        {[
          { label: 'Skills', val: counts.skills },
          { label: 'CVs Base', val: counts.base_resumes },
          { label: 'CVs Otimizados', val: counts.tailored_resumes },
          { label: 'Vagas Avaliadas', val: counts.matched_jobs },
          { label: 'Compatíveis ≥70%', val: counts.compatible_jobs },
          { label: 'Vagas Salvas', val: counts.saved_jobs },
          { label: 'Candidaturas Ativas', val: counts.active_applications },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-slate-800/90 bg-[#111621] px-3.5 py-3"
          >
            <div className="font-mono text-2xl font-bold tabular-nums text-slate-50">
              {item.val}
            </div>
            <div className="mt-0.5 text-[11px] text-[#8896ab]">{item.label}</div>
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* LLM Provider & Models */}
        <section className="space-y-4 rounded-xl border border-slate-800/90 bg-[#111621] p-5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
              <Cpu className="h-4 w-4 text-sky-400" />
              Motor &amp; Provedor de IA
            </h2>
            <div className="flex items-center gap-1.5">
              <span
                className={`rounded border px-2 py-0.5 font-mono text-[11px] ${
                  llm.is_local
                    ? 'border-sky-500/35 bg-sky-500/12 text-sky-300'
                    : 'border-slate-700 bg-slate-800 text-slate-300'
                }`}
              >
                {llm.is_local ? 'Modelo Local' : 'Provedor Externo'}
              </span>
              <span
                className={`rounded border px-2 py-0.5 font-mono text-[11px] ${
                  llm.available
                    ? 'border-emerald-500/35 bg-emerald-500/12 text-emerald-300'
                    : 'border-amber-500/35 bg-amber-500/12 text-amber-300'
                }`}
              >
                {llm.available ? 'Ativo' : 'Fallback Determinístico'}
              </span>
            </div>
          </div>

          <dl className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3">
              <dt className="text-[#8896ab]">Provedor</dt>
              <dd className="mt-1 font-mono font-semibold text-slate-100">{llm.provider}</dd>
            </div>
            <div className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3">
              <dt className="text-[#8896ab]">Temperatura</dt>
              <dd className="mt-1 font-mono font-semibold tabular-nums text-slate-100">
                {llm.temperature}
              </dd>
            </div>
            <div className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3">
              <dt className="text-[#8896ab]">Modelo de Chat</dt>
              <dd className="mt-1 break-all font-mono text-slate-200">{llm.chat_model}</dd>
            </div>
            <div className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3">
              <dt className="text-[#8896ab]">Modelo de CV &amp; ATS</dt>
              <dd className="mt-1 break-all font-mono text-slate-200">{llm.cv_model}</dd>
            </div>
            <div className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3 sm:col-span-2">
              <dt className="text-[#8896ab]">Base URL</dt>
              <dd className="mt-1 break-all font-mono text-slate-300">{llm.base_url}</dd>
            </div>
          </dl>

          {/* Applications stage summary */}
          {Object.keys(overview.applications_by_stage).length > 0 && (
            <div className="border-t border-slate-800 pt-3">
              <h3 className="mb-2 text-xs font-medium text-slate-300">
                Distribuição de Candidaturas
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {APPLICATION_STAGES.map((st) => {
                  const count = overview.applications_by_stage[st.id] || 0;
                  if (!count) return null;
                  return (
                    <span
                      key={st.id}
                      className={`rounded border px-2 py-0.5 text-[11px] font-medium ${st.pillClass}`}
                    >
                      {st.label}: <span className="font-mono tabular-nums">{count}</span>
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </section>

        {/* Windows PC Remote Control */}
        <section className="space-y-4 rounded-xl border border-slate-800/90 bg-[#111621] p-5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
              <Monitor className="h-4 w-4 text-emerald-400" />
              Controle do PC Windows (RBAC)
            </h2>
            <span className="font-mono text-[11px] uppercase text-slate-400">
              Perfil: {user?.role}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {DEVICE_ACTIONS.map((item) => {
              const allowed = hasPermission(item.permission);
              const Icon = item.icon;
              const isRunning = runningAction === item.action;

              return (
                <button
                  key={item.action}
                  type="button"
                  disabled={!allowed || runningAction !== null}
                  onClick={() => {
                    if (item.destructive) {
                      setConfirmAction(item.action);
                    } else {
                      void executeDeviceAction(item.action);
                    }
                  }}
                  className={`flex flex-col items-start justify-between rounded-xl border p-3.5 text-left transition-colors ${
                    !allowed
                      ? 'cursor-not-allowed border-slate-800/70 bg-[#0b0e14]/70 opacity-55'
                      : item.destructive
                        ? 'border-rose-500/30 bg-[#181117] hover:border-rose-500/60 hover:bg-rose-500/12'
                        : 'border-slate-800 bg-[#0c1018] hover:border-emerald-500/40 hover:bg-slate-800/60'
                  }`}
                >
                  <div className="flex w-full items-center justify-between">
                    <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-100">
                      {isRunning ? (
                        <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                      ) : (
                        <Icon
                          className={`h-4 w-4 ${
                            item.destructive ? 'text-rose-400' : 'text-emerald-400'
                          }`}
                        />
                      )}
                      {item.label}
                    </span>
                    {!allowed && <Lock className="h-3.5 w-3.5 text-slate-500" />}
                  </div>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-[#8896ab]">
                    {allowed
                      ? item.description
                      : `Requer permissão ${item.permission} no perfil.`}
                  </p>
                </button>
              );
            })}
          </div>

          {deviceOutput && (
            <div className="rounded-lg border border-slate-700 bg-[#0b0e14] p-3.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase text-sky-400">
                  Resposta ({deviceOutput.action})
                </span>
                {typeof deviceOutput.result?.online === 'boolean' && (
                  <span
                    className={`rounded px-2 py-0.5 font-mono text-[10px] font-semibold ${
                      deviceOutput.result.online
                        ? 'bg-emerald-500/15 text-emerald-300'
                        : 'bg-rose-500/15 text-rose-300'
                    }`}
                  >
                    {deviceOutput.result.online ? 'ONLINE' : 'OFFLINE'}
                  </span>
                )}
              </div>
              <p className="mt-1.5 text-slate-200">{deviceOutput.result?.message}</p>
            </div>
          )}
        </section>
      </div>

      {/* Web Password Configuration */}
      <section className="rounded-xl border border-slate-800/90 bg-[#111621] p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
              <KeyRound className="h-4 w-4 text-sky-400" />
              Segurança &amp; Senha de Acesso Web
            </h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Configure uma senha local para fazer login no painel mesmo quando o WhatsApp não
              estiver por perto.
            </p>
          </div>
          <span
            className={`rounded border px-2.5 py-1 font-mono text-[11px] ${
              user?.has_web_password
                ? 'border-emerald-500/35 bg-emerald-500/12 text-emerald-300'
                : 'border-amber-500/35 bg-amber-500/12 text-amber-300'
            }`}
          >
            {user?.has_web_password ? 'Senha web configurada' : 'Somente OTP ativo'}
          </span>
        </div>

        <form
          onSubmit={handleSetPassword}
          className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:items-end"
        >
          <div className="space-y-1">
            <label htmlFor="sys-current-pwd" className="block text-xs font-medium text-slate-300">
              Senha Atual (se já possuir senha cadastrada)
            </label>
            <input
              id="sys-current-pwd"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Opcional no 1º cadastro"
              className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab]"
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="sys-pwd" className="block text-xs font-medium text-slate-300">
              Nova senha web
            </label>
            <input
              id="sys-pwd"
              type="password"
              autoComplete="new-password"
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mínimo 6 caracteres"
              className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab]"
              required
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="sys-pwd-confirm" className="block text-xs font-medium text-slate-300">
              Confirmar senha
            </label>
            <input
              id="sys-pwd-confirm"
              type="password"
              autoComplete="new-password"
              minLength={6}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repita a senha"
              className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab]"
              required
            />
          </div>

          <button
            type="submit"
            disabled={savingPwd}
            className="inline-flex h-[38px] items-center justify-center gap-2 rounded-lg bg-sky-500 px-4 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-60"
          >
            {savingPwd ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ShieldCheck className="h-4 w-4" />
            )}
            {user?.has_web_password ? 'Atualizar Senha Web' : 'Definir Senha Web'}
          </button>
        </form>
      </section>

      {/* Confirmation modal for destructive PC commands */}
      <Modal
        open={confirmAction !== null}
        onClose={() => setConfirmAction(null)}
        title={
          confirmAction === 'shutdown'
            ? 'Confirmar desligamento do PC Windows'
            : 'Confirmar reinicialização do PC Windows'
        }
        description="Esta ação envia o comando imediatamente via SSH para a máquina configurada."
        maxWidthClass="max-w-md"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/35 bg-rose-500/10 p-3 text-xs text-rose-100">
            <Power className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
            <span>
              Tem certeza que deseja{' '}
              <strong>{confirmAction === 'shutdown' ? 'desligar' : 'reiniciar'}</strong> o PC
              Windows agora? Trabalhos não salvos podem ser perdidos.
            </span>
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmAction(null)}
              className="rounded-lg border border-slate-700 px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => confirmAction && void executeDeviceAction(confirmAction)}
              className="rounded-lg bg-rose-500 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-400"
            >
              Confirmar {confirmAction === 'shutdown' ? 'Desligamento' : 'Reinício'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
