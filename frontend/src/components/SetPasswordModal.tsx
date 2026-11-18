import React, { useState } from 'react';
import { KeyRound, Loader2, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ApiError, api } from '../lib/api';
import { Modal } from './ui/Modal';
import { useToast } from './ui/Toast';

interface SetPasswordModalProps {
  open: boolean;
  onClose: () => void;
}

export const SetPasswordModal: React.FC<SetPasswordModalProps> = ({ open, onClose }) => {
  const { user, refreshUser } = useAuth();
  const { pushToast } = useToast();
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (password.length < 6) {
      setErrorMsg('A senha web deve ter pelo menos 6 caracteres.');
      return;
    }
    if (password !== confirm) {
      setErrorMsg('As senhas informadas não coincidem.');
      return;
    }

    setSaving(true);
    try {
      const res = await api.auth.setPassword(
        password,
        currentPassword.trim() ? currentPassword : undefined,
      );
      await refreshUser();
      pushToast(res.message || 'Senha web configurada com sucesso.', 'success');
      setCurrentPassword('');
      setPassword('');
      setConfirm('');
      onClose();
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Erro ao atualizar senha web.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={user?.has_web_password ? 'Alterar Senha Web' : 'Definir Senha Web'}
      description="Permite acessar o painel mesmo sem estar com o WhatsApp disponível."
      maxWidthClass="max-w-md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {errorMsg && (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            {errorMsg}
          </div>
        )}

        <div className="space-y-1.5">
          <label htmlFor="modal-web-current-pwd" className="block text-xs font-medium text-slate-300">
            Senha Atual (se já possuir senha cadastrada)
          </label>
          <input
            id="modal-web-current-pwd"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="Opcional se ainda não definiu senha"
            className="w-full rounded-lg border border-slate-700 bg-[#0d111a] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="modal-web-pwd" className="block text-xs font-medium text-slate-300">
            Nova senha (mínimo 6 caracteres)
          </label>
          <input
            id="modal-web-pwd"
            type="password"
            autoComplete="new-password"
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Digite a nova senha web"
            className="w-full rounded-lg border border-slate-700 bg-[#0d111a] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
            required
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="modal-web-pwd-confirm" className="block text-xs font-medium text-slate-300">
            Confirmar nova senha
          </label>
          <input
            id="modal-web-pwd-confirm"
            type="password"
            autoComplete="new-password"
            minLength={6}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Repita a senha"
            className="w-full rounded-lg border border-slate-700 bg-[#0d111a] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
            required
          />
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-700 px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
          >
            {saving ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Salvando...
              </>
            ) : (
              <>
                <ShieldCheck className="h-3.5 w-3.5" />
                Salvar senha
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
};

export const PasswordBadgeButton: React.FC<{ onClick: () => void }> = ({ onClick }) => {
  const { user } = useAuth();
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between rounded-lg border border-slate-800 bg-[#131926] px-2.5 py-2 text-left text-xs transition-colors hover:border-slate-700 hover:bg-slate-800/70"
    >
      <span className="flex items-center gap-2 text-slate-300">
        <KeyRound className="h-3.5 w-3.5 text-sky-400" />
        <span>{user?.has_web_password ? 'Alterar senha web' : 'Definir senha web'}</span>
      </span>
      <span
        className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
          user?.has_web_password
            ? 'bg-emerald-500/15 text-emerald-300'
            : 'bg-amber-500/15 text-amber-300'
        }`}
      >
        {user?.has_web_password ? 'Ativa' : 'Pendente'}
      </span>
    </button>
  );
};
