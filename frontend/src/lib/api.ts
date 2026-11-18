import type {
  ApplicationInterviewPrepResponse,
  ApplicationStage,
  AuthTokenResponse,
  BaseResume,
  CandidateLanguage,
  CandidateProfile,
  ChatMessage,
  ChatThread,
  DeviceActionResponse,
  JobApplication,
  JobListParams,
  JobMatchItem,
  JobMatchStatus,
  JobPreferences,
  JobSearchPayload,
  JobSearchResponse,
  RequestOtpResponse,
  SendMessageResponse,
  SetPasswordPayload,
  SystemOverview,
  TailoredResume,
  UserSummary,
} from '../types/api';

const TOKEN_STORAGE_KEY = 'c3po_access_token';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

type UnauthorizedHandler = () => void;
let onUnauthorizedCallback: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorizedCallback = handler;
}

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Storage indisponível (modo privado restrito)
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((item: { msg?: string; loc?: Array<string | number> }) =>
          item?.msg ? `${item.loc?.slice(1).join('.') || 'campo'}: ${item.msg}` : JSON.stringify(item),
        )
        .join(' | ');
    }
    if (typeof data?.message === 'string') {
      return data.message;
    }
  } catch {
    // Resposta não-JSON
  }
  return `Erro na requisição (HTTP ${res.status}).`;
}

