import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { api, setAuthToken } from "./api";

export type AuthUser = {
  username: string;
  email?: string | null;
  authed: boolean; // true = real account, false = guest
};

type UserCtx = {
  username: string;
  email: string | null;
  authed: boolean;
  ready: boolean;
  // real auth
  register: (email: string, password: string, username?: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  // guest fallback (username only)
  setGuest: (username: string) => void;
  logout: () => void;
};

const Ctx = createContext<UserCtx>({
  username: "",
  email: null,
  authed: false,
  ready: false,
  register: async () => {},
  login: async () => {},
  setGuest: () => {},
  logout: () => {},
});

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  // On load: restore a real session from a saved token, else a saved guest name.
  useEffect(() => {
    const token = localStorage.getItem("lc_token");
    if (token) {
      setAuthToken(token);
      api
        .me()
        .then((u) =>
          setUser({ username: u.username, email: u.email, authed: true })
        )
        .catch(() => {
          // token invalid/expired
          setAuthToken(null);
          const guest = localStorage.getItem("lc_user");
          if (guest) setUser({ username: guest, authed: false });
        })
        .finally(() => setReady(true));
    } else {
      const guest = localStorage.getItem("lc_user");
      if (guest) setUser({ username: guest, authed: false });
      setReady(true);
    }
  }, []);

  const applyAuth = (res: any) => {
    setAuthToken(res.token);
    localStorage.removeItem("lc_user");
    setUser({ username: res.user.username, email: res.user.email, authed: true });
  };

  const register = async (email: string, password: string, username?: string) => {
    const res = await api.register(email, password, username);
    applyAuth(res);
  };

  const login = async (email: string, password: string) => {
    const res = await api.authLogin(email, password);
    applyAuth(res);
  };

  const setGuest = (username: string) => {
    const u = username.trim().toLowerCase();
    if (!u) return;
    localStorage.setItem("lc_user", u);
    setUser({ username: u, authed: false });
    // Best-effort: ensure a guest user row exists server-side.
    api.login(u).catch(() => {});
  };

  const logout = () => {
    setAuthToken(null);
    localStorage.removeItem("lc_user");
    setUser(null);
  };

  return (
    <Ctx.Provider
      value={{
        username: user?.username || "",
        email: user?.email ?? null,
        authed: !!user?.authed,
        ready,
        register,
        login,
        setGuest,
        logout,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export const useUser = () => useContext(Ctx);
