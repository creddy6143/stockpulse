import { useState } from "react";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  sendPasswordResetEmail,
} from "firebase/auth";
import { auth, googleProvider } from "../firebase";

const BASE = process.env.REACT_APP_API_URL || "";

export default function AuthScreen() {
  const [view, setView] = useState("login"); // "login" | "signup" | "forgot"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  const clearMessages = () => { setError(""); setInfo(""); };

  async function callAuthMe(user) {
    try {
      const token = await user.getIdToken();
      await fetch(`${BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (_) {}
  }

  async function handleLogin(e) {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    try {
      const cred = await signInWithEmailAndPassword(auth, email, password);
      await callAuthMe(cred.user);
    } catch (err) {
      setError(friendlyError(err.code));
    } finally {
      setLoading(false);
    }
  }

  async function handleSignup(e) {
    e.preventDefault();
    clearMessages();
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (password.length < 6) { setError("Password must be at least 6 characters."); return; }
    setLoading(true);
    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password);
      await callAuthMe(cred.user);
    } catch (err) {
      setError(friendlyError(err.code));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogle() {
    clearMessages();
    setLoading(true);
    try {
      const cred = await signInWithPopup(auth, googleProvider);
      await callAuthMe(cred.user);
    } catch (err) {
      if (err.code !== "auth/popup-closed-by-user") {
        setError(friendlyError(err.code));
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleForgot(e) {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    try {
      await sendPasswordResetEmail(auth, email);
      setInfo("Reset link sent — check your email.");
    } catch (err) {
      setError(friendlyError(err.code));
    } finally {
      setLoading(false);
    }
  }

  function friendlyError(code) {
    const map = {
      "auth/invalid-email":          "That doesn't look like a valid email address.",
      "auth/user-not-found":         "No account found with that email.",
      "auth/wrong-password":         "Incorrect password. Try again or reset it.",
      "auth/email-already-in-use":   "An account with that email already exists.",
      "auth/weak-password":          "Choose a stronger password (6+ characters).",
      "auth/too-many-requests":      "Too many attempts. Wait a moment then try again.",
      "auth/network-request-failed": "Network error. Check your connection.",
      "auth/invalid-credential":     "Incorrect email or password.",
    };
    return map[code] || "Something went wrong. Please try again.";
  }

  const switchView = (v) => { setView(v); clearMessages(); setPassword(""); setConfirm(""); };

  return (
    <div style={S.wrap}>
      <style>{CSS}</style>

      {/* Logo */}
      <div style={S.logo}>
        <div style={S.logoIcon}>⚡</div>
        <div>
          <div style={S.logoName}>StockPulse</div>
          <div style={S.logoSub}>AI INTELLIGENCE · 🇺🇸 🇪🇺 🇮🇳</div>
        </div>
      </div>

      {/* Card */}
      <div style={S.card}>

        {/* View: Login */}
        {view === "login" && (
          <>
            <h2 style={S.title}>Sign In</h2>
            <p style={S.sub}>Your portfolio and watchlist are waiting.</p>

            <form onSubmit={handleLogin}>
              <Input label="Email" type="email" value={email} onChange={setEmail} autoFocus />
              <Input label="Password" type="password" value={password} onChange={setPassword} />
              {error && <p style={S.err}>{error}</p>}
              <button className="auth-btn-primary" type="submit" disabled={loading}>
                {loading ? "Signing in…" : "Sign In"}
              </button>
            </form>

            <Divider />
            <button className="auth-btn-google" type="button" onClick={handleGoogle} disabled={loading}>
              <svg width="18" height="18" viewBox="0 0 18 18" style={{flexShrink:0}}>
                <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
                <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"/>
                <path fill="#FBBC05" d="M3.964 10.706A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.038l3.007-2.332z"/>
                <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z"/>
              </svg>
              Sign in with Google
            </button>

            <div style={S.links}>
              <button className="auth-link" onClick={() => switchView("forgot")}>Forgot password?</button>
              <span style={{color:"var(--t3)"}}>·</span>
              <button className="auth-link" onClick={() => switchView("signup")}>Create account</button>
            </div>
          </>
        )}

        {/* View: Sign Up */}
        {view === "signup" && (
          <>
            <h2 style={S.title}>Create Account</h2>
            <p style={S.sub}>Start tracking your stocks with AI intelligence.</p>

            <form onSubmit={handleSignup}>
              <Input label="Email" type="email" value={email} onChange={setEmail} autoFocus />
              <Input label="Password" type="password" value={password} onChange={setPassword} />
              <Input label="Confirm Password" type="password" value={confirm} onChange={setConfirm} />
              {error && <p style={S.err}>{error}</p>}
              <button className="auth-btn-primary" type="submit" disabled={loading}>
                {loading ? "Creating account…" : "Create Account"}
              </button>
            </form>

            <Divider />
            <button className="auth-btn-google" type="button" onClick={handleGoogle} disabled={loading}>
              <svg width="18" height="18" viewBox="0 0 18 18" style={{flexShrink:0}}>
                <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
                <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"/>
                <path fill="#FBBC05" d="M3.964 10.706A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.038l3.007-2.332z"/>
                <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z"/>
              </svg>
              Continue with Google
            </button>

            <div style={S.links}>
              <button className="auth-link" onClick={() => switchView("login")}>Already have an account? Sign in</button>
            </div>
          </>
        )}

        {/* View: Forgot Password */}
        {view === "forgot" && (
          <>
            <h2 style={S.title}>Reset Password</h2>
            <p style={S.sub}>Enter your email and we'll send a reset link.</p>

            <form onSubmit={handleForgot}>
              <Input label="Email" type="email" value={email} onChange={setEmail} autoFocus />
              {error && <p style={S.err}>{error}</p>}
              {info && <p style={S.info}>{info}</p>}
              <button className="auth-btn-primary" type="submit" disabled={loading || !!info}>
                {loading ? "Sending…" : "Send Reset Email"}
              </button>
            </form>

            <div style={S.links}>
              <button className="auth-link" onClick={() => switchView("login")}>← Back to sign in</button>
            </div>
          </>
        )}

      </div>

      <p style={S.foot}>Personal use · Data from public markets</p>
    </div>
  );
}

function Input({ label, type, value, onChange, autoFocus }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={S.label}>{label}</label>
      <input
        className="auth-input"
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        autoFocus={autoFocus}
        autoComplete={type === "password" ? "current-password" : "email"}
      />
    </div>
  );
}

function Divider() {
  return (
    <div style={S.divider}>
      <div style={S.divLine} />
      <span style={S.divText}>or</span>
      <div style={S.divLine} />
    </div>
  );
}

const S = {
  wrap: {
    minHeight: "100vh",
    background: "linear-gradient(180deg,#eaf2ff,#f8faff)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px 16px",
    fontFamily: "var(--dm,'DM Sans',sans-serif)",
  },
  logo: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 28,
  },
  logoIcon: {
    width: 48,
    height: 48,
    borderRadius: 14,
    background: "linear-gradient(135deg,#4f68f0,#0ea5e9)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 24,
    boxShadow: "0 8px 24px rgba(79,104,240,.28)",
  },
  logoName: {
    fontFamily: "var(--syne,'Syne',sans-serif)",
    fontWeight: 800,
    fontSize: 22,
    color: "#0f172a",
    letterSpacing: -0.5,
  },
  logoSub: {
    fontFamily: "var(--mono,'IBM Plex Mono',monospace)",
    fontSize: 8,
    color: "#94a3b8",
    letterSpacing: 1.5,
    textTransform: "uppercase",
    marginTop: 2,
  },
  card: {
    width: "100%",
    maxWidth: 360,
    background: "#fff",
    borderRadius: 20,
    boxShadow: "0 4px 32px rgba(91,114,248,.1)",
    border: "1px solid rgba(91,114,248,.08)",
    padding: "28px 24px",
  },
  title: {
    fontFamily: "var(--syne,'Syne',sans-serif)",
    fontWeight: 700,
    fontSize: 20,
    color: "#0f172a",
    marginBottom: 4,
  },
  sub: {
    fontSize: 13,
    color: "#475569",
    marginBottom: 20,
  },
  label: {
    display: "block",
    fontFamily: "var(--mono,'IBM Plex Mono',monospace)",
    fontSize: 10,
    fontWeight: 500,
    color: "#94a3b8",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 5,
  },
  err: {
    fontSize: 12,
    color: "#e11d48",
    background: "#fff1f3",
    border: "1px solid #fecdd3",
    borderRadius: 8,
    padding: "8px 12px",
    marginBottom: 12,
    lineHeight: 1.5,
  },
  info: {
    fontSize: 12,
    color: "#059669",
    background: "#d1fae5",
    border: "1px solid #a7f3d0",
    borderRadius: 8,
    padding: "8px 12px",
    marginBottom: 12,
    lineHeight: 1.5,
  },
  divider: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    margin: "16px 0",
  },
  divLine: {
    flex: 1,
    height: 1,
    background: "#e2e8f0",
  },
  divText: {
    fontSize: 11,
    color: "#94a3b8",
    fontFamily: "var(--mono,'IBM Plex Mono',monospace)",
  },
  links: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 16,
    flexWrap: "wrap",
  },
  foot: {
    marginTop: 20,
    fontSize: 11,
    color: "#94a3b8",
    fontFamily: "var(--mono,'IBM Plex Mono',monospace)",
  },
};

const CSS = `
.auth-input {
  width: 100%;
  padding: 10px 13px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  font-family: var(--dm,'DM Sans',sans-serif);
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  outline: none;
  transition: border-color .2s;
  box-sizing: border-box;
}
.auth-input:focus { border-color: #5b72f8; }
.auth-btn-primary {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg,#5b72f8,#0ea5e9);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-family: var(--dm,'DM Sans',sans-serif);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  margin-top: 4px;
  box-shadow: 0 4px 14px rgba(91,114,248,.25);
  transition: opacity .2s;
}
.auth-btn-primary:hover:not(:disabled) { opacity: .88; }
.auth-btn-primary:disabled { opacity: .55; cursor: not-allowed; }
.auth-btn-google {
  width: 100%;
  padding: 11px 14px;
  background: #fff;
  color: #0f172a;
  border: 1.5px solid #e2e8f0;
  border-radius: 12px;
  font-family: var(--dm,'DM Sans',sans-serif);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  transition: border-color .2s, box-shadow .2s;
}
.auth-btn-google:hover:not(:disabled) {
  border-color: #5b72f8;
  box-shadow: 0 2px 12px rgba(91,114,248,.1);
}
.auth-btn-google:disabled { opacity: .55; cursor: not-allowed; }
.auth-link {
  background: none;
  border: none;
  color: #5b72f8;
  font-size: 12px;
  font-family: var(--dm,'DM Sans',sans-serif);
  font-weight: 600;
  cursor: pointer;
  padding: 0;
  text-decoration: none;
}
.auth-link:hover { text-decoration: underline; }
`;
