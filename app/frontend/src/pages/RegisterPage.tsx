import { useState } from 'react';
import { Shield, Eye, EyeOff, Loader2, UserPlus } from 'lucide-react';
import { authApi } from '../services/api';
import { useNavigate } from 'react-router-dom';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [confirm,  setConfirm]  = useState('');
  const [showPw,   setShowPw]   = useState(false);
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);
  const [success,  setSuccess]  = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setLoading(true);
    try {
      await authApi.register(email, password, username || undefined);
      setSuccess(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-card" style={{ textAlign: 'center' }}>
          <div className="auth-logo">
            <div className="auth-logo-icon" style={{ background: 'linear-gradient(135deg, #10b981, #06b6d4)' }}>
              <Shield size={24} color="white" />
            </div>
            <div className="auth-logo-text">NT505.Q21-KLTN</div>
          </div>
          <h2 style={{ marginBottom: 8 }}>Check your email</h2>
          <p className="auth-subtitle" style={{ marginBottom: 24 }}>
            We've sent a verification link to <strong>{email}</strong>.
            <br />Please verify within <strong>10 minutes</strong> to activate your account.
          </p>
          <button
            className="btn btn-secondary"
            onClick={() => navigate('/login')}
            style={{ width: '100%', textAlign: 'center', display: 'flex', justifyContent: 'center', alignItems: 'center' }}
          >
            Back to Sign In
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-icon">
            <Shield size={24} color="white" />
          </div>
          <div className="auth-logo-text">NT505.Q21-KLTN</div>
        </div>

        <h2>Create account</h2>
        <p className="auth-subtitle">Register to get started with NT505.Q21-KLTN</p>

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
            <label className="form-label">Display Name</label>
            <input
              className="form-control"
              type="text"
              placeholder="Your display name"
              value={username}
              onChange={e => setUsername(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Email *</label>
            <input
              className="form-control"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password *</label>
            <div style={{ position: 'relative' }}>
              <input
                className="form-control"
                type={showPw ? 'text' : 'password'}
                placeholder="Min. 8 characters"
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

          <div className="form-group">
            <label className="form-label">Confirm Password *</label>
            <input
              className="form-control"
              type="password"
              placeholder="Retype your password"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary auth-submit"
            disabled={loading}
            style={{ textAlign: 'center', display: 'flex', justifyContent: 'center', alignItems: 'center' }}
          >
            {loading ? (
              <>
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                Creating account…
              </>
            ) : (
              <>
                <UserPlus size={16} />
                Create Account
              </>
            )}
          </button>

          <p style={{ textAlign: 'center', marginTop: 16, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Already have an account?{' '}
            <a href="/login" style={{ color: 'var(--accent-purple)', fontWeight: 600 }}>Sign in</a>
          </p>
        </form>
      </div>
    </div>
  );
}
