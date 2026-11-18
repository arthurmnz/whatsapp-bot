import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Check,
  Loader2,
  Plus,
  Save,
  SlidersHorizontal,
  Star,
  Trash2,
  User,
  Wrench,
} from 'lucide-react';
import { ApiError, api } from '../lib/api';
import { SKILL_CATEGORIES, SKILL_PROFICIENCIES } from '../lib/format';
import type { CandidateLanguage, CandidateProfile, JobPreferences } from '../types/api';
import { SkeletonBlock } from '../components/ui/ScoreBadge';
import { TagInput } from '../components/ui/TagInput';
import { useToast } from '../components/ui/Toast';

type ProfileSectionTab = 'general' | 'skills' | 'preferences';

const SENIORITY_OPTIONS = [
  { id: 'intern', label: 'Estágio' },
  { id: 'junior', label: 'Júnior' },
  { id: 'mid', label: 'Pleno' },
  { id: 'senior', label: 'Sênior' },
  { id: 'staff', label: 'Staff / Principal' },
];

const WORK_MODEL_OPTIONS = [
  { id: 'remote', label: 'Remoto' },
  { id: 'hybrid', label: 'Híbrido' },
  { id: 'onsite', label: 'Presencial' },
];

const CONTRACT_OPTIONS = [
  { id: 'clt', label: 'CLT' },
  { id: 'pj', label: 'PJ' },
  { id: 'contractor', label: 'Contractor (USD/EUR)' },
];

