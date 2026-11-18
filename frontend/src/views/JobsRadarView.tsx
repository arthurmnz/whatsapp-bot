import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Bookmark,
  BookmarkCheck,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  KanbanSquare,
  Link2,
  Loader2,
  MapPin,
  Plus,
  Radar,
  Search,
  Sparkles,
  XCircle,
} from 'lucide-react';
import { ApiError, api } from '../lib/api';
import {
  JOB_SOURCES,
  formatRelativeDate,
  formatSalaryRange,
  getContractLabel,
  getWorkModelLabel,
  sanitizeExternalUrl,
} from '../lib/format';
import type { JobApplication, JobMatchItem, JobMatchStatus, TailorPrefillContext } from '../types/api';
import { Modal } from '../components/ui/Modal';
import { ScoreBadge, SkeletonBlock } from '../components/ui/ScoreBadge';
import { useToast } from '../components/ui/Toast';

interface JobsRadarViewProps {
  onOpenCvStudio: (prefill: TailorPrefillContext) => void;
  onOpenApplications: () => void;
}

const STATUS_TABS: Array<{ id: string; label: string }> = [
  { id: '', label: 'Todas' },
  { id: 'new', label: 'Novas' },
  { id: 'saved', label: 'Salvas' },
  { id: 'applied', label: 'Candidatadas' },
  { id: 'dismissed', label: 'Dispensadas' },
];

function findExistingApplicationForMatch(
  apps: JobApplication[],
  match: JobMatchItem,
): JobApplication | undefined {
  const job = match.job;
  if (!job) return undefined;
  const companyLow = (job.company_name || 'Empresa').trim().toLowerCase();
  const titleLow = job.title.trim().toLowerCase();
  return apps.find(
    (a) =>
      (a.job_id !== null && a.job_id === job.id) ||
      (a.company_name.trim().toLowerCase() === companyLow &&
        a.role_title.trim().toLowerCase() === titleLow),
  );
}

