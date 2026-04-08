const API_BASE = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8080';
const WS_BASE  = API_BASE.replace(/^http/, 'ws');

export const API_URLS = {
  // User Service
  LOGIN:        `${API_BASE}/api/users/auth/login`,
  REGISTER:     `${API_BASE}/api/users/auth/register`,
  VERIFY_EMAIL: `${API_BASE}/api/users/auth/verify-email`,
  ME:           `${API_BASE}/api/users/me`,
  USERS:        `${API_BASE}/api/users/`,
  USER_ROLE:    (id: number) => `${API_BASE}/api/users/${id}/role`,

  // Device Service
  DEVICES:  `${API_BASE}/api/devices/`,
  DEVICE:   (id: number) => `${API_BASE}/api/devices/${id}`,

  // Alert Service
  ALERTS:   `${API_BASE}/api/alerts/`,
  ALERT:    (id: number) => `${API_BASE}/api/alerts/${id}`,

  // WebSockets
  EVENTS_WS:    `${WS_BASE}/ws/`,
};

// ----------------------------------------------------------------
// Auth helpers
// ----------------------------------------------------------------
export function getToken(): string | null {
  const match = document.cookie.match(/(?:^|; )access_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function setToken(token: string): void {
  const expires = new Date(Date.now() + 24 * 60 * 60 * 1000).toUTCString();
  document.cookie = `access_token=${encodeURIComponent(token)}; expires=${expires}; path=/; SameSite=Lax`;
}

export function clearToken(): void {
  document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
}

// ----------------------------------------------------------------
// Generic fetch wrapper
// ----------------------------------------------------------------
async function apiFetch<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API Error');
  }
  return res.json() as Promise<T>;
}

// ----------------------------------------------------------------
// API methods
// ----------------------------------------------------------------

export interface UserInfo {
  id: number;
  username: string;
  email: string;
  role: string;
  is_verified?: boolean;
  created_at?: string;
}

export const authApi = {
  login: (email: string, password: string) => {
    return fetch(API_URLS.LOGIN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }).then(async r => {
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Login failed');
      return data as { access_token: string; token_type: string };
    });
  },
  register: (email: string, password: string, username?: string) => {
    return fetch(API_URLS.REGISTER, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, username }),
    }).then(async r => {
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Registration failed');
      return data as { id: number; email: string; message: string };
    });
  },
  verifyEmail: (token: string) =>
    apiFetch<{ status: string; message: string }>(`${API_URLS.VERIFY_EMAIL}?token=${token}`),
  me: () => apiFetch<UserInfo>(API_URLS.ME),
};

// Users management (admin)
export const userApi = {
  list: () => apiFetch<UserInfo[]>(API_URLS.USERS),
  updateRole: (id: number, role: string) =>
    apiFetch<{ id: number; role: string }>(API_URLS.USER_ROLE(id), {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),
};

// Devices
export interface Device {
  id: number;
  name: string;
  location?: string;
  notes?: string;
  status: 'online' | 'offline' | 'warning';
  owner_user_id?: number;
  provisioning_status?: 'pending' | 'active' | 'expired';
  onboarding_expires_at?: string | null;
}

export interface DeviceProvisioning {
  id: number;
  name: string;
  location?: string | null;
  notes?: string | null;
  owner_user_id?: number;
  is_online: boolean;
  provisioning_status: 'pending' | 'active' | 'expired';
  onboarding_token: string;
  onboarding_expires_at: string;
}


export const deviceApi = {
  list: () =>
    apiFetch<Array<Record<string, unknown>>>(API_URLS.DEVICES).then((rows) =>
      rows.map((r) => {
        const is_online = Boolean(r.is_online);
        return {
          ...(r as any),
          status: (r.status as Device['status'] | undefined) ?? (is_online ? 'online' : 'offline'),
        } as Device;
      })
    ),
  get: (id: number) =>
    apiFetch<Record<string, unknown>>(API_URLS.DEVICE(id)).then((r) => {
      const is_online = Boolean(r.is_online);
      return {
        ...(r as any),
        status: (r.status as Device['status'] | undefined) ?? (is_online ? 'online' : 'offline'),
      } as Device;
    }),
  create: (data: { name: string; location?: string; notes?: string }) =>
    apiFetch<DeviceProvisioning>(API_URLS.DEVICES, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<Device>) =>
    apiFetch<Record<string, unknown>>(API_URLS.DEVICE(id), { method: 'PUT', body: JSON.stringify(data) }).then((r) => {
      const is_online = Boolean(r.is_online);
      return {
        ...(r as any),
        status: (r.status as Device['status'] | undefined) ?? (is_online ? 'online' : 'offline'),
      } as Device;
    }),
  delete: (id: number) =>
    apiFetch<void>(API_URLS.DEVICE(id), { method: 'DELETE' }),
};

export interface Alert {
  id: number;
  device_id: number;
  device_name?: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timestamp: string;
  resolved: boolean;
}

interface BackendAlert {
  id: number;
  device_id: number;
  confidence: number;
  label: string;
  occurred_at: string;
  snapshot_url: string;
  acknowledged: boolean;
}

function mapAlert(a: BackendAlert): Alert {
  return {
    id: a.id,
    device_id: a.device_id,
    type: a.label?.toLowerCase() || 'unknown',
    severity: (a.confidence > 0.8 ? 'critical' : (a.confidence > 0.5 ? 'high' : 'medium')) as Alert['severity'],
    message: `Detected ${a.label} with ${(a.confidence * 100).toFixed(0)}% confidence`,
    timestamp: a.occurred_at,
    resolved: a.acknowledged,
  };
}

export const alertApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return apiFetch<BackendAlert[]>(`${API_URLS.ALERTS}${qs}`).then(alerts =>
      alerts.map(mapAlert)
    );
  },
  updateStatus: (id: number, acknowledged: boolean) =>
    apiFetch<BackendAlert>(API_URLS.ALERT(id), { 
      method: 'PATCH', 
      body: JSON.stringify({ acknowledged }) 
    }).then(mapAlert),
  acknowledgeAll: () =>
    apiFetch<{ success: boolean }>(`${API_URLS.ALERTS}acknowledge-all`, { method: 'POST' }),
  delete: (id: number) =>
    apiFetch<{ deleted: number }>(API_URLS.ALERT(id), { method: 'DELETE' }),
};