export const ProfileView: React.FC = () => {
  const { pushToast } = useToast();

  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [section, setSection] = useState<ProfileSectionTab>('general');

  // General form
  const [headline, setHeadline] = useState('');
  const [summary, setSummary] = useState('');
  const [yearsExp, setYearsExp] = useState<string>('0');
  const [location, setLocation] = useState('');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [portfolioUrl, setPortfolioUrl] = useState('');
  const [languages, setLanguages] = useState<CandidateLanguage[]>([]);
  const [newLangName, setNewLangName] = useState('');
  const [newLangLevel, setNewLangLevel] = useState('Avançado');
  const [savingGeneral, setSavingGeneral] = useState(false);

  // Skill creation form
  const [skillName, setSkillName] = useState('');
  const [skillCategory, setSkillCategory] = useState('language');
  const [skillProficiency, setSkillProficiency] = useState('advanced');
  const [skillYears, setSkillYears] = useState('');
  const [skillIsCore, setSkillIsCore] = useState(true);
  const [quickBatchSkills, setQuickBatchSkills] = useState('');
  const [savingSkills, setSavingSkills] = useState(false);

  // Preferences form
  const [prefs, setPrefs] = useState<JobPreferences>({
    target_roles: [],
    seniority_levels: [],
    work_models: ['remote'],
    contract_types: [],
    min_salary: null,
    salary_currency: 'BRL',
    desired_stack: [],
    dealbreakers: [],
    target_companies: [],
    preferred_language: 'auto',
    auto_search_enabled: false,
    min_notify_score: 70,
  });
  const [savingPrefs, setSavingPrefs] = useState(false);

  const hydrateState = useCallback((data: CandidateProfile) => {
    setProfile(data);
    setHeadline(data.headline || '');
    setSummary(data.summary || '');
    setYearsExp(String(data.years_experience ?? 0));
    setLocation(data.location || '');
    setLinkedinUrl(data.linkedin_url || '');
    setGithubUrl(data.github_url || '');
    setPortfolioUrl(data.portfolio_url || '');
    setLanguages(Array.isArray(data.languages) ? data.languages : []);
    setPrefs(data.preferences);
  }, []);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await api.profile.get();
      hydrateState(data);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.detail : 'Erro ao carregar perfil.');
    } finally {
      setLoading(false);
    }
  }, [hydrateState]);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  const handleSaveGeneral = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingGeneral(true);
    try {
      const parsedYears = Math.max(0, Math.min(70, Number(yearsExp) || 0));
      const normalizedLanguages = languages
        .map((item) => {
          const langText = (item.language || item.name || '').trim();
          const levelText = (item.level || '').trim();
          return {
            language: langText,
            name: langText,
            level: levelText,
          };
        })
        .filter((item) => item.language.length > 0);

      const updated = await api.profile.update({
        headline,
        summary,
        years_experience: parsedYears,
        location,
        linkedin_url: linkedinUrl,
        github_url: githubUrl,
        portfolio_url: portfolioUrl,
        languages: normalizedLanguages,
      });
      hydrateState(updated);
      pushToast('Dados profissionais salvos com sucesso.', 'success');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao salvar perfil.', 'error');
    } finally {
      setSavingGeneral(false);
    }
  };

  const handleAddLanguage = () => {
    const clean = newLangName.trim();
    if (!clean) return;
    setLanguages((prev) => [...prev, { language: clean, name: clean, level: newLangLevel }]);
    setNewLangName('');
  };

  const handleAddDetailedSkill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    const cleanName = skillName.trim();
    if (!cleanName) return;

    setSavingSkills(true);
    try {
      const existing = (profile.skills || []).map((sk) => ({
        name: sk.name,
        category: sk.category,
        proficiency: sk.proficiency,
        years_used: sk.years_used,
        is_core: sk.is_core,
      }));
      const yearsNum = skillYears.trim() ? Number(skillYears) : null;
      const filtered = existing.filter(
        (s) => s.name.toLowerCase() !== cleanName.toLowerCase(),
      );
      filtered.push({
        name: cleanName,
        category: skillCategory,
        proficiency: skillProficiency,
        years_used: yearsNum !== null && !Number.isNaN(yearsNum) ? yearsNum : null,
        is_core: skillIsCore,
      });
      const updated = await api.profile.update({ skills: filtered });
      hydrateState(updated);
      setSkillName('');
      setSkillYears('');
      pushToast(`Skill "${cleanName}" adicionada na matriz.`, 'success');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao salvar skill.', 'error');
    } finally {
      setSavingSkills(false);
    }
  };

  const handleQuickBatchSkills = async (e: React.FormEvent) => {
    e.preventDefault();
    const list = quickBatchSkills
      .split(/[,;\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!list.length) return;

    setSavingSkills(true);
    try {
      const updated = await api.profile.addSkills(list, false);
      hydrateState(updated);
      setQuickBatchSkills('');
      pushToast(`${list.length} skill(s) processada(s) no perfil.`, 'success');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao adicionar skills.', 'error');
    } finally {
      setSavingSkills(false);
    }
  };

  const handleToggleCoreSkill = async (skillId: number) => {
    if (!profile) return;
    setSavingSkills(true);
    try {
      const nextSkills = profile.skills.map((sk) => ({
        name: sk.name,
        category: sk.category,
        proficiency: sk.proficiency,
        years_used: sk.years_used,
        is_core: sk.id === skillId ? !sk.is_core : sk.is_core,
      }));
      const updated = await api.profile.update({ skills: nextSkills });
      hydrateState(updated);
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao atualizar skill.', 'error');
    } finally {
      setSavingSkills(false);
    }
  };

  const handleDeleteSkill = async (skillId: number, name: string) => {
    setSavingSkills(true);
    try {
      const updated = await api.profile.deleteSkill(skillId);
      hydrateState(updated);
      pushToast(`Skill "${name}" removida.`, 'info');
    } catch (err) {
      pushToast(err instanceof ApiError ? err.detail : 'Erro ao remover skill.', 'error');
    } finally {
      setSavingSkills(false);
    }
  };

  const togglePrefList = (
    field: 'seniority_levels' | 'work_models' | 'contract_types',
    value: string,
  ) => {
    setPrefs((prev) => {
      const curr = prev[field] || [];
      const exists = curr.includes(value);
      return {
        ...prev,
        [field]: exists ? curr.filter((x) => x !== value) : [...curr, value],
      };
    });
  };

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingPrefs(true);
    try {
      const updated = await api.profile.updatePreferences(prefs);
      hydrateState(updated);
      pushToast('Vontades de mercado atualizadas com sucesso.', 'success');
    } catch (err) {
      pushToast(
        err instanceof ApiError ? err.detail : 'Erro ao salvar preferências.',
        'error',
      );
    } finally {
      setSavingPrefs(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-5 p-6">
        <SkeletonBlock className="h-8 w-64" />
        <SkeletonBlock className="h-12 w-full" />
        <SkeletonBlock className="h-72 w-full" />
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
            onClick={() => void loadProfile()}
            className="rounded-lg border border-rose-400/40 px-3 py-1.5 text-xs font-medium hover:bg-rose-500/20"
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">
            Meu Perfil, Habilidades &amp; Vontades de Mercado
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Estes dados calibram o Match Score das vagas e alimentam o otimizador anti-alucinação
            de currículos.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono tabular-nums text-slate-300">
          <span className="rounded-md border border-slate-800 bg-[#111621] px-2.5 py-1">
            {profile?.skills.length ?? 0} skills
          </span>
          <span className="rounded-md border border-slate-800 bg-[#111621] px-2.5 py-1">
            {prefs.target_roles.length} cargos alvo
          </span>
          <span className="rounded-md border border-rose-500/25 bg-rose-500/10 px-2.5 py-1 text-rose-300">
            {prefs.dealbreakers.length} dealbreakers
          </span>
        </div>
      </header>

      {/* Section tabs */}
      <div
        role="tablist"
        aria-label="Seções do perfil"
        className="flex flex-wrap gap-1.5 rounded-xl border border-slate-800 bg-[#111621] p-1.5"
      >
        <button
          type="button"
          role="tab"
          aria-selected={section === 'general'}
          onClick={() => setSection('general')}
          className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition-colors sm:text-sm ${
            section === 'general'
              ? 'bg-slate-800 text-slate-50'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <User className="h-4 w-4 text-sky-400" />
          Resumo &amp; Links
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={section === 'skills'}
          onClick={() => setSection('skills')}
          className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition-colors sm:text-sm ${
            section === 'skills'
              ? 'bg-slate-800 text-slate-50'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Wrench className="h-4 w-4 text-emerald-400" />
          Matriz de Habilidades ({profile?.skills.length ?? 0})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={section === 'preferences'}
          onClick={() => setSection('preferences')}
          className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition-colors sm:text-sm ${
            section === 'preferences'
              ? 'bg-slate-800 text-slate-50'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <SlidersHorizontal className="h-4 w-4 text-amber-400" />
          Vontades de Mercado
        </button>
      </div>

      {/* 1. GENERAL SECTION */}
      {section === 'general' && (
        <form
          onSubmit={handleSaveGeneral}
          className="animate-panel-enter space-y-6 rounded-xl border border-slate-800/90 bg-[#111621] p-5 sm:p-6"
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5 sm:col-span-2">
              <label htmlFor="prof-headline" className="block text-xs font-medium text-slate-300">
                Headline Profissional
              </label>
              <input
                id="prof-headline"
                type="text"
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                placeholder="Ex: Senior Backend Engineer | Python, FastAPI & Cloud"
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="prof-years" className="block text-xs font-medium text-slate-300">
                Anos de Experiência
              </label>
              <input
                id="prof-years"
                type="number"
                step="0.5"
                min="0"
                max="70"
                value={yearsExp}
                onChange={(e) => setYearsExp(e.target.value)}
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 font-mono text-sm text-slate-100 tabular-nums focus:border-sky-500/70 focus:outline-none"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="prof-summary" className="block text-xs font-medium text-slate-300">
              Resumo Profissional
            </label>
            <textarea
              id="prof-summary"
              rows={4}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="Descreva sua trajetória, principais entregas, arquitetura e especialidades..."
              className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3.5 py-2.5 text-sm leading-relaxed text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label htmlFor="prof-location" className="block text-xs font-medium text-slate-300">
                Localização
              </label>
              <input
                id="prof-location"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Ex: São Paulo, SP — Brasil"
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="prof-linkedin" className="block text-xs font-medium text-slate-300">
                LinkedIn URL
              </label>
              <input
                id="prof-linkedin"
                type="url"
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
                placeholder="https://linkedin.com/in/seu-perfil"
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="prof-github" className="block text-xs font-medium text-slate-300">
                GitHub URL
              </label>
              <input
                id="prof-github"
                type="url"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                placeholder="https://github.com/seu-usuario"
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="prof-portfolio" className="block text-xs font-medium text-slate-300">
                Portfólio / Site
              </label>
              <input
                id="prof-portfolio"
                type="url"
                value={portfolioUrl}
                onChange={(e) => setPortfolioUrl(e.target.value)}
                placeholder="https://seusite.dev"
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
            </div>
          </div>

          {/* Languages */}
          <div className="space-y-2.5 border-t border-slate-800 pt-5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Idiomas
            </h3>
            <div className="flex flex-wrap gap-2">
              {languages.map((item, idx) => {
                const langLabel = (item.language || item.name || '').trim();
                const levelLabel = (item.level || '').trim();
                if (!langLabel) return null;
                return (
                  <span
                    key={`${langLabel}-${idx}`}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-[#171e2c] px-2.5 py-1 text-xs text-slate-200"
                  >
                    <span>
                      {langLabel}
                      {levelLabel && (
                        <>
                          {' '}
                          · <span className="text-slate-400">{levelLabel}</span>
                        </>
                      )}
                    </span>
                    <button
                      type="button"
                      onClick={() => setLanguages((prev) => prev.filter((_, i) => i !== idx))}
                      className="text-slate-400 hover:text-rose-300"
                      aria-label={`Remover idioma ${langLabel}`}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </span>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                type="text"
                value={newLangName}
                onChange={(e) => setNewLangName(e.target.value)}
                placeholder="Idioma (ex: Inglês)"
                className="min-w-[160px] flex-1 rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
              />
              <select
                value={newLangLevel}
                onChange={(e) => setNewLangLevel(e.target.value)}
                className="rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-1.5 text-xs text-slate-100 focus:border-sky-500/70 focus:outline-none"
              >
                <option value="Nativo">Nativo</option>
                <option value="Fluente">Fluente</option>
                <option value="Avançado">Avançado</option>
                <option value="Intermediário">Intermediário</option>
                <option value="Básico">Básico</option>
              </select>
              <button
                type="button"
                onClick={handleAddLanguage}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
              >
                <Plus className="h-3.5 w-3.5" />
                Adicionar idioma
              </button>
            </div>
          </div>

          <div className="flex justify-end border-t border-slate-800 pt-4">
            <button
              type="submit"
              disabled={savingGeneral}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
            >
              {savingGeneral ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Salvar Dados Profissionais
            </button>
          </div>
        </form>
      )}

      {/* 2. SKILLS MATRIX SECTION */}
      {section === 'skills' && (
        <div className="animate-panel-enter space-y-5">
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {/* Detailed skill entry */}
            <form
              onSubmit={handleAddDetailedSkill}
              className="space-y-4 rounded-xl border border-slate-800/90 bg-[#111621] p-5"
            >
              <h2 className="text-sm font-semibold text-slate-100">
                Adicionar Skill Detalhada
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1 sm:col-span-2">
                  <label htmlFor="sk-name" className="block text-xs font-medium text-slate-300">
                    Nome da Skill
                  </label>
                  <input
                    id="sk-name"
                    type="text"
                    value={skillName}
                    onChange={(e) => setSkillName(e.target.value)}
                    placeholder="Ex: FastAPI, React, PostgreSQL, Docker"
                    className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-emerald-500/70 focus:outline-none"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label htmlFor="sk-cat" className="block text-xs font-medium text-slate-300">
                    Categoria
                  </label>
                  <select
                    id="sk-cat"
                    value={skillCategory}
                    onChange={(e) => setSkillCategory(e.target.value)}
                    className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 focus:border-emerald-500/70 focus:outline-none"
                  >
                    {SKILL_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label htmlFor="sk-prof" className="block text-xs font-medium text-slate-300">
                    Nível
                  </label>
                  <select
                    id="sk-prof"
                    value={skillProficiency}
                    onChange={(e) => setSkillProficiency(e.target.value)}
                    className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 focus:border-emerald-500/70 focus:outline-none"
                  >
                    {SKILL_PROFICIENCIES.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label htmlFor="sk-yrs" className="block text-xs font-medium text-slate-300">
                    Anos de uso (opcional)
                  </label>
                  <input
                    id="sk-yrs"
                    type="number"
                    step="0.5"
                    min="0"
                    max="40"
                    value={skillYears}
                    onChange={(e) => setSkillYears(e.target.value)}
                    placeholder="Ex: 3.5"
                    className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 font-mono text-sm text-slate-100 placeholder-[#8896ab] tabular-nums focus:border-emerald-500/70 focus:outline-none"
                  />
                </div>

                <div className="flex items-end pb-1">
                  <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-200">
                    <input
                      type="checkbox"
                      checked={skillIsCore}
                      onChange={(e) => setSkillIsCore(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
                    />
                    <span>Principal (Core)</span>
                  </label>
                </div>
              </div>

              <button
                type="submit"
                disabled={savingSkills}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
              >
                {savingSkills ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Plus className="h-3.5 w-3.5" />
                )}
                Adicionar à matriz
              </button>
            </form>

            {/* Quick batch import */}
            <form
              onSubmit={handleQuickBatchSkills}
              className="flex flex-col justify-between space-y-4 rounded-xl border border-slate-800/90 bg-[#111621] p-5"
            >
              <div className="space-y-3">
                <h2 className="text-sm font-semibold text-slate-100">
                  Importação Rápida em Lote
                </h2>
                <p className="text-xs leading-relaxed text-slate-400">
                  Cole várias tecnologias separadas por vírgula. O backend categoriza
                  automaticamente e ignora duplicatas.
                </p>
                <textarea
                  rows={4}
                  value={quickBatchSkills}
                  onChange={(e) => setQuickBatchSkills(e.target.value)}
                  placeholder="Ex: Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, TypeScript"
                  className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 placeholder-[#8896ab] focus:border-sky-500/70 focus:outline-none"
                />
              </div>
              <div>
                <button
                  type="submit"
                  disabled={savingSkills || !quickBatchSkills.trim()}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-50"
                >
                  <Plus className="h-3.5 w-3.5 text-sky-400" />
                  Adicionar em lote
                </button>
              </div>
            </form>
          </div>

          {/* Skills table */}
          <div className="overflow-hidden rounded-xl border border-slate-800/90 bg-[#111621]">
            <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3.5">
              <h3 className="text-sm font-semibold text-slate-100">
                Competências Cadastradas ({profile?.skills.length ?? 0})
              </h3>
              <span className="text-[11px] text-[#8896ab]">
                Clique na estrela para marcar/desmarcar como Principal (Core)
              </span>
            </div>

            {!profile?.skills.length ? (
              <div className="p-8 text-center text-xs text-[#8896ab]">
                Nenhuma skill cadastrada ainda. Adicione manualmente acima ou faça upload do seu
                currículo no CV Studio com sincronização automática.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 bg-[#0e131c] text-[11px] uppercase tracking-wider text-slate-400">
                      <th className="px-4 py-2.5 font-medium">Core</th>
                      <th className="px-4 py-2.5 font-medium">Skill</th>
                      <th className="px-4 py-2.5 font-medium">Categoria</th>
                      <th className="px-4 py-2.5 font-medium">Nível</th>
                      <th className="px-4 py-2.5 font-medium">Anos</th>
                      <th className="px-4 py-2.5 text-right font-medium">Ação</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {profile.skills.map((sk) => {
                      const catLabel =
                        SKILL_CATEGORIES.find((c) => c.value === sk.category)?.label ||
                        sk.category;
                      const profLabel =
                        SKILL_PROFICIENCIES.find((p) => p.value === sk.proficiency)?.label ||
                        sk.proficiency;
                      return (
                        <tr key={sk.id} className="hover:bg-slate-800/35">
                          <td className="px-4 py-2.5">
                            <button
                              type="button"
                              disabled={savingSkills}
                              onClick={() => void handleToggleCoreSkill(sk.id)}
                              title={
                                sk.is_core
                                  ? 'Skill Principal (Core)'
                                  : 'Marcar como Principal (Core)'
                              }
                              className={`rounded p-1 transition-colors ${
                                sk.is_core
                                  ? 'text-amber-400 hover:bg-amber-500/15'
                                  : 'text-slate-600 hover:text-slate-300'
                              }`}
                            >
                              <Star
                                className="h-4 w-4"
                                fill={sk.is_core ? 'currentColor' : 'none'}
                              />
                            </button>
                          </td>
                          <td className="px-4 py-2.5 font-semibold text-slate-100">{sk.name}</td>
                          <td className="px-4 py-2.5 text-slate-300">{catLabel}</td>
                          <td className="px-4 py-2.5">
                            <span className="rounded border border-slate-700 bg-slate-800/70 px-2 py-0.5 text-[11px] text-slate-200">
                              {profLabel}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 font-mono tabular-nums text-slate-300">
                            {sk.years_used !== null ? `${sk.years_used}a` : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <button
                              type="button"
                              disabled={savingSkills}
                              onClick={() => void handleDeleteSkill(sk.id, sk.name)}
                              className="rounded p-1 text-slate-400 hover:bg-rose-500/15 hover:text-rose-300"
                              aria-label={`Remover ${sk.name}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. MARKET PREFERENCES SECTION */}
      {section === 'preferences' && (
        <form
          onSubmit={handleSavePreferences}
          className="animate-panel-enter space-y-6 rounded-xl border border-slate-800/90 bg-[#111621] p-5 sm:p-6"
        >
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <TagInput
              label="Cargos Desejados"
              values={prefs.target_roles}
              onChange={(target_roles) => setPrefs((p) => ({ ...p, target_roles }))}
              placeholder="Ex: Backend Engineer, Tech Lead, Full Stack Python"
              tone="accent"
            />

            <TagInput
              label="Stack Desejada (bônus no match)"
              values={prefs.desired_stack}
              onChange={(desired_stack) => setPrefs((p) => ({ ...p, desired_stack }))}
              placeholder="Ex: Python, FastAPI, LangChain, PostgreSQL"
            />

            <TagInput
              label="Dealbreakers (tecnologias ou filtros rejeitados)"
              values={prefs.dealbreakers}
              onChange={(dealbreakers) => setPrefs((p) => ({ ...p, dealbreakers }))}
              placeholder="Ex: PHP, WordPress, presencial, Java legado"
              hint="Vagas com estes termos recebem penalidade automática de -25 a -50 pts no Match Score."
              tone="danger"
            />

            <TagInput
              label="Empresas-alvo (slugs Greenhouse / Lever)"
              values={prefs.target_companies}
              onChange={(target_companies) => setPrefs((p) => ({ ...p, target_companies }))}
              placeholder="Ex: nubank, stripe, brex, datadog"
              hint="Usadas automaticamente nas buscas nas APIs públicas Greenhouse e Lever."
            />
          </div>

          <div className="grid grid-cols-1 gap-5 border-t border-slate-800 pt-5 md:grid-cols-3">
            {/* Seniority */}
            <div className="space-y-2">
              <span className="block text-xs font-medium text-slate-300">Senioridades</span>
              <div className="flex flex-wrap gap-1.5">
                {SENIORITY_OPTIONS.map((opt) => {
                  const active = prefs.seniority_levels.includes(opt.id);
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => togglePrefList('seniority_levels', opt.id)}
                      className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        active
                          ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300'
                          : 'border-slate-700 bg-[#0b0e14] text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {active && <Check className="h-3 w-3" />}
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Work models */}
            <div className="space-y-2">
              <span className="block text-xs font-medium text-slate-300">Modelos de Trabalho</span>
              <div className="flex flex-wrap gap-1.5">
                {WORK_MODEL_OPTIONS.map((opt) => {
                  const active = prefs.work_models.includes(opt.id);
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => togglePrefList('work_models', opt.id)}
                      className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        active
                          ? 'border-sky-500/40 bg-sky-500/15 text-sky-300'
                          : 'border-slate-700 bg-[#0b0e14] text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {active && <Check className="h-3 w-3" />}
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Contract types */}
            <div className="space-y-2">
              <span className="block text-xs font-medium text-slate-300">Tipos de Contrato</span>
              <div className="flex flex-wrap gap-1.5">
                {CONTRACT_OPTIONS.map((opt) => {
                  const active = prefs.contract_types.includes(opt.id);
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => togglePrefList('contract_types', opt.id)}
                      className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        active
                          ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300'
                          : 'border-slate-700 bg-[#0b0e14] text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {active && <Check className="h-3 w-3" />}
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 border-t border-slate-800 pt-5 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1.5">
              <label htmlFor="pref-salary" className="block text-xs font-medium text-slate-300">
                Pretensão Salarial Mínima
              </label>
              <input
                id="pref-salary"
                type="number"
                min="0"
                step="500"
                value={prefs.min_salary ?? ''}
                onChange={(e) =>
                  setPrefs((p) => ({
                    ...p,
                    min_salary: e.target.value ? Number(e.target.value) : null,
                  }))
                }
                placeholder="Ex: 12000"
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 font-mono text-sm text-slate-100 placeholder-[#8896ab] tabular-nums focus:border-sky-500/70 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="pref-currency" className="block text-xs font-medium text-slate-300">
                Moeda
              </label>
              <select
                id="pref-currency"
                value={prefs.salary_currency}
                onChange={(e) => setPrefs((p) => ({ ...p, salary_currency: e.target.value }))}
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 focus:border-sky-500/70 focus:outline-none"
              >
                <option value="BRL">BRL (R$)</option>
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="pref-lang" className="block text-xs font-medium text-slate-300">
                Idioma Preferido (CV &amp; Vagas)
              </label>
              <select
                id="pref-lang"
                value={prefs.preferred_language}
                onChange={(e) => setPrefs((p) => ({ ...p, preferred_language: e.target.value }))}
                className="w-full rounded-lg border border-slate-700/80 bg-[#0b0e14] px-3 py-2 text-sm text-slate-100 focus:border-sky-500/70 focus:outline-none"
              >
                <option value="auto">Automático (segue a vaga)</option>
                <option value="pt-BR">Português (pt-BR)</option>
                <option value="en">Inglês (en)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="pref-score" className="block text-xs font-medium text-slate-300">
                Score mínimo p/ alerta ({prefs.min_notify_score}%)
              </label>
              <input
                id="pref-score"
                type="range"
                min="0"
                max="100"
                step="5"
                value={prefs.min_notify_score}
                onChange={(e) =>
                  setPrefs((p) => ({ ...p, min_notify_score: Number(e.target.value) }))
                }
                className="mt-2 w-full accent-emerald-500"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-800 pt-4">
            <label className="inline-flex cursor-pointer items-center gap-2.5 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={prefs.auto_search_enabled}
                onChange={(e) =>
                  setPrefs((p) => ({ ...p, auto_search_enabled: e.target.checked }))
                }
                className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
              />
              <span>Habilitar alertas automáticos de vagas compatíveis no WhatsApp</span>
            </label>

            <button
              type="submit"
              disabled={savingPrefs}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
            >
              {savingPrefs ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Salvar Vontades de Mercado
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
