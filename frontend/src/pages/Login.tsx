import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Login() {
  const { login, user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch {
      setError("Неверный email или пароль");
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Karavay</h1>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Пароль
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <div className="error-text">{error}</div>}
        <button type="submit" disabled={isLoading}>
          {isLoading ? "Вход..." : "Войти"}
        </button>
      </form>
    </div>
  );
}
