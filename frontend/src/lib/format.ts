import type { ApplicationStage } from '../types/api';

export function formatRelativeDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'agora';
  if (diffMin < 60) return `há ${diffMin} min`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `há ${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `há ${diffDays}d`;
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}

export function formatTimeShort(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

export function formatSalaryRange(
  min: number | null,
  max: number | null,
  currency: string | null,
): string | null {
  if (!min && !max) return null;
  const curr = (currency || 'USD').toUpperCase();
  const fmt = (val: number) =>
    val.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  if (min && max && min !== max) {
    return `${curr} ${fmt(min)} – ${fmt(max)}`;
  }
  const value = max || min || 0;
  return `${curr} ${fmt(value)}`;
}

export function getScoreTone(score: number): {
  badgeClass: string;
  barClass: string;
  textClass: string;
  label: string;
} {
  if (score >= 80) {
    return {
      badgeClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
      barClass: 'bg-emerald-500',
      textClass: 'text-emerald-400',
      label: 'Alta aderência',
    };
  }
  if (score >= 60) {
    return {
      badgeClass: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
      barClass: 'bg-sky-500',
      textClass: 'text-sky-400',
      label: 'Boa compatibilidade',
    };
  }
  if (score >= 40) {
    return {
      badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
      barClass: 'bg-amber-500',
      textClass: 'text-amber-400',
      label: 'Parcial',
    };
  }
  return {
    badgeClass: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    barClass: 'bg-rose-500',
    textClass: 'text-rose-400',
    label: 'Baixa aderência',
  };
}

export function sanitizeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (trimmed.startsWith('https://') || trimmed.startsWith('http://')) {
    return trimmed;
  }
  return null;
}

export const SKILL_CATEGORIES: Array<{ value: string; label: string }> = [
  { value: 'language', label: 'Linguagem' },
  { value: 'framework', label: 'Framework' },
  { value: 'backend', label: 'Backend' },
  { value: 'frontend', label: 'Frontend' },
  { value: 'database', label: 'Banco de Dados' },
  { value: 'devops', label: 'DevOps' },
  { value: 'cloud', label: 'Cloud' },
  { value: 'cloud_devops', label: 'Cloud & DevOps' },
  { value: 'ai', label: 'IA & LLMs' },
  { value: 'ai_ml', label: 'IA & Machine Learning' },
  { value: 'data', label: 'Dados & Analytics' },
  { value: 'mobile', label: 'Mobile' },
  { value: 'testing', label: 'Testes & QA' },
  { value: 'security', label: 'Segurança' },
  { value: 'architecture', label: 'Arquitetura' },
  { value: 'messaging', label: 'Mensageria' },
  { value: 'tool', label: 'Ferramentas' },
  { value: 'practice', label: 'Práticas & Qualidade' },
  { value: 'agile', label: 'Agilidade' },
  { value: 'soft_skill', label: 'Soft Skill' },
  { value: 'domain', label: 'Domínio' },
  { value: 'general', label: 'Geral' },
  { value: 'other', label: 'Outro' },
];

export const SKILL_PROFICIENCIES: Array<{ value: string; label: string }> = [
  { value: 'beginner', label: 'Iniciante' },
  { value: 'intermediate', label: 'Intermediário' },
  { value: 'advanced', label: 'Avançado' },
  { value: 'expert', label: 'Especialista' },
];

export const JOB_SOURCES: Array<{ id: string; label: string; hint: string }> = [
  { id: 'github_br', label: 'GitHub BR', hint: 'Comunidades tech brasileiras' },
  { id: 'remotive', label: 'Remotive', hint: 'Vagas remotas globais' },
  { id: 'arbeitnow', label: 'Arbeitnow', hint: 'Tech Europa & remoto' },
  { id: 'himalayas', label: 'Himalayas', hint: 'Empresas remote-first' },
  { id: 'greenhouse', label: 'Greenhouse', hint: 'Boards das empresas-alvo' },
  { id: 'lever', label: 'Lever', hint: 'Boards das empresas-alvo' },
];

export const APPLICATION_STAGES: Array<{
  id: ApplicationStage;
  label: string;
  pillClass: string;
}> = [
  { id: 'wishlist', label: 'Desejadas', pillClass: 'bg-slate-700/60 text-slate-200 border-slate-600' },
  { id: 'cv_ready', label: 'CV Otimizado', pillClass: 'bg-sky-500/15 text-sky-300 border-sky-500/30' },
  { id: 'applied', label: 'Candidatada', pillClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
  { id: 'screening', label: 'Triagem / RH', pillClass: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30' },
  { id: 'technical_interview', label: 'Entrevista Técnica', pillClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  { id: 'final_interview', label: 'Entrevista Final', pillClass: 'bg-orange-500/15 text-orange-300 border-orange-500/30' },
  { id: 'offer', label: 'Proposta', pillClass: 'bg-emerald-400/20 text-emerald-200 border-emerald-400/40' },
  { id: 'rejected', label: 'Recusada', pillClass: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
];

export function getWorkModelLabel(model: string | null | undefined): string {
  switch ((model || '').toLowerCase()) {
    case 'remote':
      return 'Remoto';
    case 'hybrid':
      return 'Híbrido';
    case 'onsite':
      return 'Presencial';
    default:
      return 'Modelo não informado';
  }
}

export function getContractLabel(contract: string | null | undefined): string {
  switch ((contract || '').toLowerCase()) {
    case 'clt':
      return 'CLT';
    case 'pj':
      return 'PJ';
    case 'contractor':
      return 'Contractor';
    default:
      return contract ? contract.toUpperCase() : 'Não especificado';
  }
}
