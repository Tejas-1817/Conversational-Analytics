import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Database, Activity, Search, LogOut, MessageSquare, MessageSquarePlus, Users, LayoutDashboard, BarChart2, Menu, Bell, User as UserIcon, Settings, ChevronLeft, ChevronRight, ChevronDown, Moon, Boxes, Building2, SquarePen, Plus } from 'lucide-react';
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
  const [isProfileDropdownOpen, setIsProfileDropdownOpen] = useState(false);
  const profileDropdownRef = useRef<HTMLDivElement | null>(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isAdmin = user?.role === 'ADMIN';

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (domainDropdownRef.current && !domainDropdownRef.current.contains(target)) {
        setIsDomainDropdownOpen(false);
      }
      if (profileDropdownRef.current && !profileDropdownRef.current.contains(target)) {
        setIsProfileDropdownOpen(false);
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
      <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`} style={{ width: isCollapsed ? '48px' : '180px' }}>
        <div className="sidebar-header" style={{ justifyContent: 'center', padding: isCollapsed ? '0' : '0 1rem' }}>
          <div className="flex items-center" style={{ color: 'var(--primary)', justifyContent: 'center', gap: isCollapsed ? 0 : '0.5rem', overflow: 'hidden' }}>
            <BarChart2 size={20} style={{ flexShrink: 0 }} />
            {!isCollapsed && <span style={{ fontWeight: 700, fontSize: '0.9rem', whiteSpace: 'nowrap' }}>AnalyticsPlatform</span>}
          </div>
        </div>

        <nav className="sidebar-nav" style={{ padding: isCollapsed ? '0.75rem 0' : '0.75rem 0.5rem' }}>

          {/* New Chat Menu */}
          <Link
            to="/chat?new=true"
            onClick={() => {
              try { localStorage.removeItem('active_conversation_id'); } catch {}
              if (typeof window !== 'undefined') {
                window.dispatchEvent(new CustomEvent('app:new-chat'));
              }
            }}
            className={`sidebar-link ${location.pathname === '/chat' && location.search.includes('new=true') ? 'active' : ''}`}
            title="New Chat"
          >
            <MessageSquarePlus size={18} />
            {!isCollapsed && <span>New Chat</span>}
          </Link>

          {/* Chats Menu with Chevron Right */}
          <Link
            to="/chats"
            className={`sidebar-link ${location.pathname === '/chats' || (location.pathname === '/chat' && !location.search.includes('new=true')) ? 'active' : ''}`}
            title="Chats"
          >
            <MessageSquare size={18} />
            {!isCollapsed && <span>Chats</span>}
            {!isCollapsed && (
              <ChevronRight size={16} style={{ marginLeft: 'auto', opacity: 0.7 }} />
            )}
          </Link>

          {!isCollapsed && <div className="nav-group mt-3">Analytics</div>}
          <Link to="/dashboards" className={`sidebar-link ${location.pathname === '/dashboards' ? 'active' : ''}`} title="Dashboards">
            <LayoutDashboard size={18} />
            {!isCollapsed && <span>Dashboards</span>}
          </Link>
          <Link to="/domains" className={`sidebar-link ${location.pathname === '/domains' ? 'active' : ''}`} title="Domains">
            <Boxes size={18} />
            {!isCollapsed && <span>Domains</span>}
          </Link>

          {isAdmin && (
            <>
              {!isCollapsed && <div className="nav-group mt-4">Administration</div>}
              <Link to="/sources" className={`sidebar-link ${location.pathname === '/sources' ? 'active' : ''}`} title="Data Sources">
                <Database size={18} />
                {!isCollapsed && <span>Data Sources</span>}
              </Link>
              <Link to="/jobs" className={`sidebar-link ${location.pathname === '/jobs' ? 'active' : ''}`} title="Jobs">
                <Activity size={18} />
                {!isCollapsed && <span>Jobs</span>}
              </Link>
              <Link to="/users" className={`sidebar-link ${location.pathname === '/users' ? 'active' : ''}`} title="Users & Roles">
                <Users size={18} />
                {!isCollapsed && <span>Users & Roles</span>}
              </Link>
              <Link to="/enterprises" className={`sidebar-link ${location.pathname === '/enterprises' ? 'active' : ''}`} title="Enterprises">
                <Building2 size={18} />
                {!isCollapsed && <span>Enterprises</span>}
              </Link>
            </>
          )}
        </nav>

        <div style={{ padding: isCollapsed ? '0.75rem 0' : '0.75rem 0.5rem', borderTop: '1px solid var(--border-color)', display: 'flex', justifyContent: 'center' }}>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: isCollapsed ? 0 : '0.5rem',
              padding: isCollapsed ? 0 : '0.45rem 0.5rem',
              width: isCollapsed ? '36px' : '100%',
              height: isCollapsed ? '36px' : 'auto',
              margin: '0 auto',
              background: 'transparent',
              color: 'var(--text-muted)',
              textAlign: 'left',
              border: 'none',
              outline: 'none',
              boxShadow: 'none',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 500,
              borderRadius: 'var(--radius-sm)',
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--text-main)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--text-muted)';
            }}
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            {!isCollapsed && <span>Collapse</span>}
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
            ) : location.pathname === '/chats' ? (
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-main)' }}>
                <MessageSquare size={18} style={{ color: 'var(--primary)' }} />
                <span>Chats</span>
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

            {/* User Profile Dropdown */}
            <div
              ref={profileDropdownRef}
              style={{ position: 'relative', paddingLeft: '0.75rem', borderLeft: '1px solid var(--border-color)' }}
            >
              <button
                type="button"
                onClick={() => setIsProfileDropdownOpen((prev) => !prev)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  background: 'none',
                  border: 'none',
                  outline: 'none',
                  boxShadow: 'none',
                  padding: '0.25rem 0.4rem',
                  borderRadius: 'var(--radius-sm, 6px)',
                  cursor: 'pointer',
                  color: 'inherit',
                }}
                aria-label="User Profile"
                aria-expanded={isProfileDropdownOpen}
              >
                <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
                  <span className="text-sm" style={{ fontWeight: 500, color: 'var(--text-main)' }}>
                    {user?.email}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--primary)', fontWeight: 600 }}>
                    {user?.role}
                  </span>
                </div>
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: 'var(--bg-hover)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-main)',
                  }}
                >
                  <UserIcon size={16} />
                </div>
              </button>

              {/* Profile Dropdown Menu */}
              {isProfileDropdownOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 6px)',
                    right: 0,
                    zIndex: 1000,
                    minWidth: '200px',
                    background: '#FFFFFF',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
                    padding: '0.35rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                  }}
                >
                  <div
                    style={{
                      padding: '0.5rem 0.65rem',
                      borderBottom: '1px solid var(--border-color)',
                      marginBottom: '0.25rem',
                    }}
                  >
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Signed in as</div>
                    <div
                      style={{
                        fontSize: '0.825rem',
                        fontWeight: 600,
                        color: 'var(--text-main)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {user?.email}
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setIsProfileDropdownOpen(false);
                      handleLogout();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.625rem',
                      width: '100%',
                      padding: '0.5rem 0.65rem',
                      fontSize: '0.85rem',
                      color: '#ef4444',
                      background: 'transparent',
                      border: 'none',
                      outline: 'none',
                      boxShadow: 'none',
                      borderRadius: 'var(--radius-sm, 4px)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontWeight: 500,
                      transition: 'color 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = '#b91c1c';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = '#ef4444';
                    }}
                  >
                    <LogOut size={16} />
                    <span>Logout</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Content Area */}
        <main
          className="main-content"
          style={
            location.pathname === '/chat' || location.pathname === '/dashboards'
              ? { height: 'calc(100vh - 60px)', display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }
              : {}
          }
        >
          <div
            className="animate-fade-in"
            style={
              location.pathname === '/chat' || location.pathname === '/dashboards'
                ? { flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }
                : {}
            }
          >
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
