import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UserProfile {
  id: string;
  github_id: number;
  username: string;
  email: string | null;
  avatar_url: string | null;
  github_username: string | null;
  github_avatar_url: string | null;
  created_at: string;
  updated_at: string;
}

interface AuthState {
  /** The JWT stored in localStorage */
  token: string | null;
  /** The currently authenticated user (null while loading or logged out) */
  user: UserProfile | null;
  /** True while the initial auth check is in progress */
  isLoading: boolean;
  /** True once a valid user has been loaded */
  isAuthenticated: boolean;
  /** Redirect the browser to the backend GitHub login endpoint */
  login: () => void;
  /** Clear local auth state and redirect to login */
  logout: () => void;
  /** Store a JWT and immediately load the user profile */
  setToken: (token: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = 'http://localhost:8000/api/v1';
const TOKEN_KEY = 'reflexion_jwt';

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // -----------------------------------------------------------------------
  // Fetch the /auth/me profile using the current JWT
  // -----------------------------------------------------------------------
  const loadUser = useCallback(async (jwt: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      if (!res.ok) {
        // Token is invalid / expired – clean up
        localStorage.removeItem(TOKEN_KEY);
        setTokenState(null);
        setUser(null);
        return;
      }
      const profile: UserProfile = await res.json();
      setUser(profile);
    } catch {
      // Network error – leave state as-is so a retry can happen
      localStorage.removeItem(TOKEN_KEY);
      setTokenState(null);
      setUser(null);
    }
  }, []);

  // -----------------------------------------------------------------------
  // On mount, check for an existing token and load the user
  // -----------------------------------------------------------------------
  useEffect(() => {
    const init = async () => {
      const stored = localStorage.getItem(TOKEN_KEY);
      if (stored) {
        await loadUser(stored);
      }
      setIsLoading(false);
    };
    init();
  }, [loadUser]);

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  const login = useCallback(() => {
    window.location.href = `${API_BASE}/auth/github/login`;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setTokenState(null);
    setUser(null);
  }, []);

  const setToken = useCallback(
    async (jwt: string) => {
      localStorage.setItem(TOKEN_KEY, jwt);
      setTokenState(jwt);
      await loadUser(jwt);
    },
    [loadUser],
  );

  const value: AuthState = {
    token,
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    setToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}
