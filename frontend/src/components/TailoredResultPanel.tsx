import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Copy,
  Download,
  Eye,
  FileCode2,
  KanbanSquare,
  Loader2,
  Mail,
  RefreshCw,
  Sparkles,
  Target,
} from 'lucide-react';
import { ApiError, api } from '../lib/api';
import { formatRelativeDate } from '../lib/format';
import type { AtsBreakdown, TailoredResume } from '../types/api';
import { useToast } from './ui/Toast';

type ResultSubTab = 'report' | 'editor' | 'cover' | 'interview';

interface TailoredResultPanelProps {
  tailored: TailoredResume;
  onUpdated: (updated: TailoredResume) => void;
  onApplicationCreated?: () => void;
}

const BREAKDOWN_ROWS: Array<{
  key: keyof AtsBreakdown;
  label: string;
  max: number;
}> = [
  { key: 'keywords_score', label: 'Keywords ATS', max: 45 },
  { key: 'experience_score', label: 'Experiência', max: 25 },
  { key: 'impact_score', label: 'Impacto / Métricas', max: 15 },
  { key: 'formatting_score', label: 'Formatação', max: 15 },
];

const renderInlineBold = (text: string, prefix: string): React.ReactNode => {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) =>
    part.startsWith('**') && part.endsWith('**') ? (
      <strong key={`${prefix}-${idx}`} className="font-semibold text-slate-900">
        {part.slice(2, -2)}
      </strong>
    ) : (
      <React.Fragment key={`${prefix}-${idx}`}>{part}</React.Fragment>
    ),
  );
};

const renderMarkdownPreview = (md: string): React.ReactNode => {
  const lines = md.split('\n');
  return lines.map((line, idx) => {
    const trimmed = line.trim();
    if (trimmed.startsWith('# ')) {
      return (
        <h1 key={idx} className="border-b border-slate-300 pb-1 text-lg font-bold text-slate-900">
          {trimmed.slice(2)}
        </h1>
      );
    }
    if (trimmed.startsWith('## ')) {
      return (
        <h2
          key={idx}
          className="mt-4 border-b border-slate-200 pb-0.5 text-xs font-bold uppercase tracking-wider text-slate-700"
        >
          {trimmed.slice(3)}
        </h2>
      );
    }
    if (trimmed.startsWith('### ')) {
      return (
        <h3 key={idx} className="mt-2.5 text-sm font-semibold text-slate-800">
          {trimmed.slice(4)}
        </h3>
      );
    }
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      return (
        <li key={idx} className="ml-4 list-disc text-xs leading-relaxed text-slate-700">
          {renderInlineBold(trimmed.slice(2), `li-${idx}`)}
        </li>
      );
    }
    if (!trimmed) {
      return <div key={idx} className="h-2" />;
    }
    return (
      <p key={idx} className="text-xs leading-relaxed text-slate-700">
        {renderInlineBold(trimmed, `p-${idx}`)}
      </p>
    );
  });
};

