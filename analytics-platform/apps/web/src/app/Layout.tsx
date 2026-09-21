import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Database, Activity, Search, LogOut, MessageSquare, Users, LayoutDashboard, BarChart2, Menu, Bell, User as UserIcon, Settings, ChevronLeft, ChevronRight, ChevronDown, Moon, Boxes } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { fetchApi } from '../services/api';

export const Layout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [allDomains, setAllDomains] = useState<any[]>([]);
  const [isDomainDropdownOpen, setIsDomainDropdownOpen] = useState(false);
  const domainDropdownRef = useRef<HTMLDivElement | null>(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isAdmin = user?.role === 'ADMIN';

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (domainDropdownRef.current && !domainDropdownRef.current.contains(event.target as Node)) {
        setIsDomainDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch domains when navigating to domain routes
  useEffect(() => {
    if (location.pathname.startsWith('/domains')) {
      fetchApi('/domains')
        .then((data) => {
          if (Array.isArray(data)) setAllDomains(data);
        })
        .catch(() => {});
    }
  }, [location.pathname]);

  // Derive active domain name if on a domain detail page
  const domainIdMatch = location.pathname.match(/^\/domains\/([^/]+)/);
  const activeDomainId = domainIdMatch ? domainIdMatch[1] : null;
  const activeDomain = activeDomainId ? allDomains.find((d) => d.id === activeDomainId) : null;

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar" style={{ width: isCollapsed ? '80px' : '220px' }}>
        <div className="sidebar-header" style={{ justifyContent: isCollapsed ? 'center' : 'space-between' }}>
          <div className="flex items-center gap-2" style={{ color: 'var(--primary)' }}>
            <BarChart2 size={20} />
            {!isCollapsed && <span style={{ fontWeight: 700 }}>AnalyticsPlatform</span>}
          </div>
          {!isCollapsed && (
            <button className="btn-ghost" style={{ padding: '0.25rem' }} onClick={() => setIsCollapsed(true)}>
              <ChevronLeft size={18} />
            </button>
          )}
        </div>

        <nav className="sidebar-nav">
          {isCollapsed && (
            <button className="btn-ghost mb-4" style={{ padding: '0.25rem', alignSelf: 'center' }} onClick={() => setIsCollapsed(false)}>
              <ChevronRight size={18} />
            </button>
          )}

          {!isCollapsed && <div className="nav-group">Analytics</div>}
          <Link to="/chat" className={`sidebar-link ${location.pathname === '/chat' ? 'active' : ''}`} title="Ask AI">
            <MessageSquare size={18} /> {!isCollapsed && "Ask AI"}
          </Link>
          <Link to="/dashboards" className={`sidebar-link ${location.pathname === '/dashboards' ? 'active' : ''}`} title="Dashboards">
            <LayoutDashboard size={18} /> {!isCollapsed && "Dashboards"}
          </Link>
          <Link to="/domains" className={`sidebar-link ${location.pathname === '/domains' ? 'active' : ''}`} title="Domains">
            <Boxes size={18} /> {!isCollapsed && "Domains"}
          </Link>

          {isAdmin && (
            <>
              {!isCollapsed && <div className="nav-group mt-4">Administration</div>}
              <Link to="/sources" className={`sidebar-link ${location.pathname === '/sources' ? 'active' : ''}`} title="Data Sources">
                <Database size={18} /> {!isCollapsed && "Data Sources"}
              </Link>
              <Link to="/jobs" className={`sidebar-link ${location.pathname === '/jobs' ? 'active' : ''}`} title="Jobs">
                <Activity size={18} /> {!isCollapsed && "Jobs"}
              </Link>
              <Link to="/users" className={`sidebar-link ${location.pathname === '/users' ? 'active' : ''}`} title="Users & Roles">
                <Users size={18} /> {!isCollapsed && "Users & Roles"}
              </Link>
            </>
          )}
        </nav>

        <div style={{ padding: '1rem', borderTop: '1px solid var(--border-color)' }}>
          <button
            className="sidebar-link"
            onClick={handleLogout}
            style={{ width: '100%', background: 'transparent', textAlign: 'left', border: 'none', cursor: 'pointer', justifyContent: isCollapsed ? 'center' : 'flex-start' }}
            title="Logout"
          >
            <LogOut size={18} /> {!isCollapsed && "Logout"}
          </button>
        </div>
      </aside>

      {/* Main Wrapper */}
      <div className="main-wrapper">
        {/* Top Navigation */}
        <header className="top-nav">
          <div className="flex items-center gap-4">
            {/* Page Navigation in Place of Acme Corp */}
            {activeDomainId ? (
              <div className="flex items-center gap-2 text-sm" ref={domainDropdownRef} style={{ position: 'relative' }}>
                <Link
                  to="/domains"
                  style={{
                    color: 'var(--text-muted)',
                    textDecoration: 'none',
                    fontWeight: 500,
                    transition: 'color 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--primary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                >
                  Domains
                </Link>
                <span style={{ color: 'var(--text-faint)', fontSize: '13px' }}>/</span>
                <button
                  onClick={() => setIsDomainDropdownOpen(!isDomainDropdownOpen)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    background: 'transparent',
                    border: 'none',
                    padding: '2px 4px',
                    borderRadius: '4px',
                    fontSize: '13.5px',
                    fontWeight: 600,
                    color: 'var(--text-main)',
                    cursor: 'pointer',
                  }}
                >
                  <span>{activeDomain?.name || 'Test'}</span>
                  <ChevronDown size={13} style={{ color: 'var(--text-muted)' }} />
                </button>

                {isDomainDropdownOpen && allDomains.length > 0 && (
                  <div
                    style={{
                      position: 'absolute',
                      top: 'calc(100% + 6px)',
                      left: '60px',
                      background: '#FFFFFF',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
                      zIndex: 1000,
                      minWidth: '200px',
                      maxHeight: '260px',
                      overflowY: 'auto',
                      padding: '4px 0',
                    }}
                  >
                    {allDomains.map((d) => (
                      <button
                        key={d.id}
                        onClick={() => {
                          setIsDomainDropdownOpen(false);
                          navigate(`/domains/${d.id}`);
                        }}
                        style={{
                          display: 'block',
                          width: '100%',
                          textAlign: 'left',
                          padding: '8px 14px',
                          fontSize: '13px',
                          background: d.id === activeDomainId ? 'var(--primary-light)' : 'transparent',
                          color: d.id === activeDomainId ? 'var(--primary)' : 'var(--text-main)',
                          border: 'none',
                          cursor: 'pointer',
                          fontWeight: d.id === activeDomainId ? 600 : 400,
                        }}
                        onMouseEnter={(e) => {
                          if (d.id !== activeDomainId) e.currentTarget.style.background = '#F8FAFC';
                        }}
                        onMouseLeave={(e) => {
                          if (d.id !== activeDomainId) e.currentTarget.style.background = 'transparent';
                        }}
                      >
                        {d.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : location.pathname === '/domains' ? (
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-main)' }}>
                <Boxes size={18} style={{ color: 'var(--primary)' }} />
                <span>Domains</span>
              </div>
            ) : location.pathname === '/chat' ? (
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-main)' }}>
                <MessageSquare size={18} style={{ color: 'var(--primary)' }} />
                <span>Ask AI</span>
              </div>
            ) : location.pathname === '/dashboards' ? (
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-main)' }}>
                <LayoutDashboard size={18} style={{ color: 'var(--primary)' }} />
                <span>Dashboards</span>
              </div>
            ) : location.pathname === '/sources' ? (
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-main)' }}>
                <Database size={18} style={{ color: 'var(--primary)' }} />
                <span>Data Sources</span>
              </div>
            ) : location.pathname === '/jobs' ? (
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-main)' }}>
                <Activity size={18} style={{ color: 'var(--primary)' }} />
                <span>Jobs</span>
              </div>
            ) : location.pathname === '/users' ? (
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-main)' }}>
                <Users size={18} style={{ color: 'var(--primary)' }} />
                <span>Users & Roles</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--text-main)' }}>
                <span>Conversational Analytics</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            <div className="relative">
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search resources..."
                style={{ width: '250px', paddingLeft: '2rem', background: 'var(--bg-dark)', borderRadius: '9999px' }}
              />
            </div>

            <button className="btn-ghost" style={{ padding: '0.5rem', borderRadius: '50%' }}>
              <Bell size={18} />
            </button>
            <button className="btn-ghost" style={{ padding: '0.5rem', borderRadius: '50%' }}>
              <Moon size={18} />
            </button>

            <div className="flex items-center gap-2" style={{ paddingLeft: '1rem', borderLeft: '1px solid var(--border-color)' }}>
              <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
                <span className="text-sm" style={{ fontWeight: 500 }}>{user?.email}</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--primary)' }}>{user?.role}</span>
              </div>
              <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--bg-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <UserIcon size={16} />
              </div>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <main className="main-content" style={location.pathname === '/chat' ? { height: 'calc(100vh - 60px)', display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' } : {}}>
          <div className="animate-fade-in" style={location.pathname === '/chat' ? { flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 } : {}}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
