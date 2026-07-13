import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { Shield, UserPlus, Trash2, Mail, Lock, ShieldCheck, MoreVertical } from 'lucide-react';

export const Users = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('VIEWER');

  const loadUsers = async () => {
    try {
      const data = await fetchApi('/users');
      setUsers(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetchApi('/users', {
        method: 'POST',
        body: JSON.stringify({ email, password, role })
      });
      setEmail('');
      setPassword('');
      loadUsers();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleDisable = async (id: string) => {
    if (!confirm('Are you sure you want to disable this user?')) return;
    try {
      await fetchApi(`/users/${id}`, { method: 'DELETE' });
      loadUsers();
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="title" style={{ margin: 0 }}>
            <Shield size={24} style={{ color: 'var(--primary)' }} /> Users & Roles
          </h2>
          <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
            Manage organization members and their access levels.
          </p>
        </div>
      </div>
      
      <div className="grid grid-cols-3" style={{ alignItems: 'start' }}>
        <div className="card" style={{ gridColumn: 'span 2', padding: 0, overflow: 'hidden' }}>
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={5} className="text-center p-4">
                      <div className="skeleton" style={{ height: '40px', width: '100%', marginBottom: '10px' }} />
                      <div className="skeleton" style={{ height: '40px', width: '100%' }} />
                    </td>
                  </tr>
                ) : users.map(u => (
                  <tr key={u.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--bg-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                          {u.email.charAt(0).toUpperCase()}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 600 }}>{u.email}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${u.role === 'ADMIN' ? 'badge-primary' : 'badge-default'}`}>
                        {u.role === 'ADMIN' && <ShieldCheck size={12} style={{ marginRight: 4 }} />}
                        {u.role}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${u.is_active ? 'badge-success' : 'badge-warning'}`}>
                        <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', marginRight: 6 }} />
                        {u.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td>
                      <span className="text-sm text-muted">{new Date(u.created_at).toLocaleDateString()}</span>
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-2">
                        <button className="btn-ghost" onClick={() => handleDisable(u.id)} disabled={!u.is_active} style={{ padding: '0.5rem', color: u.is_active ? 'var(--danger)' : 'var(--text-muted)' }} title="Disable User">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.125rem' }}>
            <UserPlus size={20} color="var(--primary)" /> Invite New User
          </h3>
          <form onSubmit={handleInvite}>
            <div className="form-group">
              <label>Email Address</label>
              <div style={{ position: 'relative' }}>
                <Mail size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="user@company.com" style={{ paddingLeft: '2.5rem' }} />
              </div>
            </div>
            <div className="form-group">
              <label>Initial Password</label>
              <div style={{ position: 'relative' }}>
                <Lock size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} placeholder="••••••••" style={{ paddingLeft: '2.5rem' }} />
              </div>
            </div>
            <div className="form-group">
              <label>Access Role</label>
              <select value={role} onChange={e => setRole(e.target.value)}>
                <option value="VIEWER">VIEWER (Read-only Dashboards)</option>
                <option value="ANALYST">ANALYST (Create Insights)</option>
                <option value="ADMIN">ADMIN (Full Access)</option>
              </select>
            </div>
            <button type="submit" style={{ width: '100%', marginTop: '0.5rem' }}>Send Invitation</button>
          </form>
        </div>
      </div>
    </div>
  );
};
