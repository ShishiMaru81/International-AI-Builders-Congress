export const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
export const TOKEN_KEY = 'agrosphere-token';

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function getSessionToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setSessionToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
  window.dispatchEvent(new Event('agrosphere-session'));
}

export function clearSessionToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('agrosphere-session'));
  }
}

export async function request<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getSessionToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(API + path, {...options, headers});
  } catch {
    throw new ApiError('Network error. Check your connection and retry.', 0, 'NETWORK');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({message: 'Connection failed'}));
    throw new ApiError(
      body.message || JSON.stringify(body.detail) || `Request failed (${response.status})`,
      response.status,
      body.code,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function download(path: string, name: string) {
  const response = await fetch(API + path, {
    headers: {Authorization: `Bearer ${getSessionToken()}`},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({message: 'Export failed'}));
    throw new ApiError(body.message || 'Export failed', response.status, body.code);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function formatTime(value: string, locale: 'en' | 'bn' = 'en') {
  return (
    new Intl.DateTimeFormat(locale === 'bn' ? 'bn-BD' : 'en-BD', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'Asia/Dhaka',
    }).format(new Date(value)) + ' BST'
  );
}

export function formatDateOnly(value: string, locale: 'en' | 'bn' = 'en') {
  // Preserve date-only observation dates without inventing a time-of-day
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split('-').map(Number);
    return new Intl.DateTimeFormat(locale === 'bn' ? 'bn-BD' : 'en-BD', {
      dateStyle: 'medium',
      timeZone: 'UTC',
    }).format(new Date(Date.UTC(y, m - 1, d)));
  }
  return formatTime(value, locale);
}

export function netReturn(price: number, quantity: number, loss: number, costs: number) {
  return quantity * (1 - loss) * price - costs;
}

export function contrastRatio(foreground: string, background: string): number {
  const toRgb = (hex: string) => {
    const clean = hex.replace('#', '');
    const full = clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean;
    return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
  };
  const channel = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const luminance = (hex: string) => {
    const [r, g, b] = toRgb(hex).map(channel);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const l1 = luminance(foreground);
  const l2 = luminance(background);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}
