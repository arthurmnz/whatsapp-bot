import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  FileUp,
  History,
  Loader2,
  Sparkles,
  Star,
  Trash2,
  Upload,
} from 'lucide-react';
import { ApiError, api } from '../lib/api';
import { formatRelativeDate } from '../lib/format';
import type {
  BaseResume,
  JobMatchItem,
  TailoredResume,
  TailorPrefillContext,
} from '../types/api';
import { TailoredResultPanel } from '../components/TailoredResultPanel';
import { ScoreBadge, SkeletonBlock } from '../components/ui/ScoreBadge';
import { useToast } from '../components/ui/Toast';

interface CvStudioViewProps {
  prefillContext: TailorPrefillContext | null;
  onClearPrefill: () => void;
  onNavigateApplications: () => void;
}

export const CvStudioView: React.FC<CvStudioViewProps> = ({
  prefillContext,
  onClearPrefill,
  onNavigateApplications,
}) => {
  const { pushToast } = useToast();

  // Base resumes + tailored history + saved jobs
  const [resumes, setResumes] = useState<BaseResume[]>([]);
  const [tailoredList, setTailoredList] = useState<TailoredResume[]>([]);
  const [savedJobs, setSavedJobs] = useState<JobMatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Upload state
  const [uploadTab, setUploadTab] = useState<'file' | 'paste'>('file');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadRawText, setUploadRawText] = useState('');
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadLang, setUploadLang] = useState('');
  const [uploadIsDefault, setUploadIsDefault] = useState(true);
  const [uploadSyncProfile, setUploadSyncProfile] = useState(true);
  const [uploading, setUploading] = useState(false);

  // Tailor form state
  const [selectedBaseId, setSelectedBaseId] = useState<string>('');
  const [customResumeText, setCustomResumeText] = useState('');
  const [useCustomResumeText, setUseCustomResumeText] = useState(false);

  const [selectedJobId, setSelectedJobId] = useState<string>('');
  const [jobUrl, setJobUrl] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [targetLanguage, setTargetLanguage] = useState<'auto' | 'pt-BR' | 'en'>('auto');
  const [tailoring, setTailoring] = useState(false);

  // Active result
  const [activeTailored, setActiveTailored] = useState<TailoredResume | null>(null);
  const [previewBaseResume, setPreviewBaseResume] = useState<BaseResume | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [resList, tailoredRes, jobsRes] = await Promise.all([
        api.resumes.list(),
        api.resumes.listTailored(),
        api.jobs.list({ limit: 50 }),
      ]);
      setResumes(resList.items);
      setTailoredList(tailoredRes.items);
      setSavedJobs(jobsRes.items);

      const def = resList.items.find((r) => r.is_default) || resList.items[0];
      if (def) {
        setSelectedBaseId((prev) => prev || String(def.id));
      }
      if (tailoredRes.items.length > 0) {
        setActiveTailored((prev) => prev || tailoredRes.items[0]);
      }
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Erro ao carregar CV Studio.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  // Apply prefill context from Radar / Chat
  useEffect(() => {
    if (!prefillContext) return;

    if (prefillContext.tailoredResumeId) {
      void (async () => {
        try {
          const item = await api.resumes.getTailored(prefillContext.tailoredResumeId!);
          setActiveTailored(item);
        } catch {
          // Ignora se não encontrado
        } finally {
          onClearPrefill();
        }
      })();
      return;
    }

    if (prefillContext.jobId) {
      setSelectedJobId(String(prefillContext.jobId));
    } else {
      setSelectedJobId('');
    }
    setJobTitle(prefillContext.jobTitle || '');
    setCompanyName(prefillContext.companyName || '');
    setJobDescription(prefillContext.jobDescription || '');
    setJobUrl(prefillContext.jobUrl || '');
    onClearPrefill();
  }, [prefillContext, onClearPrefill]);

  const handleSelectSavedJob = (jobIdStr: string) => {
    setSelectedJobId(jobIdStr);
    if (!jobIdStr) return;
    const match = savedJobs.find((m) => String(m.job_id) === jobIdStr);
    if (match?.job) {
      setJobTitle(match.job.title || '');
      setCompanyName(match.job.company_name || '');
      setJobDescription(match.job.description_raw || '');
      setJobUrl(match.job.source_url || '');
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (uploadTab === 'file' && !uploadFile) {
      pushToast('Selecione um arquivo PDF, DOCX, MD ou TXT.', 'error');
      return;
    }
    if (uploadTab === 'paste' && !uploadRawText.trim()) {
      pushToast('Cole o texto do currículo para salvar.', 'error');
      return;
    }

    const fd = new FormData();
    if (uploadTab === 'file' && uploadFile) {
      fd.append('file', uploadFile);
    } else {
      fd.append('raw_text', uploadRawText.trim());
    }
    if (uploadTitle.trim()) fd.append('title', uploadTitle.trim());
    if (uploadLang) fd.append('language', uploadLang);
    fd.append('is_default', String(uploadIsDefault));
    fd.append('sync_profile', String(uploadSyncProfile));

    setUploading(true);
    try {
      const created = await api.resumes.upload(fd);
      setResumes((prev) => {
        const updated = uploadIsDefault
          ? prev.map((r) => ({ ...r, is_default: false }))
          : prev;
        return [created, ...updated];
      });
      setSelectedBaseId(String(created.id));
      setUploadFile(null);
      setUploadRawText('');
      setUploadTitle('');
      pushToast(
        `Currículo "${created.title}" salvo` +
          (uploadSyncProfile ? ' e skills sincronizadas no perfil!' : '!'),
        'success',
      );
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao enviar currículo.', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleSetDefault = async (resumeId: number) => {
    try {
      await api.resumes.setDefault(resumeId);
      setResumes((prev) => prev.map((r) => ({ ...r, is_default: r.id === resumeId })));
      setSelectedBaseId(String(resumeId));
      pushToast('Currículo padrão atualizado.', 'success');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao definir padrão.', 'error');
    }
  };

  const handleDeleteBaseResume = async (resumeId: number, title: string) => {
    try {
      await api.resumes.delete(resumeId);
      setResumes((prev) => prev.filter((r) => r.id !== resumeId));
      if (selectedBaseId === String(resumeId)) setSelectedBaseId('');
      if (previewBaseResume?.id === resumeId) setPreviewBaseResume(null);
      pushToast(`Currículo "${title}" removido.`, 'info');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao excluir currículo.', 'error');
    }
  };

  const handleTailorSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedJobId && !jobUrl.trim() && !jobDescription.trim()) {
      pushToast('Selecione uma vaga, informe a URL ou cole a descrição da vaga.', 'error');
      return;
    }

    setTailoring(true);
    try {
      const created = await api.resumes.tailor({
        base_resume_id:
          !useCustomResumeText && selectedBaseId ? Number(selectedBaseId) : null,
        resume_text: useCustomResumeText && customResumeText.trim() ? customResumeText.trim() : null,
        job_id: selectedJobId ? Number(selectedJobId) : null,
        job_url: jobUrl.trim() || null,
        job_description: jobDescription.trim() || null,
        job_title: jobTitle.trim() || null,
        company_name: companyName.trim() || null,
        target_language: targetLanguage,
      });
      setTailoredList((prev) => [created, ...prev.filter((t) => t.id !== created.id)]);
      setActiveTailored(created);
      pushToast(
        `Currículo avaliado! Score ATS: ${created.ats_score_before} → ${created.ats_score_after}/100`,
        'success',
      );
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao avaliar/otimizar currículo.', 'error');
    } finally {
      setTailoring(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl space-y-5 p-6">
        <SkeletonBlock className="h-9 w-72" />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <SkeletonBlock className="h-72" />
          <SkeletonBlock className="h-72" />
        </div>
        <SkeletonBlock className="h-96" />
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
            onClick={() => void loadAll()}
            className="rounded-lg border border-rose-400/40 px-3 py-1.5 text-xs font-medium hover:bg-rose-500/20"
          >
            Recarregar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">
            CV Studio — Avaliador ATS &amp; Otimizador
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Envie seu currículo base, compare contra a vaga, edite o texto corrigido e baixe em
            PDF, DOCX ou Markdown (pt-BR e en).
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: Base Resumes Manager & Upload */}
        <section className="space-y-5 lg:col-span-5">
          <form
            onSubmit={handleUploadSubmit}
            className="space-y-4 rounded-xl border border-slate-800/90 bg-[#111621] p-5"
          >
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <FileUp className="h-4 w-4 text-sky-400" />
                Enviar Currículo Base
              </h2>
              <div className="flex rounded-md border border-slate-800 bg-[#0b0e14] p-0.5 text-[11px]">
                <button
                  type="button"
                  onClick={() => setUploadTab('file')}
                  className={`rounded px-2 py-1 font-medium ${
                    uploadTab === 'file' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
                  }`}
                >
                  Arquivo
                </button>
                <button
                  type="button"
                  onClick={() => setUploadTab('paste')}
                  className={`rounded px-2 py-1 font-medium ${
                    uploadTab === 'paste' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
                  }`}
                >
                  Colar Texto
                </button>
              </div>
            </div>

            {uploadTab === 'file' ? (
              <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-slate-700 bg-[#0b0e14] px-4 py-5 text-center transition-colors hover:border-sky-500/60">
                <Upload className="h-5 w-5 text-sky-400" />
                <span className="mt-2 text-xs font-medium text-slate-200">
                  {uploadFile ? uploadFile.name : 'Escolher arquivo (.pdf, .docx, .md, .txt)'}
                </span>
                <span className="mt-0.5 text-[11px] text-[#8896ab]">Tamanho máximo: 5 MB</span>
                <input
                  type="file"
                  accept=".pdf,.docx,.md,.markdown,.txt"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="sr-only"
                />
              </label>
            ) : (
              <textarea
                rows={4}
                value={uploadRawText}
                onChange={(e) => setUploadRawText(e.target.value)}
                placeholder="Cole aqui o texto completo ou Markdown do seu currículo..."
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-xs text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            )}

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              <input
                type="text"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                placeholder="Título (ex: CV Backend 2026)"
                className="rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
              <select
                aria-label="Idioma do currículo"
                value={uploadLang}
                onChange={(e) => setUploadLang(e.target.value)}
                className="rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-200 focus:border-sky-500/70 focus:outline-none"
              >
                <option value="">Idioma: Detectar</option>
                <option value="pt-BR">pt-BR</option>
                <option value="en">en</option>
              </select>
            </div>

            <div className="space-y-1.5 text-xs text-slate-300">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={uploadSyncProfile}
                  onChange={(e) => setUploadSyncProfile(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-900 text-emerald-500"
                />
                <span>Extrair skills automaticamente para meu perfil</span>
              </label>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={uploadIsDefault}
                  onChange={(e) => setUploadIsDefault(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-900 text-emerald-500"
                />
                <span>Definir como currículo padrão</span>
              </label>
            </div>

            <button
              type="submit"
              disabled={uploading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-sky-500/40 bg-sky-500/15 px-3.5 py-2 text-xs font-semibold text-sky-200 hover:bg-sky-500/25 disabled:opacity-60"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Processando currículo...
                </>
              ) : (
                <>
                  <FileUp className="h-3.5 w-3.5" />
                  Importar Currículo Base
                </>
              )}
            </button>
          </form>

          {/* Base resumes list */}
          <div className="rounded-xl border border-slate-800/90 bg-[#111621] p-4 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Currículos Base ({resumes.length})
            </h3>
            {resumes.length === 0 ? (
              <p className="text-xs text-[#8896ab]">
                Nenhum currículo enviado ainda. Se preferir, o motor também pode montar um rascunho
                a partir das skills do seu perfil.
              </p>
            ) : (
              <div className="space-y-2">
                {resumes.map((r) => (
                  <div
                    key={r.id}
                    className={`rounded-lg border p-3 text-xs transition-colors ${
                      r.is_default
                        ? 'border-emerald-500/35 bg-emerald-500/8'
                        : 'border-slate-800 bg-[#0c1018]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          setPreviewBaseResume((prev) => (prev?.id === r.id ? null : r))
                        }
                        className="min-w-0 flex-1 text-left"
                      >
                        <div className="flex items-center gap-1.5 font-semibold text-slate-100">
                          <FileText className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                          <span className="truncate">{r.title}</span>
                        </div>
                        <div className="mt-0.5 font-mono text-[10px] text-[#8896ab]">
                          {r.source_format.toUpperCase()} · {r.language} ·{' '}
                          {formatRelativeDate(r.updated_at)}
                        </div>
                      </button>

                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => void handleSetDefault(r.id)}
                          title={r.is_default ? 'Padrão' : 'Definir como padrão'}
                          className={`rounded p-1 ${
                            r.is_default
                              ? 'text-amber-400'
                              : 'text-slate-500 hover:bg-slate-800 hover:text-slate-200'
                          }`}
                        >
                          <Star
                            className="h-3.5 w-3.5"
                            fill={r.is_default ? 'currentColor' : 'none'}
                          />
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeleteBaseResume(r.id, r.title)}
                          className="rounded p-1 text-slate-500 hover:bg-rose-500/15 hover:text-rose-300"
                          aria-label={`Excluir ${r.title}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {previewBaseResume && (
              <div className="rounded-lg border border-slate-700 bg-[#0b0e14] p-3">
                <div className="mb-1.5 flex items-center justify-between text-[11px] font-semibold text-slate-300">
                  <span>Texto extraído: {previewBaseResume.title}</span>
                  <button
                    type="button"
                    onClick={() => setPreviewBaseResume(null)}
                    className="text-slate-400 hover:text-slate-200"
                  >
                    Fechar
                  </button>
                </div>
                <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap font-mono text-[11px] text-slate-300">
                  {previewBaseResume.raw_text}
                </pre>
              </div>
            )}
          </div>
        </section>

        {/* Right: Tailor Engine Form + History */}
        <section className="space-y-5 lg:col-span-7">
          <form
            onSubmit={handleTailorSubmit}
            className="space-y-4 rounded-xl border border-slate-800/90 bg-[#111621] p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <Sparkles className="h-4 w-4 text-emerald-400" />
                Avaliar &amp; Corrigir Currículo para Vaga
              </h2>
              <span className="rounded border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">
                Anti-alucinação ativo
              </span>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label htmlFor="tailor-base" className="text-xs font-medium text-slate-300">
                    Currículo Base
                  </label>
                  <button
                    type="button"
                    onClick={() => setUseCustomResumeText((v) => !v)}
                    className="text-[11px] text-sky-400 hover:underline"
                  >
                    {useCustomResumeText ? 'Escolher salvo' : 'Colar texto avulso'}
                  </button>
                </div>
                {!useCustomResumeText ? (
                  <select
                    id="tailor-base"
                    value={selectedBaseId}
                    onChange={(e) => setSelectedBaseId(e.target.value)}
                    className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-xs text-slate-100 focus:border-emerald-500/70 focus:outline-none"
                  >
                    <option value="">
                      {resumes.length
                        ? 'Usar currículo padrão / perfil'
                        : 'Montar com dados do Perfil'}
                    </option>
                    {resumes.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.title} ({r.language}){r.is_default ? ' ★' : ''}
                      </option>
                    ))}
                  </select>
                ) : (
                  <textarea
                    rows={3}
                    value={customResumeText}
                    onChange={(e) => setCustomResumeText(e.target.value)}
                    placeholder="Cole o texto do currículo a avaliar..."
                    className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 placeholder-[#8896ab]"
                  />
                )}
              </div>

              <div className="space-y-1">
                <label htmlFor="tailor-lang" className="block text-xs font-medium text-slate-300">
                  Idioma de Saída (CV, Carta &amp; Prep)
                </label>
                <select
                  id="tailor-lang"
                  value={targetLanguage}
                  onChange={(e) =>
                    setTargetLanguage(e.target.value as 'auto' | 'pt-BR' | 'en')
                  }
                  className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-xs text-slate-100 focus:border-emerald-500/70 focus:outline-none"
                >
                  <option value="auto">Automático (detectar idioma da vaga)</option>
                  <option value="pt-BR">Português (pt-BR)</option>
                  <option value="en">Inglês (en)</option>
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="tailor-saved-job" className="block text-xs font-medium text-slate-300">
                Selecionar Vaga do Radar (opcional)
              </label>
              <select
                id="tailor-saved-job"
                value={selectedJobId}
                onChange={(e) => handleSelectSavedJob(e.target.value)}
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-xs text-slate-100 focus:border-sky-500/70 focus:outline-none"
              >
                <option value="">— Preencher URL ou descrição manualmente abaixo —</option>
                {savedJobs.map(
                  (m) =>
                    m.job && (
                      <option key={m.match_id} value={m.job.id}>
                        [{m.match_score}%] {m.job.title}
                        {m.job.company_name ? ` @ ${m.job.company_name}` : ''}
                      </option>
                    ),
                )}
              </select>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1">
                <label htmlFor="tailor-title" className="block text-xs font-medium text-slate-300">
                  Cargo da Vaga
                </label>
                <input
                  id="tailor-title"
                  type="text"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  placeholder="Ex: Backend Engineer"
                  className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 placeholder-[#8896ab]"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="tailor-comp" className="block text-xs font-medium text-slate-300">
                  Empresa
                </label>
                <input
                  id="tailor-comp"
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Ex: Stripe"
                  className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 placeholder-[#8896ab]"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="tailor-url" className="block text-xs font-medium text-slate-300">
                  URL da Vaga (opcional)
                </label>
                <input
                  id="tailor-url"
                  type="url"
                  value={jobUrl}
                  onChange={(e) => setJobUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 placeholder-[#8896ab]"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="tailor-desc" className="block text-xs font-medium text-slate-300">
                Descrição / Requisitos da Vaga
              </label>
              <textarea
                id="tailor-desc"
                rows={5}
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Cole aqui os requisitos, responsabilidades e stack da vaga (ou informe a URL acima)..."
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-xs leading-relaxed text-slate-100 placeholder-[#8896ab] focus:border-emerald-500/70 focus:outline-none"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={tailoring}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400 disabled:opacity-60"
              >
                {tailoring ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Avaliando ATS &amp; Gerando PDF/DOCX...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Avaliar &amp; Corrigir Currículo
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Previously tailored versions quick switcher */}
          {tailoredList.length > 0 && (
            <div className="rounded-xl border border-slate-800/90 bg-[#111621] p-4 space-y-2.5">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
                <History className="h-3.5 w-3.5 text-sky-400" />
                Versões Otimizadas Recentes ({tailoredList.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {tailoredList.slice(0, 8).map((item) => {
                  const active = activeTailored?.id === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setActiveTailored(item)}
                      className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
                        active
                          ? 'border-emerald-500/50 bg-emerald-500/12 text-slate-50'
                          : 'border-slate-800 bg-[#0c1018] text-slate-300 hover:border-slate-700'
                      }`}
                    >
                      <span className="max-w-[170px] truncate font-medium">
                        {item.job_title}
                        {item.company_name ? ` @ ${item.company_name}` : ''}
                      </span>
                      <ScoreBadge score={item.ats_score_after} suffix="" />
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Tailored Result Full Panel */}
      {activeTailored ? (
        <TailoredResultPanel
          tailored={activeTailored}
          onUpdated={(updated) => {
            setActiveTailored(updated);
            setTailoredList((prev) =>
              prev.map((item) => (item.id === updated.id ? updated : item)),
            );
          }}
          onApplicationCreated={onNavigateApplications}
        />
      ) : (
        <div className="rounded-xl border border-slate-800 bg-[#111621] p-8 text-center">
          <CheckCircle2 className="mx-auto h-8 w-8 text-slate-600" />
          <h3 className="mt-2 text-sm font-semibold text-slate-200">
            Nenhum currículo otimizado selecionado ainda
          </h3>
          <p className="mx-auto mt-1 max-w-md text-xs text-[#8896ab]">
            Selecione uma vaga ou cole a descrição acima e clique em{' '}
            <strong>Avaliar &amp; Corrigir Currículo</strong> para ver a comparação ATS antes vs
            depois e baixar em PDF e DOCX.
          </p>
        </div>
      )}
    </div>
  );
};