async function request<T>(path: string, init: RequestInit = {}, authRequired = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const token = getStoredToken();
  if (authRequired && token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const res = await fetch(path, {
    ...init,
    headers,
  });

  if (!res.ok) {
    const detail = await parseErrorDetail(res);
    if (res.status === 401 && authRequired && onUnauthorizedCallback) {
      onUnauthorizedCallback();
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const api = {
  auth: {
    requestOtp: (phone_or_jid: string) =>
      request<RequestOtpResponse>(
        '/api/v1/auth/request-otp',
        { method: 'POST', body: JSON.stringify({ phone_or_jid }) },
        false,
      ),
    verifyOtp: (phone_or_jid: string, code: string) =>
      request<AuthTokenResponse>(
        '/api/v1/auth/verify-otp',
        { method: 'POST', body: JSON.stringify({ phone_or_jid, code }) },
        false,
      ),
    loginPassword: (identifier: string, password: string) =>
      request<AuthTokenResponse>(
        '/api/v1/auth/login-password',
        { method: 'POST', body: JSON.stringify({ identifier, password }) },
        false,
      ),
    setPassword: (password: string, current_password?: string) => {
      const payload: SetPasswordPayload = { password };
      if (current_password && current_password.trim()) {
        payload.current_password = current_password;
      }
      return request<{ status: string; message: string; user: UserSummary }>(
        '/api/v1/auth/set-password',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      );
    },
    me: () => request<{ user: UserSummary }>('/api/v1/auth/me'),
  },

  profile: {
    get: () => request<CandidateProfile>('/api/v1/profile'),
    update: (payload: {
      headline?: string;
      summary?: string;
      years_experience?: number;
      location?: string;
      linkedin_url?: string;
      github_url?: string;
      portfolio_url?: string;
      languages?: CandidateLanguage[];
      skills?: Array<{
        name: string;
        category?: string;
        proficiency?: string;
        years_used?: number | null;
        is_core?: boolean;
      }>;
      preferences?: Partial<JobPreferences>;
    }) =>
      request<CandidateProfile>('/api/v1/profile', {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    updatePreferences: (preferences: Partial<JobPreferences>) =>
      request<CandidateProfile>('/api/v1/profile/preferences', {
        method: 'PUT',
        body: JSON.stringify(preferences),
      }),
    addSkills: (skills: string[], is_core = false) =>
      request<CandidateProfile>('/api/v1/profile/skills', {
        method: 'POST',
        body: JSON.stringify({ skills, is_core }),
      }),
    deleteSkill: (skillId: number) =>
      request<CandidateProfile>(`/api/v1/profile/skills/${skillId}`, {
        method: 'DELETE',
      }),
  },

  jobs: {
    list: (params?: JobListParams) => {
      const sp = new URLSearchParams();
      if (params?.status) sp.set('status', params.status);
      if (typeof params?.min_score === 'number' && params.min_score > 0) {
        sp.set('min_score', String(params.min_score));
      }
      if (params?.source) sp.set('source', params.source);
      if (params?.language) sp.set('language', params.language);
      if (params?.seniority) sp.set('seniority', params.seniority);
      if (params?.location?.trim()) sp.set('location', params.location.trim());
      if (params?.work_model) sp.set('work_model', params.work_model);
      if (params?.search?.trim()) sp.set('search', params.search.trim());
      if (params?.limit) sp.set('limit', String(params.limit));
      if (params?.offset) sp.set('offset', String(params.offset));
      const qs = sp.toString();
      return request<{ total: number; items: JobMatchItem[] }>(`/api/v1/jobs${qs ? `?${qs}` : ''}`);
    },
    search: (body: JobSearchPayload) =>
      request<JobSearchResponse>('/api/v1/jobs/search', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    ingest: (body: {
      url?: string;
      description_raw?: string;
      title?: string;
      company_name?: string;
      location?: string;
      work_model?: string;
      contract_type?: string;
    }) =>
      request<JobMatchItem>('/api/v1/jobs/ingest', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    updateMatchStatus: (matchId: number, status: JobMatchStatus) =>
      request<JobMatchItem>(`/api/v1/jobs/matches/${matchId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
  },

  resumes: {
    list: () => request<{ items: BaseResume[] }>('/api/v1/resumes'),
    upload: (formData: FormData) =>
      request<BaseResume>('/api/v1/resumes/upload', {
        method: 'POST',
        body: formData,
      }),
    setDefault: (resumeId: number) =>
      request<BaseResume>(`/api/v1/resumes/${resumeId}/default`, {
        method: 'PATCH',
      }),
    delete: (resumeId: number) =>
      request<{ status: string; id: number }>(`/api/v1/resumes/${resumeId}`, {
        method: 'DELETE',
      }),
    tailor: (body: {
      base_resume_id?: number | null;
      resume_text?: string | null;
      job_id?: number | null;
      job_url?: string | null;
      job_description?: string | null;
      job_title?: string | null;
      company_name?: string | null;
      target_language?: string;
    }) =>
      request<TailoredResume>('/api/v1/resumes/tailor', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    listTailored: () => request<{ items: TailoredResume[] }>('/api/v1/resumes/tailored'),
    getTailored: (tailoredId: number) =>
      request<TailoredResume>(`/api/v1/resumes/tailored/${tailoredId}`),
    updateTailored: (
      tailoredId: number,
      body: {
        tailored_markdown?: string;
        tailored_data?: Record<string, unknown>;
        target_language?: string;
        cover_letter?: string;
      },
    ) =>
      request<TailoredResume>(`/api/v1/resumes/tailored/${tailoredId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    deleteTailored: (tailoredId: number) =>
      request<{ status: string; id: number }>(`/api/v1/resumes/tailored/${tailoredId}`, {
        method: 'DELETE',
      }),
    saveTailoredAsBase: (
      tailoredId: number,
      payload?: { title?: string; is_default?: boolean; sync_profile?: boolean },
    ) =>
      request<BaseResume>(`/api/v1/resumes/tailored/${tailoredId}/save-as-base`, {
        method: 'POST',
        body: JSON.stringify(payload || {}),
      }),
    downloadTailored: async (tailoredId: number, format: 'pdf' | 'docx' | 'md'): Promise<void> => {
      const token = getStoredToken();
      const headers = new Headers();
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      const res = await fetch(`/api/v1/resumes/tailored/${tailoredId}/download?format=${format}`, {
        method: 'GET',
        headers,
      });
      if (!res.ok) {
        const detail = await parseErrorDetail(res);
        if (res.status === 401 && onUnauthorizedCallback) {
          onUnauthorizedCallback();
        }
        throw new ApiError(res.status, detail);
      }

      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || `cv_otimizado_${tailoredId}.${format}`;

      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    },
  },

  applications: {
    list: (stage?: ApplicationStage) => {
      const qs = stage ? `?stage=${encodeURIComponent(stage)}` : '';
      return request<{ items: JobApplication[] }>(`/api/v1/applications${qs}`);
    },
    create: (body: {
      company_name: string;
      role_title: string;
      job_id?: number | null;
      tailored_resume_id?: number | null;
      job_url?: string | null;
      stage?: ApplicationStage;
      notes?: string | null;
    }) =>
      request<JobApplication>('/api/v1/applications', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    update: (
      applicationId: number,
      body: {
        company_name?: string;
        role_title?: string;
        job_url?: string;
        tailored_resume_id?: number | null;
        stage?: ApplicationStage;
        notes?: string;
        follow_up_at?: string | null;
      },
    ) =>
      request<JobApplication>(`/api/v1/applications/${applicationId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    delete: (applicationId: number) =>
      request<{ status: string; id: number }>(`/api/v1/applications/${applicationId}`, {
        method: 'DELETE',
      }),
    generateInterviewPrep: (applicationId: number, target_language = 'auto') =>
      request<ApplicationInterviewPrepResponse>(
        `/api/v1/applications/${applicationId}/interview-prep`,
        {
          method: 'POST',
          body: JSON.stringify({ target_language }),
        },
      ),
  },

  chat: {
    listThreads: () => request<{ items: ChatThread[] }>('/api/v1/chat/threads'),
    createThread: (title = 'Nova conversa', context_type = 'career') =>
      request<ChatThread>('/api/v1/chat/threads', {
        method: 'POST',
        body: JSON.stringify({ title, context_type }),
      }),
    listMessages: (threadId: number) =>
      request<{ thread: ChatThread; items: ChatMessage[] }>(
        `/api/v1/chat/threads/${threadId}/messages`,
      ),
    sendMessageHttp: (threadId: number, content: string) =>
      request<SendMessageResponse>(`/api/v1/chat/threads/${threadId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      }),
    deleteThread: (threadId: number) =>
      request<{ status: string; id: number }>(`/api/v1/chat/threads/${threadId}`, {
        method: 'DELETE',
      }),
  },

  system: {
    overview: () => request<SystemOverview>('/api/v1/system/overview'),
    controlDevice: (action: 'status' | 'wake' | 'restart' | 'shutdown') =>
      request<DeviceActionResponse>(`/api/v1/system/devices/${action}`, {
        method: 'POST',
      }),
  },
};
