export interface UserSummary {
  id: number;
  nome: string;
  role: string;
  permissions: string[];
  has_web_password: boolean;
  is_active: boolean;
}

export interface RequestOtpResponse {
  status: 'sent' | 'unavailable' | string;
  delivery: 'whatsapp' | 'unconfigured' | string;
  expires_in_seconds: number;
  message: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user: UserSummary;
}

export interface SetPasswordPayload {
  password: string;
  current_password?: string;
}

export type SkillCategory =
  | 'language'
  | 'framework'
  | 'database'
  | 'cloud_devops'
  | 'ai_ml'
  | 'soft_skill'
  | 'domain'
  | 'backend'
  | 'frontend'
  | 'devops'
  | 'cloud'
  | 'testing'
  | 'ai'
  | 'data'
  | 'mobile'
  | 'security'
  | 'general'
  | 'other';

export type SkillProficiency = 'beginner' | 'intermediate' | 'advanced' | 'expert';

export interface CandidateSkill {
  id: number;
  name: string;
  normalized_name: string;
  category: SkillCategory | string;
  proficiency: SkillProficiency | string;
  years_used: number | null;
  is_core: boolean;
}

export interface CandidateLanguage {
  language?: string;
  name?: string;
  level?: string;
}

export interface JobPreferences {
  target_roles: string[];
  seniority_levels: string[];
  work_models: string[];
  contract_types: string[];
  min_salary: number | null;
  salary_currency: string;
  desired_stack: string[];
  dealbreakers: string[];
  target_companies: string[];
  preferred_language: 'auto' | 'pt-BR' | 'en' | string;
  auto_search_enabled: boolean;
  min_notify_score: number;
}

export interface CandidateProfile {
  id: number;
  user_id: number;
  headline: string;
  summary: string;
  years_experience: number;
  location: string;
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
  languages: CandidateLanguage[];
  skills: CandidateSkill[];
  preferences: JobPreferences;
  updated_at: string | null;
}

export type JobMatchStatus = 'new' | 'notified' | 'saved' | 'dismissed' | 'applied';

export type JobSeniorityFilter = '' | 'intern' | 'junior' | 'mid' | 'senior' | 'lead';
export type JobWorkModelFilter = '' | 'remote' | 'hybrid' | 'onsite';

export interface JobSearchPayload {
  query?: string;
  sources?: string[];
  limit_per_source?: number;
  greenhouse_slugs?: string[];
  lever_slugs?: string[];
  seniority?: string;
  location?: string;
  work_model?: string;
}

