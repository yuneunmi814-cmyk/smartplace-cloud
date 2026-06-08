const TOKEN_KEY = 'spc_token';
const ROLE_KEY = 'spc_role';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function getRole(): string | null {
  return localStorage.getItem(ROLE_KEY);
}
export function setSession(token: string | null, role?: string): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    if (role) localStorage.setItem(ROLE_KEY, role);
  } else {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
  }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      ...(init.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    // Expired/invalid token on an authenticated request → bounce to login.
    if (res.status === 401 && getToken()) {
      setSession(null);
      location.reload();
      throw new Error('세션이 만료되었습니다. 다시 로그인하세요.');
    }
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `요청 실패: ${res.status}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
  role: string;
  status: string;
}
export interface NaverAccount {
  id: number;
  alias: string;
  status: string;
  createdAt: string;
}
export interface Place {
  id: number;
  accountId: number;
  placeId: string;
  businessName: string;
}
export interface ImageRes {
  id: number;
  originalFilename: string;
  contentType: string;
  sizeBytes: number;
  url: string;
}
export interface TaskItem {
  id: number;
  placeId: number;
  status: string;
  attempts: number;
  errorMessage: string | null;
}
export interface Task {
  id: number;
  imageId: number;
  status: string;
  scheduledAt: string | null;
  createdAt: string;
  finishedAt: string | null;
  items: TaskItem[];
}
export interface UserRes {
  id: number;
  email: string;
  role: string;
  status: string;
}
export interface AuditRow {
  id: number;
  actorUserId: number | null;
  action: string;
  targetType: string;
  targetId: string;
  detail: string | null;
  createdAt: string;
}
export interface Stats {
  totalTasks: number;
  successRate: number;
  pendingTasks: number;
  users: number;
}
export interface LicenseDevice {
  id: number;
  fingerprint: string;
  name: string | null;
  createdAt: string;
  lastSeenAt: string | null;
}
export interface LicenseDetail {
  id: number;
  licenseKey: string;
  plan: string;
  seats: number;
  status: string;
  expiresAt: string;
  devices: LicenseDevice[];
}
export interface LicenseAdmin {
  id: number;
  licenseKey: string;
  ownerEmail: string;
  plan: string;
  seats: number;
  status: string;
  expiresAt: string;
  devicesUsed: number;
}
export interface LicenseCreated {
  id: number;
  licenseKey: string;
  plan: string;
  seats: number;
  status: string;
  expiresAt: string;
  devicesUsed: number;
}

export const api = {
  signup: (email: string, password: string) =>
    req<UserRes>('/api/v1/auth/signup', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    req<TokenPair>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  listAccounts: () => req<NaverAccount[]>('/api/v1/naver-accounts'),
  linkAccount: (payload: { alias: string; loginId?: string; loginPw?: string; token?: string }) =>
    req<NaverAccount>('/api/v1/naver-accounts', { method: 'POST', body: JSON.stringify(payload) }),

  listPlaces: () => req<Place[]>('/api/v1/places'),
  createPlace: (accountId: number, placeId: string, businessName: string) =>
    req<Place>('/api/v1/places', { method: 'POST', body: JSON.stringify({ accountId, placeId, businessName }) }),

  listImages: () => req<ImageRes[]>('/api/v1/images'),
  uploadImage: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return req<ImageRes>('/api/v1/images/upload', { method: 'POST', body: fd });
  },
  uploadImages: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append('files', f));
    return req<ImageRes[]>('/api/v1/images/upload-batch', { method: 'POST', body: fd });
  },

  dispatch: (imageId: number, placeIds: number[], scheduledAt?: string | null) =>
    req<Task>('/api/v1/tasks/dispatch', {
      method: 'POST',
      body: JSON.stringify({ imageId, placeIds, scheduledAt: scheduledAt ?? null }),
    }),
  listTasks: () => req<Task[]>('/api/v1/tasks'),
  cancelTask: (id: number) => req<Task>(`/api/v1/tasks/${id}/cancel`, { method: 'PATCH' }),

  listUsers: () => req<UserRes[]>('/api/v1/admin/users'),
  approveUser: (id: number) => req<{ ok: boolean }>(`/api/v1/admin/users/${id}/approve`, { method: 'POST' }),
  setRole: (id: number, role: string) =>
    req<{ ok: boolean }>(`/api/v1/admin/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }),
  audit: () => req<AuditRow[]>('/api/v1/admin/audit'),
  stats: () => req<Stats>('/api/v1/admin/stats'),

  myLicenses: () => req<LicenseDetail[]>('/api/v1/license/mine'),
  deactivateDevice: (licenseId: number, deviceId: number) =>
    req<void>(`/api/v1/license/${licenseId}/devices/${deviceId}`, { method: 'DELETE' }),
  listLicenses: () => req<LicenseAdmin[]>('/api/v1/license'),
  createLicense: (payload: { email: string; plan: string; seats: number; days?: number }) =>
    req<LicenseCreated>('/api/v1/license', { method: 'POST', body: JSON.stringify(payload) }),
  revokeLicense: (id: number) =>
    req<LicenseAdmin>(`/api/v1/license/${id}/revoke`, { method: 'POST' }),
};
