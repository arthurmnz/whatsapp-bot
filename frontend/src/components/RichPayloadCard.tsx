import React, { useState } from 'react';
import {
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  MonitorCheck,
  Sparkles,
  Target,
} from 'lucide-react';
import { api, ApiError } from '../lib/api';
import { getWorkModelLabel, sanitizeExternalUrl } from '../lib/format';
import type {
  InterviewPrep,
  JobMatchItem,
  TailoredResume,
  TailorPrefillContext,
} from '../types/api';
import { ScoreBadge } from './ui/ScoreBadge';
import { useToast } from './ui/Toast';

interface RichPayloadCardProps {
  payload: Record<string, unknown>;
  onOpenCvStudio: (prefill: TailorPrefillContext) => void;
  onNavigateTab: (tab: 'jobs' | 'cv' | 'profile' | 'applications' | 'system') => void;
}

export const RichPayloadCard: React.FC<RichPayloadCardProps> = ({
  payload,
  onOpenCvStudio,
  onNavigateTab,
}) => {
  const { pushToast } = useToast();
  const [downloadingFormat, setDownloadingFormat] = useState<'pdf' | 'docx' | null>(null);

  const kind = String(payload.type || '');

  const handleDownload = async (tailoredId: number, fmt: 'pdf' | 'docx') => {
    setDownloadingFormat(fmt);
    try {
      await api.resumes.downloadTailored(tailoredId, fmt);
    } catch (err) {
      pushToast(
        err instanceof ApiError ? err.detail : `Erro ao baixar ${fmt.toUpperCase()}.`,
        'error',
      );
    } finally {
      setDownloadingFormat(null);
    }
  };

  if (kind === 'tailored_resume' && payload.tailored && typeof payload.tailored === 'object') {
    const t = payload.tailored as TailoredResume;
    const delta = (t.ats_score_after ?? 0) - (t.ats_score_before ?? 0);
    return (
      <div className="mt-2.5 rounded-lg border border-emerald-500/30 bg-[#0d141d] p-3.5 text-xs">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-1.5 font-semibold text-slate-100">
              <FileText className="h-4 w-4 text-emerald-400" />
              <span>{t.job_title || 'Currículo Otimizado'}</span>
              {t.company_name && <span className="text-slate-400">@ {t.company_name}</span>}
            </div>
            <p className="mt-0.5 font-mono text-[11px] text-slate-400">
              Idioma: {t.target_language}
            </p>
          </div>

          <div className="flex items-center gap-1.5 rounded-md border border-slate-700/80 bg-[#121926] px-2.5 py-1 font-mono tabular-nums">
            <span className="text-slate-400">ATS</span>
            <span className="text-slate-200">{t.ats_score_before}</span>
            <ArrowRight className="h-3 w-3 text-emerald-400" />
            <span className="font-bold text-emerald-300">{t.ats_score_after}</span>
            {delta > 0 && <span className="text-emerald-400">(+{delta})</span>}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={downloadingFormat !== null}
            onClick={() => void handleDownload(t.id, 'pdf')}
            className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-2.5 py-1.5 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
          >
            {downloadingFormat === 'pdf' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            Baixar PDF
          </button>
          <button
            type="button"
            disabled={downloadingFormat !== null}
            onClick={() => void handleDownload(t.id, 'docx')}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-slate-100 hover:bg-slate-700 disabled:opacity-60"
          >
            {downloadingFormat === 'docx' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            Baixar DOCX
          </button>
          <button
            type="button"
            onClick={() => onOpenCvStudio({ tailoredResumeId: t.id })}
            className="inline-flex items-center gap-1.5 rounded-md border border-sky-500/35 bg-sky-500/10 px-2.5 py-1.5 text-xs font-medium text-sky-300 hover:bg-sky-500/20"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Editar no CV Studio
          </button>
        </div>
      </div>
    );
  }

  if (kind === 'jobs' && Array.isArray(payload.items)) {
    const items = payload.items as JobMatchItem[];
    if (!items.length) return null;
    return (
      <div className="mt-2.5 space-y-2">
        {items.slice(0, 5).map((item) => {
          const job = item.job;
          if (!job) return null;
          const safeUrl = sanitizeExternalUrl(job.source_url);
          return (
            <div
              key={item.match_id}
              className="rounded-lg border border-slate-700/70 bg-[#0d121b] p-3 text-xs"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-slate-100">{job.title}</div>
                  <div className="mt-0.5 text-[11px] text-slate-400">
                    {job.company_name || 'Empresa'} · {getWorkModelLabel(job.work_model)} ·{' '}
                    <span className="font-mono">{job.source}</span>
                  </div>
                </div>
                <ScoreBadge score={item.match_score} />
              </div>
              {item.matched_skills.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {item.matched_skills.slice(0, 5).map((sk) => (
                    <span
                      key={sk}
                      className="rounded border border-emerald-500/25 bg-emerald-500/10 px-1.5 py-0.5 text-[11px] text-emerald-300"
                    >
                      {sk}
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    onOpenCvStudio({
                      jobId: job.id,
                      jobTitle: job.title,
                      companyName: job.company_name || '',
                      jobDescription: job.description_raw,
                    })
                  }
                  className="inline-flex items-center gap-1 rounded bg-emerald-500/15 px-2 py-1 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/25"
                >
                  <Sparkles className="h-3 w-3" />
                  Otimizar CV
                </button>
                {safeUrl && (
                  <a
                    href={safeUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded border border-slate-700 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-800"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Abrir vaga
                  </a>
                )}
              </div>
            </div>
          );
        })}
        <button
          type="button"
          onClick={() => onNavigateTab('jobs')}
          className="inline-flex items-center gap-1 text-xs font-medium text-sky-400 hover:text-sky-300"
        >
          <BriefcaseBusiness className="h-3.5 w-3.5" />
          Ver todas no Radar de Vagas
        </button>
      </div>
    );
  }

  if (kind === 'job_match' && payload.item && typeof payload.item === 'object') {
    const item = payload.item as JobMatchItem;
    const job = item.job;
    if (!job) return null;
    return (
      <div className="mt-2.5 rounded-lg border border-sky-500/30 bg-[#0d121b] p-3 text-xs">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="font-semibold text-slate-100">{job.title}</div>
            <div className="text-[11px] text-slate-400">
              {job.company_name || 'Empresa'} · {getWorkModelLabel(job.work_model)}
            </div>
          </div>
          <ScoreBadge score={item.match_score} />
        </div>
        {item.ai_rationale && (
          <p className="mt-2 text-slate-300 leading-relaxed">{item.ai_rationale}</p>
        )}
        <div className="mt-2.5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() =>
              onOpenCvStudio({
                jobId: job.id,
                jobTitle: job.title,
                companyName: job.company_name || '',
                jobDescription: job.description_raw,
              })
            }
            className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-2.5 py-1 text-[11px] font-semibold text-slate-950 hover:bg-emerald-400"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Otimizar CV para esta vaga
          </button>
          <button
            type="button"
            onClick={() => onNavigateTab('jobs')}
            className="rounded-md border border-slate-700 px-2.5 py-1 text-[11px] text-slate-300 hover:bg-slate-800"
          >
            Abrir no Radar
          </button>
        </div>
      </div>
    );
  }

  if (kind === 'interview_prep' && payload.prep && typeof payload.prep === 'object') {
    const prep = payload.prep as InterviewPrep;
    return (
      <div className="mt-2.5 rounded-lg border border-amber-500/30 bg-[#0d121b] p-3 text-xs space-y-2">
        <div className="flex items-center gap-1.5 font-semibold text-amber-300">
          <Target className="h-3.5 w-3.5" />
          Roteiro de Entrevista
        </div>
        {(prep.likely_questions || []).slice(0, 3).map((q, idx) => (
          <div key={idx} className="rounded border border-slate-800 bg-[#121824] p-2">
            <p className="font-medium text-slate-100">{q.question}</p>
            {q.focus && <p className="mt-0.5 text-[11px] text-slate-400">Foco: {q.focus}</p>}
          </div>
        ))}
      </div>
    );
  }

  if (kind === 'interview_eval' && payload.evaluation && typeof payload.evaluation === 'object') {
    const ev = payload.evaluation as {
      score?: number;
      strengths?: string[];
      improvements?: string[];
      upgraded_example?: string;
    };
    return (
      <div className="mt-2.5 rounded-lg border border-sky-500/30 bg-[#0d121b] p-3 text-xs space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-sky-300">Avaliação STAR</span>
          <span className="rounded border border-sky-500/35 bg-sky-500/15 px-2 py-0.5 font-mono font-bold text-sky-200 tabular-nums">
            {ev.score ?? '-'}/10
          </span>
        </div>
        {ev.upgraded_example && (
          <p className="rounded border border-slate-800 bg-[#121824] p-2 text-slate-300">
            {ev.upgraded_example}
          </p>
        )}
      </div>
    );
  }

  if (kind === 'resume_uploaded') {
    return (
      <div className="mt-2.5 flex items-center justify-between rounded-lg border border-emerald-500/30 bg-[#0d141d] p-3 text-xs">
        <div className="flex items-center gap-2 text-emerald-200">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span>Currículo sincronizado com seu perfil</span>
        </div>
        <button
          type="button"
          onClick={() => onNavigateTab('cv')}
          className="rounded border border-emerald-500/35 bg-emerald-500/15 px-2.5 py-1 font-medium text-emerald-300 hover:bg-emerald-500/25"
        >
          Abrir CV Studio
        </button>
      </div>
    );
  }

  if (kind === 'device_action' && payload.result && typeof payload.result === 'object') {
    const res = payload.result as { online?: boolean; success?: boolean; hostname?: string };
    return (
      <div className="mt-2 flex items-center gap-2 rounded-lg border border-slate-700 bg-[#0d121b] px-3 py-2 text-xs text-slate-300">
        <MonitorCheck className="h-4 w-4 text-sky-400" />
        <span>
          Dispositivo:{' '}
          <strong className="text-slate-100">
            {res.online === true
              ? `Online (${res.hostname || 'Windows'})`
              : res.online === false
                ? 'Offline'
                : res.success
                  ? 'Comando enviado'
                  : 'Falha'}
          </strong>
        </span>
      </div>
    );
  }

  return null;
};
