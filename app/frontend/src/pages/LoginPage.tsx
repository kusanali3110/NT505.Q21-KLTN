import { useState } from 'react';

import { Shield, Eye, EyeOff, Loader2 } from 'lucide-react';
import { authApi, setToken } from '../services/api';

export default function LoginPage() {

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw,   setShowPw]   = useState(false);
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await authApi.login(username, password);
      setToken(data.access_token);
      window.location.href = '/dashboard';
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        {/* Logo */}
        <div className="auth-logo">
          <div className="auth-logo-icon">
            <Shield size={24} color="white" />
          </div>
          <div className="auth-logo-text">NT505.Q21-KLTN</div>
        </div>

        <h2>Welcome back</h2>
        <p className="auth-subtitle">Sign in to your account to continue</p>

        <form onSubmit={handleSubmit}>
          {error && (
            <div style={{
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 8,
              padding: '10px 14px',
              marginBottom: 16,
              color: 'var(--accent-red)',
              fontSize: '0.85rem',
            }}>
              {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              id="username"
              className="form-control"
              type="text"
              autoComplete="username"
              placeholder="Enter your username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <div style={{ position: 'relative' }}>
              <input
                id="password"
                className="form-control"
                type={showPw ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                style={{ paddingRight: 40 }}
                required
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                style={{
                  position: 'absolute', right: 12, top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                  background: 'none', border: 'none', cursor: 'pointer',
                }}
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button
            id="login-submit"
            type="submit"
            className="btn btn-primary auth-submit"
            disabled={loading}
            style={{ textAlign: 'center', display: 'flex', justifyContent: 'center', alignItems: 'center' }}
          >
            {loading ? (
              <>
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                Signing in…
              </>
            ) : 'Sign In'}
          </button>

          <p style={{ textAlign: 'center', marginTop: 16, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Don't have an account?{' '}
            <a href="/register" style={{ color: 'var(--accent-purple)', fontWeight: 600 }}>Create account</a>
          </p>
        </form>
      </div>
    </div>
  );
}
