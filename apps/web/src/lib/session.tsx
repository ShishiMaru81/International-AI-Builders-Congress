'use client';
import {createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore, useRef} from 'react';
import {QueryClient, QueryClientProvider, useQuery, useQueryClient} from '@tanstack/react-query';
import {request, ApiError, clearSessionToken, getSessionToken, setSessionToken} from '@/lib/api';
import type {Plot, Preferences, User} from '@/lib/types';

export type SessionState = 'checking' | 'authenticated' | 'anonymous' | 'service_error';

type SessionContextValue = {
  state: SessionState;
  user: User | null;
  serviceError: string;
  selectedPlotId: string;
  setSelectedPlotId: (id: string) => void;
  plot: Plot | undefined;
  plots: Plot[];
  refreshSession: () => Promise<void>;
  signOut: () => Promise<void>;
  beginDemo: (name: string) => Promise<void>;
  dark: boolean;
  setDarkLocal: (value: boolean) => void;
  applyPreferences: (prefs: Preferences) => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);
const PLOT_KEY = 'agrosphere-selected-plot';

function subscribeToken(callback: () => void) {
  window.addEventListener('storage', callback);
  window.addEventListener('agrosphere-session', callback);
  return () => {
    window.removeEventListener('storage', callback);
    window.removeEventListener('agrosphere-session', callback);
  };
}

function readTokenSnapshot() {
  return getSessionToken() || '';
}

export function SessionProvider({
  locale,
  children,
}: {
  locale: 'en' | 'bn';
  children: React.ReactNode;
}) {
  const qc = useQueryClient();
  const token = useSyncExternalStore(subscribeToken, readTokenSnapshot, () => '');
  const [state, setState] = useState<SessionState>(token ? 'checking' : 'anonymous');
  const [user, setUser] = useState<User | null>(null);
  const [serviceError, setServiceError] = useState('');
  const [selectedPlotId, setSelectedPlotIdState] = useState('');
  const [dark, setDark] = useState(false);
  const validatedToken = useRef('');
  const refreshEpoch = useRef(0);

  const applyPreferences = useCallback((prefs: Preferences) => {
    setDark(prefs.theme === 'dark');
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('dark', prefs.theme === 'dark');
      document.documentElement.lang = prefs.language === 'bn' ? 'bn' : 'en';
    }
    if (prefs.selected_plot_id) {
      setSelectedPlotIdState(prefs.selected_plot_id);
      try {
        localStorage.setItem(PLOT_KEY, prefs.selected_plot_id);
      } catch {
        /* ignore quota */
      }
    }
  }, []);

  const clearLocalSession = useCallback(() => {
    refreshEpoch.current += 1;
    validatedToken.current = '';
    clearSessionToken();
    setUser(null);
    setSelectedPlotIdState('');
    try {
      localStorage.removeItem(PLOT_KEY);
    } catch {
      /* ignore */
    }
    qc.clear();
    setState('anonymous');
  }, [qc]);

  const refreshSession = useCallback(async () => {
    const current = getSessionToken();
    if (!current) {
      if (validatedToken.current) clearLocalSession();
      else { setUser(null); setState('anonymous'); }
      return;
    }
    validatedToken.current = current;
    const epoch = ++refreshEpoch.current;
    setState('checking');
    setServiceError('');
    try {
      const me = await request<User>('/me');
      if (epoch !== refreshEpoch.current || getSessionToken() !== current) return;
      setUser(me);
      applyPreferences(me.preferences);
      setState('authenticated');
    } catch (error) {
      if (epoch !== refreshEpoch.current || getSessionToken() !== current) return;
      if (error instanceof ApiError && error.status === 401) {
        clearLocalSession();
        return;
      }
      setServiceError((error as Error).message || 'Service unavailable');
      setState('service_error');
    }
  }, [applyPreferences, clearLocalSession]);

  useEffect(() => {
    // FE-01: validate token via /me whenever local session token presence changes.
    void refreshSession();
  }, [token, refreshSession]);

  const plotsQuery = useQuery({
    queryKey: ['plots'],
    queryFn: () => request<Plot[]>('/plots'),
    enabled: state === 'authenticated',
    retry: (count, error) => {
      if (error instanceof ApiError && error.status === 401) return false;
      return count < 1;
    },
  });

  useEffect(() => {
    if (plotsQuery.error instanceof ApiError && plotsQuery.error.status === 401) {
      clearLocalSession();
    }
  }, [plotsQuery.error, clearLocalSession]);

  useEffect(() => {
    if (state !== 'authenticated') return;
    const nextPlots = plotsQuery.data || [];
    if (!nextPlots.length) {
      setSelectedPlotIdState('');
      return;
    }
    let stored = '';
    try {
      stored = localStorage.getItem(PLOT_KEY) || '';
    } catch {
      stored = '';
    }
    const preferred = user?.preferences?.selected_plot_id || '';
    const candidate = selectedPlotId || preferred || stored;
    const valid = nextPlots.some((p) => p.id === candidate)
      ? candidate
      : nextPlots[nextPlots.length - 1]?.id || nextPlots[0].id;
    if (valid !== selectedPlotId) {
      setSelectedPlotIdState(valid);
    }
    try {
      localStorage.setItem(PLOT_KEY, valid);
    } catch {
      /* ignore */
    }
  }, [state, plotsQuery.data, selectedPlotId, user]);

  const setSelectedPlotId = useCallback(
    (id: string) => {
      setSelectedPlotIdState(id);
      try {
        localStorage.setItem(PLOT_KEY, id);
      } catch {
        /* ignore */
      }
      if (state === 'authenticated') {
        void request('/me', {
          method: 'PATCH',
          body: JSON.stringify({selected_plot_id: id}),
        })
          .then((prefs) => {
            setUser((prev) => (prev ? {...prev, preferences: prefs as Preferences} : prev));
          })
          .catch(() => {
            /* keep local selection even if preference sync fails */
          });
      }
    },
    [state],
  );

  const signOut = useCallback(async () => {
    try {
      await request('/auth/logout', {method: 'POST'});
    } catch {
      // Local sign-out must complete even when remote revocation returns 401 (FE-01)
    } finally {
      clearLocalSession();
    }
  }, [clearLocalSession]);

  const beginDemo = useCallback(
    async (name: string) => {
      const result = await request<{token: string}>('/auth/demo', {
        method: 'POST',
        body: JSON.stringify({name}),
      });
      setSessionToken(result.token);
      window.dispatchEvent(new Event('agrosphere-session'));
      await refreshSession();
    },
    [refreshSession],
  );

  const plots = useMemo(() => plotsQuery.data || [], [plotsQuery.data]);
  const plot = plots.find((p) => p.id === selectedPlotId) || plots[0];

  const value = useMemo<SessionContextValue>(
    () => ({
      state,
      user,
      serviceError,
      selectedPlotId: plot?.id || selectedPlotId,
      setSelectedPlotId,
      plot,
      plots,
      refreshSession,
      signOut,
      beginDemo,
      dark,
      setDarkLocal: setDark,
      applyPreferences,
    }),
    [
      state,
      user,
      serviceError,
      plot,
      selectedPlotId,
      setSelectedPlotId,
      plots,
      refreshSession,
      signOut,
      beginDemo,
      dark,
      applyPreferences,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}

export function AppProviders({
  locale,
  children,
}: {
  locale: 'en' | 'bn';
  children: React.ReactNode;
}) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: (count, error) => {
              if (error instanceof ApiError && (error.status === 401 || error.status === 404)) return false;
              return count < 1;
            },
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <SessionProvider locale={locale}>{children}</SessionProvider>
    </QueryClientProvider>
  );
}
