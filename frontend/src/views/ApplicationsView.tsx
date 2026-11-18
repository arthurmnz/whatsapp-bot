import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  ExternalLink,
  FileText,
  KanbanSquare,
  LayoutList,
  Loader2,
  Plus,
  Sparkles,
  Target,
  Trash2,
} from 'lucide-react';
import { ApiError, api } from '../lib/api';
import {
  APPLICATION_STAGES,
  formatRelativeDate,
  sanitizeExternalUrl,
} from '../lib/format';
import type {
  ApplicationInterviewPrepResponse,
  ApplicationStage,
  JobApplication,
  TailoredResume,
  TailorPrefillContext,
} from '../types/api';
import { Modal } from '../components/ui/Modal';
import { SkeletonBlock } from '../components/ui/ScoreBadge';
import { useToast } from '../components/ui/Toast';

interface ApplicationsViewProps {
  onOpenCvStudio: (prefill: TailorPrefillContext) => void;
}

export const ApplicationsView: React.FC<ApplicationsViewProps> = ({ onOpenCvStudio }) => {
  const { pushToast } = useToast();

  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [tailoredResumes, setTailoredResumes] = useState<TailoredResume[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'kanban' | 'list'>('kanban');
  const [dragAppId, setDragAppId] = useState<number | null>(null);

  // Create / Edit modal
  const [formOpen, setFormOpen] = useState(false);
  const [editingApp, setEditingApp] = useState<JobApplication | null>(null);
  const [companyName, setCompanyName] = useState('');
  const [roleTitle, setRoleTitle] = useState('');
  const [jobUrl, setJobUrl] = useState('');
  const [stage, setStage] = useState<ApplicationStage>('wishlist');
  const [tailoredId, setTailoredId] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [savingForm, setSavingForm] = useState(false);

  // Interview prep modal
  const [prepModalOpen, setPrepModalOpen] = useState(false);
  const [prepLoading, setPrepLoading] = useState(false);
  const [prepLang, setPrepLang] = useState<'auto' | 'pt-BR' | 'en'>('auto');
  const [prepData, setPrepData] = useState<ApplicationInterviewPrepResponse | null>(null);
  const [prepTargetApp, setPrepTargetApp] = useState<JobApplication | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [appsRes, tailoredRes] = await Promise.all([
        api.applications.list(),
        api.resumes.listTailored(),
      ]);
      setApplications(appsRes.items);
      setTailoredResumes(tailoredRes.items);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Erro ao carregar candidaturas.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const openCreateModal = (initialStage: ApplicationStage = 'wishlist') => {
    setEditingApp(null);
    setCompanyName('');
    setRoleTitle('');
    setJobUrl('');
    setStage(initialStage);
    setTailoredId('');
    setNotes('');
    setFormOpen(true);
  };

  const openEditModal = (app: JobApplication) => {
    setEditingApp(app);
    setCompanyName(app.company_name);
    setRoleTitle(app.role_title);
    setJobUrl(app.job_url || '');
    setStage(app.stage);
    setTailoredId(app.tailored_resume_id ? String(app.tailored_resume_id) : '');
    setNotes(app.notes || '');
    setFormOpen(true);
  };

  const handleSaveForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim() || !roleTitle.trim()) {
      pushToast('Informe empresa e cargo.', 'error');
      return;
    }

    setSavingForm(true);
    try {
      if (editingApp) {
        const updated = await api.applications.update(editingApp.id, {
          company_name: companyName.trim(),
          role_title: roleTitle.trim(),
          job_url: jobUrl.trim(),
          stage,
          tailored_resume_id: tailoredId ? Number(tailoredId) : null,
          notes,
        });
        setApplications((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
        pushToast('Candidatura atualizada.', 'success');
      } else {
        const created = await api.applications.create({
          company_name: companyName.trim(),
          role_title: roleTitle.trim(),
          job_url: jobUrl.trim() || null,
          stage,
          tailored_resume_id: tailoredId ? Number(tailoredId) : null,
          notes: notes.trim() || null,
        });
        setApplications((prev) => [created, ...prev]);
        pushToast('Candidatura criada no funil!', 'success');
      }
      setFormOpen(false);
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao salvar candidatura.', 'error');
    } finally {
      setSavingForm(false);
    }
  };

  const handleMoveStage = async (appId: number, nextStage: ApplicationStage) => {
    try {
      const updated = await api.applications.update(appId, { stage: nextStage });
      setApplications((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao mover estágio.', 'error');
    }
  };

  const handleDeleteApp = async (appId: number) => {
    try {
      await api.applications.delete(appId);
      setApplications((prev) => prev.filter((a) => a.id !== appId));
      pushToast('Candidatura removida.', 'info');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao excluir candidatura.', 'error');
    }
  };

  const handleOpenInterviewPrep = async (
    app: JobApplication,
    lang: 'auto' | 'pt-BR' | 'en' = prepLang,
  ) => {
    setPrepTargetApp(app);
    setPrepModalOpen(true);
    setPrepLoading(true);
    try {
      const res = await api.applications.generateInterviewPrep(app.id, lang);
      setPrepData(res);
    } catch (err) {
      pushToast(
        err instanceof ApiError ? err.detail : 'Erro ao gerar guia de entrevista.',
        'error',
      );
      setPrepModalOpen(false);
    } finally {
      setPrepLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl space-y-5 p-6">
        <SkeletonBlock className="h-9 w-72" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <SkeletonBlock className="h-80" />
          <SkeletonBlock className="h-80" />
          <SkeletonBlock className="h-80" />
          <SkeletonBlock className="h-80" />
        </div>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="flex items-center justify-between rounded-xl border border-rose-500/35 bg-rose-500/10 p-5 text-sm text-rose-200">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="h-5 w-5 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
          <button
            type="button"
            onClick={() => void loadData()}
            className="rounded-lg border border-rose-400/40 px-3 py-1.5 text-xs font-medium hover:bg-rose-500/20"
          >
            Recarregar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-full max-w-[1480px] flex-col space-y-5 px-4 py-6 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">
            Kanban de Candidaturas &amp; Entrevistas
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Acompanhe cada processo seletivo por estágio e gere roteiros personalizados de
            entrevista.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-slate-800 bg-[#111621] p-1 text-xs">
            <button
              type="button"
              onClick={() => setViewMode('kanban')}
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-medium ${
                viewMode === 'kanban' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
              }`}
            >
              <KanbanSquare className="h-3.5 w-3.5 text-emerald-400" />
              Kanban
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-medium ${
                viewMode === 'list' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
              }`}
            >
              <LayoutList className="h-3.5 w-3.5 text-sky-400" />
              Lista
            </button>
          </div>

          <button
            type="button"
            onClick={() => openCreateModal('wishlist')}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400"
          >
            <Plus className="h-4 w-4" />
            Nova Candidatura
          </button>
        </div>
      </header>

      {applications.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-[#111621] p-10 text-center">
          <KanbanSquare className="mx-auto h-9 w-9 text-slate-500" />
          <h2 className="mt-3 text-base font-semibold text-slate-100">
            Nenhuma candidatura registrada ainda
          </h2>
          <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-400">
            Adicione uma candidatura manualmente ou envie uma vaga diretamente pelo Radar de Vagas
            ou CV Studio.
          </p>
          <button
            type="button"
            onClick={() => openCreateModal('wishlist')}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400"
          >
            <Plus className="h-4 w-4" />
            Criar primeira candidatura
          </button>
        </div>
      ) : viewMode === 'kanban' ? (
        <div className="flex flex-1 gap-3.5 overflow-x-auto pb-4">
          {APPLICATION_STAGES.map((col) => {
            const colItems = applications.filter((a) => a.stage === col.id);
            return (
              <section
                key={col.id}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragAppId !== null) {
                    void handleMoveStage(dragAppId, col.id);
                    setDragAppId(null);
                  }
                }}
                className="flex w-72 shrink-0 flex-col rounded-xl border border-slate-800/90 bg-[#111621]"
              >
                <div className="flex items-center justify-between border-b border-slate-800 px-3.5 py-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded border px-2 py-0.5 text-[11px] font-medium ${col.pillClass}`}
                    >
                      {col.label}
                    </span>
                    <span className="font-mono text-xs text-slate-400 tabular-nums">
                      {colItems.length}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => openCreateModal(col.id)}
                    className="rounded p-1 text-slate-500 hover:bg-slate-800 hover:text-slate-200"
                    aria-label={`Adicionar em ${col.label}`}
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="flex-1 space-y-2.5 overflow-y-auto p-2.5">
                  {colItems.map((app) => {
                    const safeUrl = sanitizeExternalUrl(app.job_url);
                    return (
                      <article
                        key={app.id}
                        draggable
                        onDragStart={() => setDragAppId(app.id)}
                        onDragEnd={() => setDragAppId(null)}
                        className="cursor-grab rounded-lg border border-slate-800 bg-[#0c1018] p-3 text-xs transition-colors hover:border-slate-700 active:cursor-grabbing"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => openEditModal(app)}
                            className="min-w-0 flex-1 text-left"
                          >
                            <div className="font-semibold text-slate-100 hover:text-emerald-300">
                              {app.role_title}
                            </div>
                            <div className="mt-0.5 text-[11px] text-slate-400">
                              {app.company_name}
                            </div>
                          </button>

                          {safeUrl && (
                            <a
                              href={safeUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-sky-300"
                              aria-label="Abrir link da vaga"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          )}
                        </div>

                        {app.notes && (
                          <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-slate-400">
                            {app.notes}
                          </p>
                        )}

                        <div className="mt-2.5 flex flex-wrap items-center justify-between gap-1.5 border-t border-slate-800/80 pt-2">
                          <select
                            aria-label={`Estágio de ${app.role_title}`}
                            value={app.stage}
                            onChange={(e) =>
                              void handleMoveStage(app.id, e.target.value as ApplicationStage)
                            }
                            className="max-w-[130px] rounded border border-slate-700 bg-[#111621] px-1.5 py-1 text-[11px] text-slate-200"
                          >
                            {APPLICATION_STAGES.map((st) => (
                              <option key={st.id} value={st.id}>
                                {st.label}
                              </option>
                            ))}
                          </select>

                          <div className="flex items-center gap-1">
                            {app.tailored_resume_id && (
                              <button
                                type="button"
                                onClick={() =>
                                  onOpenCvStudio({ tailoredResumeId: app.tailored_resume_id })
                                }
                                title="Abrir CV otimizado vinculado"
                                className="rounded p-1 text-sky-400 hover:bg-sky-500/15"
                              >
                                <FileText className="h-3.5 w-3.5" />
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => void handleOpenInterviewPrep(app)}
                              title="Gerar / Ver Guia de Entrevista"
                              className="inline-flex items-center gap-1 rounded border border-amber-500/35 bg-amber-500/12 px-2 py-1 text-[11px] font-medium text-amber-200 hover:bg-amber-500/20"
                            >
                              <Target className="h-3 w-3" />
                              Entrevista
                            </button>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-800/90 bg-[#111621]">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 bg-[#0e131c] text-[11px] uppercase tracking-wider text-slate-400">
                  <th className="px-4 py-3 font-medium">Cargo</th>
                  <th className="px-4 py-3 font-medium">Empresa</th>
                  <th className="px-4 py-3 font-medium">Estágio</th>
                  <th className="px-4 py-3 font-medium">Atualizado</th>
                  <th className="px-4 py-3 text-right font-medium">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {applications.map((app) => (
                  <tr key={app.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3 font-semibold text-slate-100">
                      <button
                        type="button"
                        onClick={() => openEditModal(app)}
                        className="text-left hover:text-emerald-300"
                      >
                        {app.role_title}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{app.company_name}</td>
                    <td className="px-4 py-3">
                      <select
                        value={app.stage}
                        onChange={(e) =>
                          void handleMoveStage(app.id, e.target.value as ApplicationStage)
                        }
                        className="rounded border border-slate-700 bg-[#0b0e14] px-2 py-1 text-xs text-slate-200"
                      >
                        {APPLICATION_STAGES.map((st) => (
                          <option key={st.id} value={st.id}>
                            {st.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3 text-[#8896ab]">
                      {formatRelativeDate(app.updated_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => void handleOpenInterviewPrep(app)}
                          className="inline-flex items-center gap-1 rounded border border-amber-500/35 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-200 hover:bg-amber-500/20"
                        >
                          <Sparkles className="h-3 w-3" />
                          Guia Entrevista
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeleteApp(app.id)}
                          className="rounded p-1 text-slate-500 hover:bg-rose-500/15 hover:text-rose-300"
                          aria-label="Excluir candidatura"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create / Edit Application Modal */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingApp ? 'Editar Candidatura' : 'Nova Candidatura'}
        maxWidthClass="max-w-lg"
      >
        <form onSubmit={handleSaveForm} className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <label htmlFor="app-company" className="block text-xs font-medium text-slate-300">
                Empresa
              </label>
              <input
                id="app-company"
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Ex: Nubank"
                className="w-full rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab]"
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="app-role" className="block text-xs font-medium text-slate-300">
                Cargo
              </label>
              <input
                id="app-role"
                type="text"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                placeholder="Ex: Senior Python Engineer"
                className="w-full rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab]"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <label htmlFor="app-stage" className="block text-xs font-medium text-slate-300">
                Estágio Atual
              </label>
              <select
                id="app-stage"
                value={stage}
                onChange={(e) => setStage(e.target.value as ApplicationStage)}
                className="w-full rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-2 text-xs text-slate-100"
              >
                {APPLICATION_STAGES.map((st) => (
                  <option key={st.id} value={st.id}>
                    {st.label}
                  </option>
                ))}
                <option value="withdrawn">Desistência</option>
              </select>
            </div>

            <div className="space-y-1">
              <label htmlFor="app-cv" className="block text-xs font-medium text-slate-300">
                Currículo Otimizado (opcional)
              </label>
              <select
                id="app-cv"
                value={tailoredId}
                onChange={(e) => setTailoredId(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-2 text-xs text-slate-100"
              >
                <option value="">Nenhum vinculado</option>
                {tailoredResumes.map((t) => (
                  <option key={t.id} value={t.id}>
                    #{t.id} {t.job_title} ({t.ats_score_after}%)
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label htmlFor="app-url" className="block text-xs font-medium text-slate-300">
              URL da Vaga (opcional)
            </label>
            <input
              id="app-url"
              type="url"
              value={jobUrl}
              onChange={(e) => setJobUrl(e.target.value)}
              placeholder="https://..."
              className="w-full rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-2 text-xs text-slate-100 placeholder-[#8896ab]"
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="app-notes" className="block text-xs font-medium text-slate-300">
              Anotações, contatos e próximos passos
            </label>
            <textarea
              id="app-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ex: Conversa com recrutador agendada para quinta às 15h..."
              className="w-full rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-2 text-xs text-slate-100 placeholder-[#8896ab]"
            />
          </div>

          <div className="flex items-center justify-between border-t border-slate-800 pt-4">
            {editingApp ? (
              <button
                type="button"
                onClick={() => {
                  void handleDeleteApp(editingApp.id);
                  setFormOpen(false);
                }}
                className="inline-flex items-center gap-1 rounded-lg border border-rose-500/35 px-3 py-2 text-xs font-medium text-rose-300 hover:bg-rose-500/15"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Excluir
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setFormOpen(false)}
                className="rounded-lg border border-slate-700 px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={savingForm}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
              >
                {savingForm && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Salvar
              </button>
            </div>
          </div>
        </form>
      </Modal>

      {/* Interview Prep Modal */}
      <Modal
        open={prepModalOpen}
        onClose={() => setPrepModalOpen(false)}
        title={
          prepTargetApp
            ? `Guia de Entrevista — ${prepTargetApp.role_title}`
            : 'Guia de Preparação de Entrevista'
        }
        description={prepTargetApp?.company_name}
        maxWidthClass="max-w-2xl"
      >
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <span className="text-xs text-slate-400">Idioma do roteiro:</span>
            <div className="flex items-center gap-2">
              <select
                value={prepLang}
                onChange={(e) => {
                  const next = e.target.value as 'auto' | 'pt-BR' | 'en';
                  setPrepLang(next);
                  if (prepTargetApp) {
                    void handleOpenInterviewPrep(prepTargetApp, next);
                  }
                }}
                className="rounded-md border border-slate-700 bg-[#0b0e14] px-2.5 py-1 text-xs text-slate-200"
              >
                <option value="auto">Automático</option>
                <option value="pt-BR">Português (pt-BR)</option>
                <option value="en">Inglês (en)</option>
              </select>
            </div>
          </div>

          {prepLoading ? (
            <div className="space-y-3 py-4">
              <SkeletonBlock className="h-20" />
              <SkeletonBlock className="h-20" />
              <SkeletonBlock className="h-20" />
            </div>
          ) : prepData ? (
            <div className="space-y-4 text-xs">
              <div className="space-y-2">
                <h3 className="font-semibold uppercase tracking-wider text-slate-300">
                  Perguntas Prováveis
                </h3>
                {(prepData.interview_prep.likely_questions || []).map((q, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3 space-y-1"
                  >
                    <p className="font-semibold text-slate-100">{q.question}</p>
                    {q.focus && (
                      <p className="text-slate-400">
                        <span className="text-sky-400">Foco:</span> {q.focus}
                      </p>
                    )}
                    {q.sample_angle && (
                      <p className="text-slate-300">
                        <span className="text-emerald-400">Estratégia STAR:</span>{' '}
                        {q.sample_angle}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              {(prepData.interview_prep.gap_mitigation_tips || []).length > 0 && (
                <div className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3.5">
                  <h4 className="font-semibold text-amber-300">Como Mitigar Gaps</h4>
                  <ul className="mt-2 space-y-1 text-slate-300">
                    {prepData.interview_prep.gap_mitigation_tips?.map((tip, i) => (
                      <li key={i}>• {tip}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {(prepData.interview_prep.key_talking_points || []).length > 0 && (
                  <div className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3.5">
                    <h4 className="font-semibold text-emerald-300">Pontos Fortes</h4>
                    <ul className="mt-2 space-y-1 text-slate-300">
                      {prepData.interview_prep.key_talking_points?.map((pt, i) => (
                        <li key={i}>• {pt}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {(prepData.interview_prep.questions_to_ask_interviewer || []).length > 0 && (
                  <div className="rounded-lg border border-slate-800 bg-[#0b0e14] p-3.5">
                    <h4 className="font-semibold text-sky-300">Perguntas para Fazer ao Time</h4>
                    <ul className="mt-2 space-y-1 text-slate-300">
                      {prepData.interview_prep.questions_to_ask_interviewer?.map((pq, i) => (
                        <li key={i}>• {pq}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </Modal>
    </div>
  );
};