export const JobsRadarView: React.FC<JobsRadarViewProps> = ({
  onOpenCvStudio,
  onOpenApplications,
}) => {
  const { pushToast } = useToast();

  // Search controls (POST /api/v1/jobs/search)
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSources, setSelectedSources] = useState<string[]>(
    JOB_SOURCES.map((s) => s.id),
  );
  const [customSlugs, setCustomSlugs] = useState('');
  const [searching, setSearching] = useState(false);
  const [lastSearchSummary, setLastSearchSummary] = useState<{
    total_fetched: number;
    sources: Record<string, { fetched: number; error?: string }>;
  } | null>(null);

  // List & filter state (GET /api/v1/jobs)
  const [items, setItems] = useState<JobMatchItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>('');
  const [minScore, setMinScore] = useState<number>(0);
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [languageFilter, setLanguageFilter] = useState<string>('');
  const [localSearch, setLocalSearch] = useState<string>('');

  const [expandedMatchIds, setExpandedMatchIds] = useState<Set<number>>(new Set());
  const [busyMatchId, setBusyMatchId] = useState<number | null>(null);

  // Manual ingest modal (POST /api/v1/jobs/ingest)
  const [ingestOpen, setIngestOpen] = useState(false);
  const [ingestMode, setIngestMode] = useState<'url' | 'text'>('url');
  const [ingestUrl, setIngestUrl] = useState('');
  const [ingestDesc, setIngestDesc] = useState('');
  const [ingestTitle, setIngestTitle] = useState('');
  const [ingestCompany, setIngestCompany] = useState('');
  const [ingestLocation, setIngestLocation] = useState('');
  const [ingestWorkModel, setIngestWorkModel] = useState('');
  const [ingestContract, setIngestContract] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.jobs.list({
        status: statusFilter || undefined,
        min_score: minScore,
        source: sourceFilter || undefined,
        language: languageFilter || undefined,
        search: localSearch || undefined,
        limit: 50,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Erro ao listar vagas.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, minScore, sourceFilter, languageFilter, localSearch]);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  const toggleSource = (id: string) => {
    setSelectedSources((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  };

  const handleRunSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSources.length) {
      pushToast('Selecione ao menos uma fonte gratuita para buscar.', 'error');
      return;
    }

    setSearching(true);
    setLastSearchSummary(null);
    try {
      const slugs = customSlugs
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const res = await api.jobs.search({
        query: searchQuery.trim(),
        sources: selectedSources,
        limit_per_source: 15,
        greenhouse_slugs: slugs.length ? slugs : undefined,
        lever_slugs: slugs.length ? slugs : undefined,
      });
      setLastSearchSummary({ total_fetched: res.total_fetched, sources: res.sources });
      pushToast(`${res.total_fetched} vaga(s) avaliada(s) nas fontes selecionadas.`, 'success');
      await loadJobs();
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Falha ao buscar vagas.', 'error');
    } finally {
      setSearching(false);
    }
  };

  const handleIngestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIngestError(null);
    if (ingestMode === 'url' && !ingestUrl.trim()) {
      setIngestError('Informe a URL pública da vaga.');
      return;
    }
    if (ingestMode === 'text' && !ingestDesc.trim()) {
      setIngestError('Cole a descrição completa da vaga.');
      return;
    }

    setIngesting(true);
    try {
      const created = await api.jobs.ingest({
        url: ingestUrl.trim() || undefined,
        description_raw: ingestMode === 'text' ? ingestDesc.trim() : undefined,
        title: ingestTitle.trim() || undefined,
        company_name: ingestCompany.trim() || undefined,
        location: ingestLocation.trim() || undefined,
        work_model: ingestWorkModel || undefined,
        contract_type: ingestContract || undefined,
      });
      setItems((prev) => [
        created,
        ...prev.filter((item) => item.match_id !== created.match_id),
      ]);
      setIngestOpen(false);
      setIngestUrl('');
      setIngestDesc('');
      setIngestTitle('');
      setIngestCompany('');
      setIngestLocation('');
      setIngestWorkModel('');
      setIngestContract('');
      pushToast(
        `Vaga analisada com Match Score ${created.match_score}/100!`,
        'success',
      );
    } catch (err) {
      setIngestError(err instanceof ApiError ? err.detail : 'Não foi possível analisar a vaga.');
    } finally {
      setIngesting(false);
    }
  };

  const handleMatchStatus = async (match: JobMatchItem, status: JobMatchStatus) => {
    setBusyMatchId(match.match_id);
    try {
      const updated = await api.jobs.updateMatchStatus(match.match_id, status);
      setItems((prev) => prev.map((it) => (it.match_id === match.match_id ? updated : it)));

      if (status === 'saved' && match.job) {
        const appsRes = await api.applications.list();
        const existing = findExistingApplicationForMatch(appsRes.items, match);
        if (!existing) {
          await api.applications.create({
            company_name: match.job.company_name || 'Empresa',
            role_title: match.job.title,
            job_id: match.job.id,
            job_url: match.job.source_url || undefined,
            stage: 'wishlist',
          });
        }
        pushToast('Vaga salva na aba Salvas e na coluna Interesse do Kanban!', 'success');
        return;
      }

      const labels: Record<JobMatchStatus, string> = {
        saved: 'Vaga salva na aba Salvas e na coluna Interesse do Kanban!',
        applied: 'Marcada como candidatada.',
        dismissed: 'Vaga dispensada.',
        new: 'Restaurada.',
        notified: 'Notificada.',
      };
      pushToast(labels[status] || 'Status atualizado.', 'success');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao atualizar vaga.', 'error');
    } finally {
      setBusyMatchId(null);
    }
  };

  const handleApplyAndKanban = async (match: JobMatchItem) => {
    if (!match.job) return;
    setBusyMatchId(match.match_id);
    try {
      const updated = await api.jobs.updateMatchStatus(match.match_id, 'applied');
      setItems((prev) => prev.map((it) => (it.match_id === match.match_id ? updated : it)));

      const appsRes = await api.applications.list();
      const existing = findExistingApplicationForMatch(appsRes.items, match);
      if (existing) {
        await api.applications.update(existing.id, { stage: 'applied' });
      } else {
        await api.applications.create({
          company_name: match.job.company_name || 'Empresa',
          role_title: match.job.title,
          job_id: match.job.id,
          job_url: match.job.source_url || undefined,
          stage: 'applied',
        });
      }
      pushToast('Candidatura registrada e adicionada ao Kanban!', 'success');
    } catch (err) {
      pushToast(
        err instanceof ApiError ? err.detail : 'Erro ao enviar para candidaturas.',
        'error',
      );
    } finally {
      setBusyMatchId(null);
    }
  };

  const toggleExpand = (matchId: number) => {
    setExpandedMatchIds((prev) => {
      const next = new Set(prev);
      if (next.has(matchId)) next.delete(matchId);
      else next.add(matchId);
      return next;
    });
  };

  const showAtsSlugInput =
    selectedSources.includes('greenhouse') || selectedSources.includes('lever');

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">
            Radar de Vagas &amp; Match Inteligente
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Busque em fontes gratuitas ou ingira links/descrições para calcular aderência ao seu
            perfil.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onOpenApplications}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#111621] px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800"
          >
            <KanbanSquare className="h-4 w-4 text-sky-400" />
            Ver Kanban
          </button>
          <button
            type="button"
            onClick={() => {
              setIngestError(null);
              setIngestOpen(true);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/12 px-3.5 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20"
          >
            <Plus className="h-4 w-4" />
            Adicionar Vaga Manualmente
          </button>
        </div>
      </header>

      {/* Free sources search panel */}
      <form
        onSubmit={handleRunSearch}
        className="space-y-4 rounded-xl border border-slate-800/90 bg-[#111621] p-4 sm:p-5"
      >
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8896ab]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filtro opcional (ex: Python, FastAPI, React). Se vazio, usa seu cargo-alvo."
              className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] py-2.5 pl-9 pr-3.5 text-sm text-slate-100 placeholder-[#8896ab] focus:border-emerald-500/70 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={searching}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400 disabled:opacity-60"
          >
            {searching ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Varrendo fontes...
              </>
            ) : (
              <>
                <Radar className="h-4 w-4" />
                Buscar Vagas Agora
              </>
            )}
          </button>
        </div>

        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium text-slate-400">Fontes gratuitas:</span>
            {JOB_SOURCES.map((src) => {
              const active = selectedSources.includes(src.id);
              return (
                <button
                  key={src.id}
                  type="button"
                  title={src.hint}
                  onClick={() => toggleSource(src.id)}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                    active
                      ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
                      : 'border-slate-700/80 bg-[#0b0e14] text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {src.label}
                </button>
              );
            })}
          </div>

          {showAtsSlugInput && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <label htmlFor="ats-slugs" className="text-[11px] text-[#8896ab]">
                Slugs Greenhouse/Lever (opcional, além das empresas-alvo do perfil):
              </label>
              <input
                id="ats-slugs"
                type="text"
                value={customSlugs}
                onChange={(e) => setCustomSlugs(e.target.value)}
                placeholder="ex: nubank, stripe, brex"
                className="min-w-[200px] flex-1 rounded-md border border-slate-700/80 bg-[#0b0e14] px-2.5 py-1 text-xs text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            </div>
          )}
        </div>

        {lastSearchSummary && (
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-800 pt-3 text-[11px]">
            <span className="font-medium text-slate-300">
              Última varredura ({lastSearchSummary.total_fetched} coletadas):
            </span>
            {Object.entries(lastSearchSummary.sources).map(([src, info]) => (
              <span
                key={src}
                className={`rounded border px-2 py-0.5 font-mono ${
                  info.error
                    ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                    : 'border-slate-700 bg-[#0b0e14] text-slate-300'
                }`}
              >
                {src}: {info.error ? 'erro' : info.fetched}
              </span>
            ))}
          </div>
        )}
      </form>

      {/* Local filtering bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-[#111621]/70 px-4 py-3">
        <div className="flex flex-wrap items-center gap-1">
          {STATUS_TABS.map((tab) => {
            const active = statusFilter === tab.id;
            return (
              <button
                key={tab.id || 'all'}
                type="button"
                onClick={() => setStatusFilter(tab.id)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? 'bg-slate-800 text-slate-50'
                    : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            placeholder="Filtrar lista..."
            className="w-40 rounded-md border border-slate-700/80 bg-[#0b0e14] px-2.5 py-1.5 text-xs text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
          />
          <select
            aria-label="Score mínimo"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="rounded-md border border-slate-700/80 bg-[#0b0e14] px-2.5 py-1.5 text-xs text-slate-200 focus:border-sky-500/70 focus:outline-none"
          >
            <option value={0}>Score: Todos</option>
            <option value={50}>Score &ge; 50%</option>
            <option value={70}>Score &ge; 70%</option>
            <option value={85}>Score &ge; 85%</option>
          </select>
          <select
            aria-label="Filtrar por fonte"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="rounded-md border border-slate-700/80 bg-[#0b0e14] px-2.5 py-1.5 text-xs text-slate-200 focus:border-sky-500/70 focus:outline-none"
          >
            <option value="">Fonte: Todas</option>
            {JOB_SOURCES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
            <option value="manual">Manual</option>
          </select>
          <select
            aria-label="Filtrar por idioma"
            value={languageFilter}
            onChange={(e) => setLanguageFilter(e.target.value)}
            className="rounded-md border border-slate-700/80 bg-[#0b0e14] px-2.5 py-1.5 text-xs text-slate-200 focus:border-sky-500/70 focus:outline-none"
          >
            <option value="">Idioma: Todos</option>
            <option value="pt-BR">pt-BR</option>
            <option value="en">en</option>
          </select>
        </div>
      </div>

      {/* Results list */}
      {loading ? (
        <div className="space-y-4">
          <SkeletonBlock className="h-44" />
          <SkeletonBlock className="h-44" />
          <SkeletonBlock className="h-44" />
        </div>
      ) : errorMsg ? (
        <div className="flex items-center justify-between rounded-xl border border-rose-500/35 bg-rose-500/10 p-5 text-sm text-rose-200">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="h-5 w-5 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
          <button
            type="button"
            onClick={() => void loadJobs()}
            className="rounded-lg border border-rose-400/40 px-3 py-1.5 text-xs font-medium hover:bg-rose-500/20"
          >
            Recarregar
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-[#111621] p-10 text-center">
          <BriefcaseBusiness className="mx-auto h-9 w-9 text-slate-500" />
          <h2 className="mt-3 text-base font-semibold text-slate-100">
            Nenhuma vaga encontrada neste filtro
          </h2>
          <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-400">
            Clique em <strong>Buscar Vagas Agora</strong> para consultar as fontes gratuitas ou
            adicione uma vaga manualmente colando o link ou descrição.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="text-xs text-[#8896ab]">
            Exibindo <span className="font-mono text-slate-200">{items.length}</span> de{' '}
            <span className="font-mono text-slate-200">{total}</span> vagas ranqueadas
          </div>

          {items.map((match) => {
            const job = match.job;
            if (!job) return null;
            const expanded = expandedMatchIds.has(match.match_id);
            const salary = formatSalaryRange(
              job.salary_min,
              job.salary_max,
              job.salary_currency,
            );
            const safeUrl = sanitizeExternalUrl(job.source_url);
            const b = match.score_breakdown || {};
            const isBusy = busyMatchId === match.match_id;

            return (
              <article
                key={match.match_id}
                className="rounded-xl border border-slate-800/90 bg-[#111621] p-5 transition-colors hover:border-slate-700/90"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <ScoreBadge score={match.match_score} />
                      <h2 className="text-base font-semibold text-slate-50">{job.title}</h2>
                      {match.status === 'saved' && (
                        <span className="rounded border border-sky-500/30 bg-sky-500/12 px-2 py-0.5 text-[11px] font-medium text-sky-300">
                          Salva
                        </span>
                      )}
                      {match.status === 'applied' && (
                        <span className="rounded border border-emerald-500/30 bg-emerald-500/12 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
                          Candidatada
                        </span>
                      )}
                      {match.status === 'dismissed' && (
                        <span className="rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-[11px] text-slate-400">
                          Dispensada
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-300">
                      <span className="font-medium text-slate-100">
                        {job.company_name || 'Empresa confidencial'}
                      </span>
                      {job.location && (
                        <span className="inline-flex items-center gap-1 text-slate-400">
                          <MapPin className="h-3 w-3" />
                          {job.location}
                        </span>
                      )}
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] text-slate-300">
                        {getWorkModelLabel(job.work_model)}
                      </span>
                      {job.contract_type && job.contract_type !== 'unknown' && (
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] text-slate-300">
                          {getContractLabel(job.contract_type)}
                        </span>
                      )}
                      {salary && (
                        <span className="font-mono text-[11px] text-emerald-300">{salary}</span>
                      )}
                      <span className="font-mono text-[11px] text-[#8896ab]">
                        {job.source} · {job.language || 'en'} · {formatRelativeDate(job.fetched_at)}
                      </span>
                    </div>
                  </div>

                  {safeUrl && (
                    <a
                      href={safeUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800"
                    >
                      <ExternalLink className="h-3.5 w-3.5 text-sky-400" />
                      Ver original
                    </a>
                  )}
                </div>

                {/* Score breakdown strip */}
                <div className="mt-4 grid grid-cols-2 gap-2 rounded-lg border border-slate-800/90 bg-[#0c1018] p-3 font-mono text-[11px] tabular-nums sm:grid-cols-5">
                  <div>
                    <span className="text-[#8896ab]">Skills: </span>
                    <span className="font-semibold text-slate-100">{b.skills_match ?? 0}/50</span>
                  </div>
                  <div>
                    <span className="text-[#8896ab]">Vontades: </span>
                    <span className="font-semibold text-slate-100">
                      {b.preferences_match ?? 0}/25
                    </span>
                  </div>
                  <div>
                    <span className="text-[#8896ab]">Senioridade: </span>
                    <span className="font-semibold text-slate-100">
                      {b.seniority_match ?? 0}/15
                    </span>
                  </div>
                  <div>
                    <span className="text-[#8896ab]">Stack bônus: </span>
                    <span className="font-semibold text-slate-100">
                      {b.desired_stack_bonus ?? 0}/10
                    </span>
                  </div>
                  <div>
                    <span className="text-[#8896ab]">Dealbreaker: </span>
                    <span
                      className={`font-semibold ${
                        (b.dealbreaker_penalty ?? 0) < 0 ? 'text-rose-400' : 'text-slate-300'
                      }`}
                    >
                      {b.dealbreaker_penalty ?? 0}
                    </span>
                  </div>
                </div>

                {/* Matched vs Missing skills */}
                <div className="mt-3.5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <div className="mb-1.5 text-[11px] font-medium text-emerald-400">
                      Skills compatíveis ({match.matched_skills.length})
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {match.matched_skills.length ? (
                        match.matched_skills.map((sk) => (
                          <span
                            key={sk}
                            className="rounded border border-emerald-500/30 bg-emerald-500/12 px-2 py-0.5 text-[11px] font-medium text-emerald-200"
                          >
                            {sk}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-[#8896ab]">Nenhuma direta identificada</span>
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="mb-1.5 text-[11px] font-medium text-amber-400">
                      Skills faltantes / Gaps ({match.missing_skills.length})
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {match.missing_skills.length ? (
                        match.missing_skills.map((sk) => (
                          <span
                            key={sk}
                            className="rounded border border-amber-500/30 bg-amber-500/12 px-2 py-0.5 text-[11px] font-medium text-amber-200"
                          >
                            {sk}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-[#8896ab]">Nenhum gap crítico</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* AI Rationale */}
                {match.ai_rationale && (
                  <p className="mt-3 rounded-lg border border-slate-800 bg-[#0e131c] px-3 py-2 text-xs leading-relaxed text-slate-300">
                    <span className="font-semibold text-sky-300">Análise: </span>
                    {match.ai_rationale}
                  </p>
                )}

                {/* Expandable description */}
                {expanded && job.description_raw && (
                  <div className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg border border-slate-800 bg-[#0b0e14] p-3.5 text-xs leading-relaxed text-slate-300">
                    {job.description_raw}
                  </div>
                )}

                {/* Actions footer */}
                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-3.5">
                  <div className="flex flex-wrap items-center gap-2">
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
                      className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-slate-950 transition-colors hover:bg-emerald-400"
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      Otimizar Meu Currículo para esta Vaga
                    </button>

                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() =>
                        void handleMatchStatus(
                          match,
                          match.status === 'saved' ? 'new' : 'saved',
                        )
                      }
                      className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                        match.status === 'saved'
                          ? 'border-sky-500/40 bg-sky-500/15 text-sky-200'
                          : 'border-slate-700 bg-[#0b0e14] text-slate-200 hover:bg-slate-800'
                      }`}
                    >
                      {match.status === 'saved' ? (
                        <BookmarkCheck className="h-3.5 w-3.5 text-sky-400" />
                      ) : (
                        <Bookmark className="h-3.5 w-3.5" />
                      )}
                      {match.status === 'saved' ? 'Salva' : 'Salvar Vaga'}
                    </button>

                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => void handleApplyAndKanban(match)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#0b0e14] px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-emerald-500/40 hover:bg-slate-800 disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      Marcar Candidatada + Kanban
                    </button>

                    {match.status !== 'dismissed' && (
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => void handleMatchStatus(match, 'dismissed')}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-800 px-2.5 py-1.5 text-xs text-slate-400 hover:border-rose-500/35 hover:text-rose-300 disabled:opacity-50"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        Dispensar
                      </button>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => toggleExpand(match.match_id)}
                    className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 hover:text-slate-200"
                  >
                    {expanded ? (
                      <>
                        Ocultar descrição
                        <ChevronUp className="h-3.5 w-3.5" />
                      </>
                    ) : (
                      <>
                        Ver descrição
                        <ChevronDown className="h-3.5 w-3.5" />
                      </>
                    )}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Manual Ingest Modal */}
      <Modal
        open={ingestOpen}
        onClose={() => setIngestOpen(false)}
        title="Adicionar Vaga Manualmente"
        description="Cole o link público da vaga ou a descrição completa para calcular o Match Score e deixar pronto para o CV Studio."
        maxWidthClass="max-w-2xl"
      >
        <form onSubmit={handleIngestSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-1 rounded-lg border border-slate-800 bg-[#0b0e14] p-1">
            <button
              type="button"
              onClick={() => setIngestMode('url')}
              className={`inline-flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium ${
                ingestMode === 'url' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
              }`}
            >
              <Link2 className="h-3.5 w-3.5 text-sky-400" />
              Por Link (URL pública)
            </button>
            <button
              type="button"
              onClick={() => setIngestMode('text')}
              className={`inline-flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium ${
                ingestMode === 'text' ? 'bg-slate-800 text-slate-100' : 'text-slate-400'
              }`}
            >
              <BriefcaseBusiness className="h-3.5 w-3.5 text-emerald-400" />
              Colar Descrição
            </button>
          </div>

          {ingestError && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
              {ingestError}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="ing-url" className="block text-xs font-medium text-slate-300">
              URL da vaga {ingestMode === 'text' ? '(opcional)' : '(obrigatória)'}
            </label>
            <input
              id="ing-url"
              type="url"
              value={ingestUrl}
              onChange={(e) => setIngestUrl(e.target.value)}
              placeholder="https://boards.greenhouse.io/..."
              className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              required={ingestMode === 'url'}
            />
          </div>

          {ingestMode === 'text' && (
            <div className="space-y-1.5">
              <label htmlFor="ing-desc" className="block text-xs font-medium text-slate-300">
                Descrição completa da vaga
              </label>
              <textarea
                id="ing-desc"
                rows={6}
                value={ingestDesc}
                onChange={(e) => setIngestDesc(e.target.value)}
                placeholder="Cole os requisitos, responsabilidades, stack e benefícios da vaga..."
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-emerald-500/70 focus:outline-none"
                required
              />
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <label htmlFor="ing-title" className="block text-xs font-medium text-slate-300">
                Cargo (opcional)
              </label>
              <input
                id="ing-title"
                type="text"
                value={ingestTitle}
                onChange={(e) => setIngestTitle(e.target.value)}
                placeholder="Ex: Senior Python Engineer"
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="ing-company" className="block text-xs font-medium text-slate-300">
                Empresa (opcional)
              </label>
              <input
                id="ing-company"
                type="text"
                value={ingestCompany}
                onChange={(e) => setIngestCompany(e.target.value)}
                placeholder="Ex: Nubank"
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="ing-model" className="block text-xs font-medium text-slate-300">
                Modelo (opcional)
              </label>
              <select
                id="ing-model"
                value={ingestWorkModel}
                onChange={(e) => setIngestWorkModel(e.target.value)}
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 focus:border-sky-500/70 focus:outline-none"
              >
                <option value="">Detectar automaticamente</option>
                <option value="remote">Remoto</option>
                <option value="hybrid">Híbrido</option>
                <option value="onsite">Presencial</option>
              </select>
            </div>
            <div className="space-y-1">
              <label htmlFor="ing-contract" className="block text-xs font-medium text-slate-300">
                Contrato (opcional)
              </label>
              <select
                id="ing-contract"
                value={ingestContract}
                onChange={(e) => setIngestContract(e.target.value)}
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 focus:border-sky-500/70 focus:outline-none"
              >
                <option value="">Detectar automaticamente</option>
                <option value="clt">CLT</option>
                <option value="pj">PJ</option>
                <option value="contractor">Contractor</option>
              </select>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
            <button
              type="button"
              onClick={() => setIngestOpen(false)}
              className="rounded-lg border border-slate-700 px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={ingesting}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
            >
              {ingesting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Analisando vaga...
                </>
              ) : (
                <>
                  <Plus className="h-3.5 w-3.5" />
                  Analisar e Salvar Vaga
                </>
              )}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
