import { useEffect, useState } from 'react';
import { Users, ShieldCheck, ShieldAlert, Search, UserCog } from 'lucide-react';
import TopHeader from '../components/Layout/TopHeader';
import { userApi, type UserInfo } from '../services/api';

export default function UsersPage() {
  const [users,   setUsers]   = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search,  setSearch]  = useState('');
  const [error,   setError]   = useState('');

  const fetchUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await userApi.list();
      setUsers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleRoleToggle = async (userId: number, currentRole: string) => {
    const newRole = currentRole === 'admin' ? 'user' : 'admin';
    try {
      await userApi.updateRole(userId, newRole);
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u));
    } catch { /* ignore */ }
  };

  const filtered = users.filter(u =>
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    (u.username ?? '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      <TopHeader
        title="Users Management"
        subtitle={`${users.length} registered users`}
        onRefresh={fetchUsers}
      />
      <div className="page-content">
        {error && (
          <div className="card" style={{
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            color: 'var(--accent-red)',
            padding: 16,
            marginBottom: 16,
          }}>
            {error}
          </div>
        )}

        {/* Summary */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
          {[
            { label: 'Total Users', count: users.length, icon: <Users size={18} />, color: 'var(--accent-purple)' },
            { label: 'Admins', count: users.filter(u => u.role === 'admin').length, icon: <ShieldCheck size={18} />, color: 'var(--accent-green)' },
            { label: 'Unverified', count: users.filter(u => !u.is_verified).length, icon: <ShieldAlert size={18} />, color: 'var(--accent-yellow)' },
          ].map(s => (
            <div key={s.label} className="card" style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
                {s.icon} {s.label}
              </div>
              <span style={{ fontSize: '1.4rem', fontWeight: 700, color: s.color }}>{s.count}</span>
            </div>
          ))}
        </div>

        {/* Search */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="header-search" style={{ maxWidth: 320 }}>
            <Search size={15} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Search users…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        {/* Table */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">All Users</div>
          </div>

          {loading ? (
            <div className="spinner" />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#ID</th>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Verified</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(user => (
                    <tr key={user.id}>
                      <td><span className="table-id">#{user.id}</span></td>
                      <td style={{ fontWeight: 600 }}>{user.username}</td>
                      <td style={{ color: 'var(--text-secondary)' }}>{user.email}</td>
                      <td>
                        <span className={`badge ${user.role === 'admin' ? 'badge-info' : 'badge-success'}`}>
                          {user.role}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${user.is_verified ? 'badge-success' : 'badge-warning'}`}>
                          {user.is_verified ? 'Yes' : 'No'}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleRoleToggle(user.id, user.role)}
                          style={{ fontSize: '0.75rem' }}
                        >
                          <UserCog size={12} />
                          {user.role === 'admin' ? 'Demote' : 'Promote'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
