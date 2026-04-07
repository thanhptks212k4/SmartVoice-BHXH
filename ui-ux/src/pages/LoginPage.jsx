import { useState } from "react";
import { useNavigate } from "react-router-dom";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:3000";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        setError(data.message || "Đăng nhập thất bại");
        return;
      }
      localStorage.setItem("token", data.token);
      navigate("/voice");
    } catch {
      setError("Không thể kết nối đến server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={S.bg}>
      <form onSubmit={handleLogin} style={S.card}>
        <div style={S.logo}>🐾</div>
        <h2 style={S.title}>Voice AI</h2>
        <p style={S.sub}>Đăng nhập để bắt đầu</p>

        <input
          style={S.input}
          type="text"
          placeholder="Tên đăng nhập"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          autoFocus
        />
        <input
          style={S.input}
          type="password"
          placeholder="Mật khẩu"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {error && <p style={S.error}>{error}</p>}

        <button style={{ ...S.btn, opacity: loading ? 0.6 : 1 }} disabled={loading}>
          {loading ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
      </form>
    </div>
  );
}

const S = {
  bg: {
    minHeight: "100vh", display: "flex",
    justifyContent: "center", alignItems: "center",
    background: "#0f0f1a",
  },
  card: {
    background: "#1a1a2e", border: "1px solid #2a2a4a",
    borderRadius: 20, padding: "2.5rem 2rem",
    display: "flex", flexDirection: "column", alignItems: "center",
    gap: 14, width: 320, boxShadow: "0 8px 40px rgba(0,0,0,0.5)",
  },
  logo:  { fontSize: 48 },
  title: { color: "#fff", margin: 0, fontSize: 22, fontWeight: 700 },
  sub:   { color: "#888", margin: 0, fontSize: 13 },
  input: {
    width: "100%", padding: "10px 14px", borderRadius: 10,
    border: "1px solid #3a3a5a", background: "#12122a",
    color: "#fff", fontSize: 14, outline: "none", boxSizing: "border-box",
  },
  btn: {
    width: "100%", padding: "11px 0", borderRadius: 10,
    background: "#7c4dff", color: "#fff", border: "none",
    fontSize: 15, fontWeight: 600, cursor: "pointer", marginTop: 4,
  },
  error: { color: "#ff5252", fontSize: 13, margin: 0 },
};