export const TailoredResultPanel: React.FC<TailoredResultPanelProps> = ({
  tailored,
  onUpdated,
  onApplicationCreated,
}) => {
  const { pushToast } = useToast();
  const [subTab, setSubTab] = useState<ResultSubTab>('report');
  const [markdownDraft, setMarkdownDraft] = useState(tailored.tailored_markdown || '');
  const [coverDraft, setCoverDraft] = useState(tailored.cover_letter || '');
  const [langDraft, setLangDraft] = useState(tailored.target_language || 'pt-BR');
  const [editorMode, setEditorMode] = useState<'split' | 'code' | 'preview'>('split');

  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState<'pdf' | 'docx' | 'md' | null>(null);
  const [copiedCover, setCopiedCover] = useState(false);
  const [sendingKanban, setSendingKanban] = useState(false);

  useEffect(() => {
    setMarkdownDraft(tailored.tailored_markdown || '');
    setCoverDraft(tailored.cover_letter || '');
    setLangDraft(tailored.target_language || 'pt-BR');
  }, [tailored]);

  const handleSaveAndRegenerate = async () => {
    setSaving(true);
    try {
      const updated = await api.resumes.updateTailored(tailored.id, {
        tailored_markdown: markdownDraft,
        target_language: langDraft,
        cover_letter: coverDraft,
      });
      onUpdated(updated);
      pushToast('Alterações salvas e arquivos PDF/DOCX regerados!', 'success');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao regerar arquivos.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async (format: 'pdf' | 'docx' | 'md') => {
    setDownloading(format);
    try {
      await api.resumes.downloadTailored(tailored.id, format);
    } catch (err) {
      pushToast(
        err instanceof ApiError ? err.detail : `Erro ao baixar ${format.toUpperCase()}.`,
        'error',
      );
    } finally {
      setDownloading(null);
    }
  };

  const handleCopyCover = async () => {
    try {
      await navigator.clipboard.writeText(coverDraft);
      setCopiedCover(true);
      pushToast('Carta de apresentação copiada!', 'success');
      window.setTimeout(() => setCopiedCover(false), 2000);
    } catch {
      pushToast('Não foi possível acessar a área de transferência.', 'error');
    }
  };

  const handleSendToKanban = async () => {
    setSendingKanban(true);
    try {
      await api.applications.create({
        company_name: tailored.company_name || 'Empresa',
        role_title: tailored.job_title || 'Vaga Otimizada',
        job_id: tailored.job_id,
        tailored_resume_id: tailored.id,
        stage: 'cv_ready',
      });
      pushToast('Adicionado ao Kanban no estágio "CV Otimizado"!', 'success');
      onApplicationCreated?.();
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao criar candidatura.', 'error');
    } finally {
      setSendingKanban(false);
    }
  };

  const delta = (tailored.ats_score_after ?? 0) - (tailored.ats_score_before ?? 0);
  const report = tailored.evaluation_report || {};
  const bBefore = report.breakdown_before;
  const bAfter = report.breakdown_after;
  const matchedKw = report.matched_keywords || [];
  const missingKw = report.missing_keywords || [];
  const missingInProfile = report.missing_but_in_profile || [];
  const realGaps = report.real_gaps || [];
  const critiquePoints = report.critique_points || [];
  const suggestions = report.improvement_suggestions || [];
  const prep = tailored.interview_prep || {};

  return (
    <div className="space-y-5 rounded-xl border border-slate-800/90 bg-[#111621] p-5">
      {/* Header & Download actions */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-50">
              {tailored.job_title || 'Currículo Otimizado'}
            </h2>
            {tailored.company_name && (
              <span className="text-sm text-slate-400">@ {tailored.company_name}</span>
            )}
            <span className="rounded border border-sky-500/35 bg-sky-500/12 px-2 py-0.5 font-mono text-[11px] text-sky-300">
              {tailored.target_language}
            </span>
          </div>
          <p className="mt-1 text-xs text-[#8896ab]">
            Atualizado {formatRelativeDate(tailored.updated_at || tailored.created_at)} · ID #
            {tailored.id}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={downloading !== null}
            onClick={() => void handleDownload('pdf')}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
          >
            {downloading === 'pdf' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            PDF
          </button>
          <button
            type="button"
            disabled={downloading !== null}
            onClick={() => void handleDownload('docx')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-60"
          >
            {downloading === 'docx' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            DOCX
          </button>
          <button
            type="button"
            disabled={downloading !== null}
            onClick={() => void handleDownload('md')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-60"
          >
            {downloading === 'md' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            MD
          </button>
          <button
            type="button"
            disabled={sendingKanban}
            onClick={() => void handleSendToKanban()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/12 px-3 py-2 text-xs font-medium text-sky-200 hover:bg-sky-500/20 disabled:opacity-60"
          >
            {sendingKanban ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <KanbanSquare className="h-3.5 w-3.5" />
            )}
            Enviar p/ Kanban
          </button>
        </div>
      </div>

      {/* ATS Score Before -> After & Breakdown */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
        <div className="flex flex-col justify-between rounded-xl border border-slate-800 bg-[#0c1018] p-4">
          <div className="text-xs font-medium text-slate-400">Evolução de Score ATS</div>
          <div className="my-3 flex items-baseline gap-2.5 font-mono tabular-nums">
            <span className="text-2xl font-semibold text-slate-400">
              {tailored.ats_score_before}
            </span>
            <ArrowRight className="h-5 w-5 text-emerald-400" />
            <span className="text-4xl font-bold text-emerald-400">
              {tailored.ats_score_after}
            </span>
            <span className="text-xs text-slate-400">/100</span>
          </div>
          <div className="text-xs">
            {delta > 0 ? (
              <span className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/12 px-2 py-0.5 font-mono font-semibold text-emerald-300">
                +{delta} pts após otimização
              </span>
            ) : (
              <span className="text-[#8896ab]">Currículo já estava bem alinhado</span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 rounded-xl border border-slate-800 bg-[#0c1018] p-4 sm:grid-cols-2">
          {BREAKDOWN_ROWS.map((row) => {
            const beforeVal = bBefore ? bBefore[row.key] : 0;
            const afterVal = bAfter ? bAfter[row.key] : 0;
            const beforePct = Math.min(100, Math.round((beforeVal / row.max) * 100));
            const afterPct = Math.min(100, Math.round((afterVal / row.max) * 100));

            return (
              <div key={row.key} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-200">{row.label}</span>
                  <span className="font-mono tabular-nums text-slate-300">
                    <span className="text-slate-500">{beforeVal}</span> →{' '}
                    <span className="font-semibold text-emerald-300">
                      {afterVal}/{row.max}
                    </span>
                  </span>
                </div>
                <div className="relative h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-slate-600/70"
                    style={{ width: `${beforePct}%` }}
                  />
                  <div
                    className="relative h-full rounded-full bg-emerald-500/85 transition-all"
                    style={{ width: `${afterPct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Sub-navigation tabs */}
      <div
        role="tablist"
        aria-label="Detalhes do currículo otimizado"
        className="flex flex-wrap gap-1.5 border-b border-slate-800 pb-3"
      >
        <button
          type="button"
          role="tab"
          aria-selected={subTab === 'report'}
          onClick={() => setSubTab('report')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            subTab === 'report'
              ? 'bg-slate-800 text-slate-50'
              : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
          }`}
        >
          <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
          Avaliação &amp; Correções
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={subTab === 'editor'}
          onClick={() => setSubTab('editor')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            subTab === 'editor'
              ? 'bg-slate-800 text-slate-50'
              : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
          }`}
        >
          <FileCode2 className="h-3.5 w-3.5 text-sky-400" />
          Editor &amp; Preview do CV
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={subTab === 'cover'}
          onClick={() => setSubTab('cover')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            subTab === 'cover'
              ? 'bg-slate-800 text-slate-50'
              : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
          }`}
        >
          <Mail className="h-3.5 w-3.5 text-amber-400" />
          Carta de Apresentação
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={subTab === 'interview'}
          onClick={() => setSubTab('interview')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            subTab === 'interview'
              ? 'bg-slate-800 text-slate-50'
              : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
          }`}
        >
          <Target className="h-3.5 w-3.5 text-emerald-400" />
          Preparação para Entrevista
        </button>
      </div>

      {/* 1. Evaluation & Changes */}
      {subTab === 'report' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-[#0c1018] p-4">
              <h3 className="text-xs font-semibold text-emerald-400">
                Keywords Encontradas ({matchedKw.length})
              </h3>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {matchedKw.length ? (
                  matchedKw.map((kw) => (
                    <span
                      key={kw}
                      className="rounded border border-emerald-500/30 bg-emerald-500/12 px-2 py-0.5 text-[11px] font-medium text-emerald-200"
                    >
                      {kw}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-[#8896ab]">Nenhuma keyword direta detectada.</span>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-slate-800 bg-[#0c1018] p-4">
              <h3 className="text-xs font-semibold text-amber-400">
                Gaps Reais &amp; Keywords Ausentes ({realGaps.length || missingKw.length})
              </h3>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {(realGaps.length ? realGaps : missingKw).length ? (
                  (realGaps.length ? realGaps : missingKw).map((kw) => (
                    <span
                      key={kw}
                      className="rounded border border-amber-500/30 bg-amber-500/12 px-2 py-0.5 text-[11px] font-medium text-amber-200"
                    >
                      {kw}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-emerald-300">
                    Nenhum gap técnico relevante identificado!
                  </span>
                )}
              </div>
              {missingInProfile.length > 0 && (
                <p className="mt-2.5 text-[11px] text-sky-300">
                  Resgatadas do seu perfil para o CV: {missingInProfile.join(', ')}
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2 rounded-lg border border-slate-800 bg-[#0c1018] p-4">
              <h3 className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                Avaliação &amp; Pontos Críticos
              </h3>
              {critiquePoints.length ? (
                <ul className="space-y-1.5 text-xs leading-relaxed text-slate-300">
                  {critiquePoints.map((pt, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400" />
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-[#8896ab]">Sem apontamentos críticos.</p>
              )}
            </div>

            <div className="space-y-2 rounded-lg border border-slate-800 bg-[#0c1018] p-4">
              <h3 className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                Sugestões de Melhoria
              </h3>
              {suggestions.length ? (
                <ul className="space-y-1.5 text-xs leading-relaxed text-slate-300">
                  {suggestions.map((sg, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
                      <span>{sg}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-[#8896ab]">Nenhuma sugestão extra.</p>
              )}
            </div>
          </div>

          {/* Changes Summary */}
          <div className="rounded-lg border border-slate-800 bg-[#0c1018] p-4">
            <h3 className="text-xs font-semibold text-slate-200">
              Resumo das Correções Aplicadas ({tailored.changes_summary.length})
            </h3>
            {tailored.changes_summary.length ? (
              <div className="mt-3 divide-y divide-slate-800/80">
                {tailored.changes_summary.map((chg, idx) => (
                  <div key={idx} className="flex flex-col gap-1 py-2.5 text-xs sm:flex-row sm:gap-3">
                    <span className="w-28 shrink-0 font-mono text-[11px] uppercase text-sky-400">
                      {chg.section}
                    </span>
                    <span className="flex-1 text-slate-200">{chg.reason}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-xs text-[#8896ab]">
                Estrutura preservada com ordenação ATS padrão.
              </p>
            )}
          </div>
        </div>
      )}

      {/* 2. Markdown Editor & Live Preview */}
      {subTab === 'editor' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-[#0b0e14] p-1 text-xs">
              <button
                type="button"
                onClick={() => setEditorMode('split')}
                className={`rounded-md px-2.5 py-1 font-medium ${
                  editorMode === 'split' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
                }`}
              >
                Lado a lado
              </button>
              <button
                type="button"
                onClick={() => setEditorMode('code')}
                className={`rounded-md px-2.5 py-1 font-medium ${
                  editorMode === 'code' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
                }`}
              >
                Editor Markdown
              </button>
              <button
                type="button"
                onClick={() => setEditorMode('preview')}
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 font-medium ${
                  editorMode === 'preview' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
                }`}
              >
                <Eye className="h-3.5 w-3.5" />
                Preview
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                aria-label="Idioma de saída"
                value={langDraft}
                onChange={(e) => setLangDraft(e.target.value)}
                className="rounded-lg border border-slate-700 bg-[#0b0e14] px-2.5 py-1.5 text-xs text-slate-200"
              >
                <option value="pt-BR">Português (pt-BR)</option>
                <option value="en">Inglês (en)</option>
              </select>

              <button
                type="button"
                disabled={saving}
                onClick={() => void handleSaveAndRegenerate()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3.5 py-1.5 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
              >
                {saving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" />
                )}
                Salvar e Regerar PDF/DOCX
              </button>
            </div>
          </div>

          <div
            className={`grid gap-4 ${
              editorMode === 'split' ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'
            }`}
          >
            {editorMode !== 'preview' && (
              <textarea
                rows={20}
                value={markdownDraft}
                onChange={(e) => setMarkdownDraft(e.target.value)}
                aria-label="Editor Markdown do currículo otimizado"
                className="w-full rounded-xl border border-slate-700/80 bg-[#0b0e14] p-4 font-mono text-xs leading-relaxed text-slate-100 focus:border-sky-500/70 focus:outline-none"
              />
            )}

            {editorMode !== 'code' && (
              <div className="max-h-[520px] overflow-y-auto rounded-xl border border-slate-300 bg-white p-6 text-slate-900 shadow-inner">
                {renderMarkdownPreview(markdownDraft)}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. Cover Letter */}
      {subTab === 'cover' && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-slate-400">
              Edite se necessário e copie ou salve junto ao pacote de documentos.
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void handleCopyCover()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-100 hover:bg-slate-700"
              >
                {copiedCover ? (
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                {copiedCover ? 'Copiada!' : 'Copiar Carta'}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => void handleSaveAndRegenerate()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
              >
                {saving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" />
                )}
                Salvar Carta
              </button>
            </div>
          </div>
          <textarea
            rows={12}
            value={coverDraft}
            onChange={(e) => setCoverDraft(e.target.value)}
            className="w-full rounded-xl border border-slate-700/80 bg-[#0b0e14] p-4 text-sm leading-relaxed text-slate-100 focus:border-sky-500/70 focus:outline-none"
          />
        </div>
      )}

      {/* 4. Interview Prep */}
      {subTab === 'interview' && (
        <div className="space-y-4">
          <div className="space-y-2.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Perguntas Prováveis
            </h3>
            {(prep.likely_questions || []).length ? (
              (prep.likely_questions || []).map((q, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-slate-800 bg-[#0c1018] p-3.5 text-xs"
                >
                  <p className="font-semibold text-slate-100">{q.question}</p>
                  {q.focus && (
                    <p className="mt-1 text-slate-400">
                      <span className="text-sky-400">Foco:</span> {q.focus}
                    </p>
                  )}
                  {q.sample_angle && (
                    <p className="mt-1 text-slate-300">
                      <span className="text-emerald-400">Abordagem STAR:</span> {q.sample_angle}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p className="text-xs text-[#8896ab]">Nenhuma pergunta gerada para este currículo.</p>
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-[#0c1018] p-4">
              <h4 className="text-xs font-semibold text-amber-300">Dicas para Mitigar Gaps</h4>
              <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-slate-300">
                {(prep.gap_mitigation_tips || []).map((tip, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400" />
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg border border-slate-800 bg-[#0c1018] p-4">
              <h4 className="text-xs font-semibold text-emerald-300">
                Pontos Fortes para Destacar
              </h4>
              <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-slate-300">
                {(prep.key_talking_points || []).map((pt, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
                    <span>{pt}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
