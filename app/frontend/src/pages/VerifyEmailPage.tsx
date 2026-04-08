import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Shield, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { authApi } from '../services/api';

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token');

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>(
    token ? 'loading' : 'error'
  );
  const [message, setMessage] = useState(
    token ? '' : 'No verification token provided.'
  );
  const [hasRun, setHasRun] = useState(false);

  if (token && status === 'loading' && !hasRun) {
    setHasRun(true);
    authApi.verifyEmail(token)
      .then(() => {
        setStatus('success');
        setMessage('Your email has been verified successfully!');
      })
      .catch((err: Error) => {
        setStatus('error');
        setMessage(err.message || 'Verification failed. The token may have expired.');
      });
  }

  return (
    <div className="auth-page">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <div className="auth-logo">
          <div className="auth-logo-icon" style={{
            background: status === 'success'
              ? 'linear-gradient(135deg, #10b981, #06b6d4)'
              : status === 'error'
                ? 'linear-gradient(135deg, #ef4444, #f59e0b)'
                : undefined
          }}>
            <Shield size={24} color="white" />
          </div>
          <div className="auth-logo-text">NT505.Q21-KLTN</div>
        </div>

        {status === 'loading' && (
          <>
            <Loader2 size={48} style={{ animation: 'spin 1s linear infinite', margin: '24px auto', color: 'var(--accent-purple)' }} />
            <h2>Verifying your email…</h2>
            <p className="auth-subtitle">Please wait while we confirm your account.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle2 size={48} style={{ margin: '24px auto', color: 'var(--accent-green)' }} />
            <h2>Email Verified!</h2>
            <p className="auth-subtitle" style={{ marginBottom: 24 }}>{message}</p>
            <button
              className="btn btn-primary"
              onClick={() => navigate('/login')}
              style={{ width: '100%', textAlign: 'center', display: 'flex', justifyContent: 'center', alignItems: 'center' }}
            >
              Sign In Now
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle size={48} style={{ margin: '24px auto', color: 'var(--accent-red)' }} />
            <h2>Verification Failed</h2>
            <p className="auth-subtitle" style={{ marginBottom: 24 }}>{message}</p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-secondary"
                onClick={() => navigate('/register')}
                style={{ flex: 1 }}
              >
                Register Again
              </button>
              <button
                className="btn btn-primary"
                onClick={() => navigate('/login')}
                style={{ flex: 1 }}
              >
                Sign In
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