export interface JobListParams {
  status?: string;
  min_score?: number;
  source?: string;
  language?: string;
  seniority?: string;
  location?: string;
  work_model?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface JobPosting {
  id: number;
  source: string;
  external_id: string | null;
  source_url: string | null;
  title: string;
  company_name: string | null;
  location: string | null;
  work_model: string | null;
  contract_type: string | null;
  seniority: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  language: string | null;
  description_raw: string;
  extracted_requirements: Record<string, unknown>;
  posted_at: string | null;
  fetched_at: string | null;
}

export interface ScoreBreakdown {
  skills_match?: number;
  preferences_match?: number;
  seniority_match?: number;
  desired_stack_bonus?: number;
  dealbreaker_penalty?: number;
}

export interface JobMatchItem {
  match_id: number;
  job_id: number;
  match_score: number;
  score_breakdown: ScoreBreakdown;
  matched_skills: string[];
  missing_skills: string[];
  ai_rationale: string;
  status: JobMatchStatus | string;
  created_at: string | null;
  job: JobPosting | null;
}

export interface JobSearchResponse {
  query: string;
  total_fetched: number;
  sources: Record<string, { fetched: number; error?: string }>;
  items: JobMatchItem[];
}

export interface BaseResume {
  id: number;
  user_id: number;
  title: string;
  language: string;
  is_default: boolean;
  source_format: string;
  has_file: boolean;
  raw_text: string;
  structured_data: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface AtsBreakdown {
  keywords_score: number;
  experience_score: number;
  impact_score: number;
  formatting_score: number;
}

export interface EvaluationReport {
  target_language?: string;
  breakdown_before?: AtsBreakdown;
  breakdown_after?: AtsBreakdown;
  matched_keywords?: string[];
  missing_keywords?: string[];
  missing_but_in_profile?: string[];
  real_gaps?: string[];
  critique_points?: string[];
  improvement_suggestions?: string[];
}

export interface ChangeSummaryItem {
  section: string;
  action: string;
  reason: string;
}

export interface InterviewQuestion {
  question: string;
  focus?: string;
  sample_angle?: string;
}

export interface InterviewPrep {
  target_language?: string;
  likely_questions?: InterviewQuestion[];
  gap_mitigation_tips?: string[];
  key_talking_points?: string[];
  questions_to_ask_interviewer?: string[];
}

export interface TailoredResume {
  id: number;
  user_id: number;
  base_resume_id: number | null;
  job_id: number | null;
  job_title: string;
  company_name: string;
  job_description_snapshot: string;
  target_language: 'pt-BR' | 'en' | string;
  ats_score_before: number;
  ats_score_after: number;
  evaluation_report: EvaluationReport;
  changes_summary: ChangeSummaryItem[];
  tailored_data: Record<string, unknown>;
  tailored_markdown: string;
  has_pdf: boolean;
  has_docx: boolean;
  cover_letter: string;
  interview_prep: InterviewPrep;
  created_at: string | null;
  updated_at: string | null;
}

export type ApplicationStage =
  | 'wishlist'
  | 'cv_ready'
  | 'applied'
  | 'screening'
  | 'technical_interview'
  | 'final_interview'
  | 'offer'
  | 'rejected'
  | 'withdrawn';

export interface JobApplication {
  id: number;
  user_id: number;
  job_id: number | null;
  tailored_resume_id: number | null;
  company_name: string;
  role_title: string;
  job_url: string;
  stage: ApplicationStage;
  notes: string;
  applied_at: string | null;
  follow_up_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ApplicationInterviewPrepResponse {
  application_id: number;
  company_name: string;
  role_title: string;
  interview_prep: InterviewPrep;
}

export interface ChatThread {
  id: number;
  user_id: number;
  title: string;
  channel_origin: string;
  context_type: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface ChatMessage {
  id: number;
  thread_id: number;
  role: 'user' | 'assistant' | string;
  channel: string;
  content: string;
  rich_payload: Record<string, unknown> | null;
  created_at: string | null;
}

export interface SendMessageResponse {
  thread_id: number;
  reply_text: string;
  rich_payload: Record<string, unknown> | null;
  generated_filename: string | null;
  messages: ChatMessage[];
}

export interface LLMStatusSummary {
  provider: string;
  base_url: string;
  chat_model: string;
  cv_model: string;
  temperature: number;
  is_local: boolean;
  available: boolean;
}

export interface SystemOverview {
  user: UserSummary;
  profile_summary: {
    headline: string;
    years_experience: number;
    location: string;
    target_roles: string[];
  };
  counts: {
    skills: number;
    base_resumes: number;
    tailored_resumes: number;
    matched_jobs: number;
    compatible_jobs: number;
    saved_jobs: number;
    active_applications: number;
  };
  applications_by_stage: Record<string, number>;
  llm: LLMStatusSummary;
}

export interface DeviceActionResponse {
  action: string;
  result: {
    success?: boolean;
    online?: boolean;
    hostname?: string | null;
    reason?: string;
    message?: string;
    mac?: string;
    broadcast?: string;
    port?: number;
    stdout?: string;
    stderr?: string;
  };
}

export interface TailorPrefillContext {
  jobId?: number | null;
  jobTitle?: string;
  companyName?: string;
  jobDescription?: string;
  jobUrl?: string;
  tailoredResumeId?: number | null;
}
