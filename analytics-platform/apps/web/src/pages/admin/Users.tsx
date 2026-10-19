import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { UserPlus, Trash2, Mail, Lock, ShieldCheck, Database, Building2, Filter, KeyRound } from 'lucide-react';
import { ManageDataSourceAccessModal } from '../../components/ManageDataSourceAccessModal';
import type { UserAccessTarget } from '../../components/ManageDataSourceAccessModal';

export const Users = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [tenants, setTenants] = useState<any[]>([]);
  const [selectedTenantFilter, setSelectedTenantFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('USER');
  const [selectedTenantId, setSelectedTenantId] = useState('');
  const [selectedUserForAccess, setSelectedUserForAccess] = useState<UserAccessTarget | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [userData, tenantData] = await Promise.all([
        fetchApi('/users'),
        fetchApi('/tenants').catch(() => []),
      ]);
      setUsers(userData);
      if (Array.isArray(tenantData)) {
        setTenants(tenantData);
        if (tenantData.length > 0 && !selectedTenantId) {
          setSelectedTenantId(tenantData[0].id);
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetchApi('/users', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          role,
          tenant_id: selectedTenantId || undefined,
        }),
      });
      setEmail('');
      setPassword('');
      loadData();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleDisable = async (id: string) => {
    if (!confirm('Are you sure you want to disable this user?')) return;
    try {
      await fetchApi(`/users/${id}`, { method: 'DELETE' });
      loadData();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleRoleToggle = async (user: any) => {
    const newRole = user.role === 'ADMIN' ? 'USER' : 'ADMIN';
    if (!confirm(`Change role for ${user.email} to ${newRole}?`)) return;
    try {
      await fetchApi(`/users/${user.id}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role: newRole }),
      });
      loadData();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleResetPassword = async (user: any) => {
    const newPassword = prompt(`Enter new password for ${user.email} (min 8 characters):`);
    if (!newPassword) return;
    if (newPassword.length < 8) {
      alert('Password must be at least 8 characters long');
      return;
    }
    try {
      await fetchApi(`/users/${user.id}/reset-password`, {
        method: 'POST',
        body: JSON.stringify({ new_password: newPassword }),
      });
      alert('Password has been reset successfully.');
    } catch (e: any) {
      alert(e.message);
    }
  };

  const tenantMap = React.useMemo(() => {
    const map: Record<string, string> = {};
    tenants.forEach((t) => {
      map[t.id] = t.display_name || t.name;
    });
    return map;
  }, [tenants]);

  const filteredUsers = React.useMemo(() => {
    if (selectedTenantFilter === 'ALL') return users;
    return users.filter((u) => u.tenant_id === selectedTenantFilter);
  }, [users, selectedTenantFilter]);

  return (
    <div>
      <ManageDataSourceAccessModal
        isOpen={!!selectedUserForAccess}
        onClose={() => setSelectedUserForAccess(null)}
        user={selectedUserForAccess}
        onSuccess={loadData}
      />

      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="title" style={{ margin: 0 }}>
            Users & Roles
          </h2>
          <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
            Enterprise multi-tenant user access management. Only <strong>ADMIN</strong> and <strong>USER</strong> roles are supported.
          </p>
        </div>

        {tenants.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Filter size={15} style={{ color: 'var(--text-muted)' }} />
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Enterprise:</span>
            <select
              value={selectedTenantFilter}
              onChange={(e) => setSelectedTenantFilter(e.target.value)}
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.85rem' }}
            >
              <option value="ALL">All Enterprises ({users.length})</option>
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.display_name || t.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3" style={{ alignItems: 'start' }}>
        <div className="card" style={{ gridColumn: 'span 2', padding: 0, overflow: 'hidden' }}>
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Enterprise</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Data Access</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={6} className="text-center p-4">
                      <div className="skeleton" style={{ height: '40px', width: '100%', marginBottom: '10px' }} />
                      <div className="skeleton" style={{ height: '40px', width: '100%' }} />
                    </td>
                  </tr>
                ) : filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No users found for this enterprise.
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: '50%',
                              background: 'var(--bg-dark)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: 'var(--text-muted)',
                              fontWeight: 600,
                            }}
                          >
                            {u.email.charAt(0).toUpperCase()}
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <span style={{ fontWeight: 600 }}>{u.email}</span>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              Joined {new Date(u.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <Building2 size={13} />
                          {tenantMap[u.tenant_id] || 'Default Enterprise'}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className={`badge ${u.role === 'ADMIN' ? 'badge-primary' : 'badge-default'}`}
                          onClick={() => handleRoleToggle(u)}
                          title="Click to toggle role (ADMIN / USER)"
                          style={{
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            border: 'none',
                          }}
                        >
                          {u.role === 'ADMIN' && <ShieldCheck size={12} style={{ marginRight: 4 }} />}
                          {u.role}
                        </button>
                      </td>
                      <td>
                        <span className={`badge ${u.is_active ? 'badge-success' : 'badge-warning'}`}>
                          <div
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: '50%',
                              background: 'currentColor',
                              marginRight: 6,
                            }}
                          />
                          {u.is_active ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td>
                        {u.role === 'ADMIN' ? (
                          <span
                            className="badge badge-primary"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                            title="Admins have access to all data sources and tables"
                          >
                            <ShieldCheck size={12} />
                            All Sources & Tables
                          </span>
                        ) : (
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => setSelectedUserForAccess(u)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '0.25rem 0.6rem',
                              fontSize: '0.8rem',
                              color: (u.granted_sources_count ?? 0) > 0 ? 'var(--primary)' : 'var(--text-muted)',
                              border: '1px solid var(--border-color)',
                              borderRadius: 'var(--radius-sm)',
                              background:
                                (u.granted_sources_count ?? 0) > 0
                                  ? 'rgba(59, 130, 246, 0.08)'
                                  : 'transparent',
                            }}
                            title="Configure data source and table permissions"
                          >
                            <Database size={13} />
                            <span>
                              {u.granted_sources_count ?? 0}{' '}
                              {u.granted_sources_count === 1 ? 'source' : 'sources'}
                            </span>
                          </button>
                        )}
                      </td>
                      <td>
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => setSelectedUserForAccess(u)}
                            style={{ padding: '0.5rem', color: 'var(--primary)' }}
                            title="Configure Data Source & Table Access"
                          >
                            <Database size={16} />
                          </button>
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => handleResetPassword(u)}
                            style={{ padding: '0.5rem', color: 'var(--text-muted)' }}
                            title="Reset Password"
                          >
                            <KeyRound size={16} />
                          </button>
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => handleDisable(u.id)}
                            disabled={!u.is_active}
                            style={{ padding: '0.5rem', color: u.is_active ? 'var(--danger)' : 'var(--text-muted)' }}
                            title="Disable User"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <h3
            style={{
              marginBottom: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '1.125rem',
            }}
          >
            <UserPlus size={20} color="var(--primary)" /> Invite New User
          </h3>
          <form onSubmit={handleInvite}>
            <div className="form-group">
              <label>Email Address</label>
              <div style={{ position: 'relative' }}>
                <Mail
                  size={16}
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                  }}
                />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="user@enterprise.com"
                  style={{ paddingLeft: '2.5rem' }}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Initial Password</label>
              <div style={{ position: 'relative' }}>
                <Lock
                  size={16}
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                  }}
                />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  placeholder="••••••••"
                  style={{ paddingLeft: '2.5rem' }}
                />
              </div>
            </div>

            {tenants.length > 0 && (
              <div className="form-group">
                <label>Enterprise Organization</label>
                <div style={{ position: 'relative' }}>
                  <Building2
                    size={16}
                    style={{
                      position: 'absolute',
                      left: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted)',
                    }}
                  />
                  <select
                    value={selectedTenantId}
                    onChange={(e) => setSelectedTenantId(e.target.value)}
                    style={{ paddingLeft: '2.5rem' }}
                  >
                    {tenants.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.display_name || t.name} ({t.slug})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            <div className="form-group">
              <label>Access Role</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="USER">USER (Enterprise User - Deny by default)</option>
                <option value="ADMIN">ADMIN (Platform Administrator)</option>
              </select>
            </div>

            <button type="submit" style={{ width: '100%', marginTop: '0.5rem' }}>
              Create User
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
