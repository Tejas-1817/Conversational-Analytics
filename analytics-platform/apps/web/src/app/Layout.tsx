import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Database, Activity, Search, LogOut, BookOpen, MessageSquare, Users, LayoutDashboard, BarChart2, Menu, Bell, User as UserIcon, Settings, ChevronLeft, ChevronRight, Moon, Building2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export const Layout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isAdmin = user?.role === 'ADMIN';

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar" style={{ width: isCollapsed ? '80px' : '280px' }}>
        <div className="sidebar-header" style={{ justifyContent: isCollapsed ? 'center' : 'space-between' }}>
          <div className="flex items-center gap-2" style={{ color: 'var(--primary)' }}>
            <BarChart2 size={24} />
            {!isCollapsed && <span style={{ fontWeight: 700 }}>AnalyticsPlatform</span>}
          </div>
          {!isCollapsed && (
            <button className="btn-ghost" style={{ padding: '0.25rem' }} onClick={() => setIsCollapsed(true)}>
              <ChevronLeft size={20} />
            </button>
          )}
        </div>

        <nav className="sidebar-nav">
          {isCollapsed && (
            <button className="btn-ghost mb-4" style={{ padding: '0.25rem', alignSelf: 'center' }} onClick={() => setIsCollapsed(false)}>
              <ChevronRight size={20} />
            </button>
          )}

          {!isCollapsed && <div className="nav-group">Analytics</div>}
          <Link to="/chat" className={`sidebar-link ${location.pathname === '/chat' ? 'active' : ''}`} title="Ask AI">
            <MessageSquare size={20} /> {!isCollapsed && "Ask AI"}
          </Link>
          <Link to="/dashboards" className={`sidebar-link ${location.pathname === '/dashboards' ? 'active' : ''}`} title="Dashboards">
            <LayoutDashboard size={20} /> {!isCollapsed && "Dashboards"}
          </Link>

          {isAdmin && (
            <>
              {!isCollapsed && <div className="nav-group mt-4">Administration</div>}
              <Link to="/sources" className={`sidebar-link ${location.pathname === '/sources' ? 'active' : ''}`} title="Data Sources">
                <Database size={20} /> {!isCollapsed && "Data Sources"}
              </Link>
              <Link to="/jobs" className={`sidebar-link ${location.pathname === '/jobs' ? 'active' : ''}`} title="Jobs">
                <Activity size={20} /> {!isCollapsed && "Jobs"}
              </Link>
              <Link to="/explorer" className={`sidebar-link ${location.pathname === '/explorer' ? 'active' : ''}`} title="Schema Explorer">
                <Search size={20} /> {!isCollapsed && "Schema Explorer"}
              </Link>
              <Link to="/semantic" className={`sidebar-link ${location.pathname === '/semantic' ? 'active' : ''}`} title="Semantic Layer">
                <BookOpen size={20} /> {!isCollapsed && "Semantic Layer"}
              </Link>
              <Link to="/users" className={`sidebar-link ${location.pathname === '/users' ? 'active' : ''}`} title="Users & Roles">
                <Users size={20} /> {!isCollapsed && "Users & Roles"}
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
            <LogOut size={20} /> {!isCollapsed && "Logout"}
          </button>
        </div>
      </aside>

      {/* Main Wrapper */}
      <div className="main-wrapper">
        {/* Top Navigation */}
        <header className="top-nav">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
              <Building2 size={20} />
              <span className="text-sm font-medium">Acme Corp</span>
              <span className="badge badge-default" style={{ marginLeft: '8px' }}>Enterprise</span>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="text" 
                placeholder="Search resources..." 
                style={{ width: '250px', paddingLeft: '2rem', background: 'var(--bg-dark)', borderRadius: '9999px' }}
              />
            </div>
            
            <button className="btn-ghost" style={{ padding: '0.5rem', borderRadius: '50%' }}>
              <Bell size={20} />
            </button>
            <button className="btn-ghost" style={{ padding: '0.5rem', borderRadius: '50%' }}>
              <Moon size={20} />
            </button>
            
            <div className="flex items-center gap-2" style={{ paddingLeft: '1rem', borderLeft: '1px solid var(--border-color)' }}>
              <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
                <span className="text-sm" style={{ fontWeight: 500 }}>{user?.email}</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--primary)' }}>{user?.role}</span>
              </div>
              <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'var(--bg-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <UserIcon size={18} />
              </div>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <main className="main-content">
          <div className="animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
