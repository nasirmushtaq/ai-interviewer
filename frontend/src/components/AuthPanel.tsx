import { useState } from "react";
import { useUser } from "../user";

/**
 * Login / Register panel with a guest fallback. Shown when no user is present.
 */
export default function AuthPanel() {
  const { register, login, setGuest } = useUser();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [guestName, setGuestName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showGuest, setShowGuest] = useState(false);

  const submit = async () => {
    setError("");
    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }
    if (mode === "register" && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "register") {
        await register(email.trim(), password, displayName.trim() || undefined);
      } else {
        await login(email.trim(), password);
      }
    } catch (e: any) {
      setError(e.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-14 text-center">
      <h1 className="text-4xl font-bold">Ace your next interview.</h1>
      <p className="mt-3 text-gray-400">
        Practice real mock interviews with an AI that watches your code and
        diagrams, grades you, and remembers your progress.
      </p>

      <div className="mt-8 rounded-2xl bg-white/5 border border-white/10 p-6 text-left">
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setMode("login")}
            className={`flex-1 py-2 rounded-lg text-sm font-medium ${
              mode === "login" ? "bg-brand-600" : "bg-white/10 hover:bg-white/20"
            }`}
          >
            Log in
          </button>
          <button
            onClick={() => setMode("register")}
            className={`flex-1 py-2 rounded-lg text-sm font-medium ${
              mode === "register" ? "bg-brand-600" : "bg-white/10 hover:bg-white/20"
            }`}
          >
            Sign up
          </button>
        </div>

        <div className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className="w-full px-4 py-2.5 rounded-xl bg-white/10 border border-white/10 outline-none focus:border-brand-500"
          />
          {mode === "register" && (
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Display name (optional)"
              className="w-full px-4 py-2.5 rounded-xl bg-white/10 border border-white/10 outline-none focus:border-brand-500"
            />
          )}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder={
              mode === "register" ? "Password (min 8 chars)" : "Password"
            }
            className="w-full px-4 py-2.5 rounded-xl bg-white/10 border border-white/10 outline-none focus:border-brand-500"
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            onClick={submit}
            disabled={busy}
            className="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 font-medium disabled:opacity-50"
          >
            {busy
              ? "Please wait…"
              : mode === "register"
              ? "Create account"
              : "Log in"}
          </button>
        </div>

        <div className="mt-4 text-center">
          {!showGuest ? (
            <button
              onClick={() => setShowGuest(true)}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              or continue as a guest
            </button>
          ) : (
            <div className="flex gap-2">
              <input
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && setGuest(guestName)}
                placeholder="Guest username"
                className="flex-1 px-3 py-2 rounded-lg bg-white/10 border border-white/10 outline-none text-sm"
              />
              <button
                onClick={() => setGuest(guestName)}
                className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm"
              >
                Continue
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
