import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  Trash2,
  Edit2,
  Search,
  MoreVertical,
  ChevronDown,
  ArrowUpDown,
  MessageSquare,
  FileText,
  ThumbsUp,
  ThumbsDown,
  Info,
  BookOpen,
  Share2,
  ChevronLeft,
  ChevronRight,
  Database,
  Eye,
  EyeOff,
  Boxes,
} from 'lucide-react';
import { fetchApi } from '../../services/api';
import { DomainModal } from '../../components/DomainModal';
import { SourceLogo } from '../../components/SourceLogos';

export interface Domain {
  id: string;
  name: string;
  description: string;
  status: string;
  document_count: number;
  table_count?: number;
  source_id?: string | null;
  source_name?: string | null;
  data_sources?: string[];
  dashboards_count?: number;
  agents_count?: number;
  users_count?: number;
  admins?: string[];
  activity_messages?: number;
  activity_queries?: number;
  activity_thumbs_up?: number;
  activity_thumbs_down?: number;
  is_hidden?: boolean;
  created_at: string;
  updated_at: string;
}

// In-memory mock fallback branch
export let mockDomains: Domain[] = [];

export const addMockDomain = (domain: Domain) => {
  mockDomains = [domain, ...mockDomains];
};

export const updateMockDomainDocs = (id: string, countDelta: number) => {
  mockDomains = mockDomains.map((d) =>
    d.id === id ? { ...d, document_count: (d.document_count || 0) + countDelta } : d
  );
};

// Format date into WisdomAI standard: "Sep 10, 2026, 6:45 PM"
function formatDateTime(dateStr?: string): string {
  if (!dateStr) return 'Never';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return dateStr;
  }
}

export const Domains: React.FC = () => {
  const navigate = useNavigate();
  const [domains, setDomains] = useState<Domain[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Filters & Controls
  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [ownerFilter, setOwnerFilter] = useState('all');
  const [showHidden, setShowHidden] = useState(false);

  // Sorting
  const [sortField, setSortField] = useState<keyof Domain>('updated_at');
  const [sortAsc, setSortAsc] = useState(false);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(50);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedDomainId, setSelectedDomainId] = useState<string | undefined>(undefined);
  const [selectedDomainName, setSelectedDomainName] = useState<string | undefined>(undefined);

  // Actions menu state
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const loadDomains = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await fetchApi('/domains');
      setDomains(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('Failed to load domains:', err);
      setLoadError(err?.message || 'Failed to load domains.');
      setDomains([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDomains();
  }, []);

  // Close actions menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setActiveMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const deleteDomain = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this domain?')) return;
    try {
      await fetchApi(`/domains/${id}`, { method: 'DELETE' });
      setActiveMenuId(null);
      loadDomains();
    } catch (err: any) {
      console.error('Failed to delete domain', err);
      alert(`Failed to delete domain: ${err.message || err}`);
    }
  };

  const toggleHideDomain = (id: string) => {
    setDomains((prev) =>
      prev.map((d) => (d.id === id ? { ...d, is_hidden: !d.is_hidden } : d))
    );
    setActiveMenuId(null);
  };

  const openCreateModal = () => {
    setSelectedDomainId(undefined);
    setSelectedDomainName(undefined);
    setIsModalOpen(true);
  };

  const openDomainDetail = (domain: Domain, tab?: string) => {
    navigate(tab ? `/domains/${domain.id}?tab=${tab}` : `/domains/${domain.id}`);
  };

  // Filtered & Sorted Domains
  const filteredDomains = useMemo(() => {
    return domains
      .filter((d) => {
        if (!showHidden && d.is_hidden) return false;
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchName = d.name?.toLowerCase().includes(q);
          const matchDesc = d.description?.toLowerCase().includes(q);
          if (!matchName && !matchDesc) return false;
        }
        if (sourceFilter !== 'all') {
          const matchSource =
            d.source_name?.toLowerCase().includes(sourceFilter.toLowerCase()) ||
            (d.data_sources &&
              d.data_sources.some((s) => s.toLowerCase().includes(sourceFilter.toLowerCase())));
          if (!matchSource) return false;
        }
        if (ownerFilter !== 'all') {
          const matchOwner = d.admins?.some((a) =>
            a.toLowerCase().includes(ownerFilter.toLowerCase())
          );
          if (!matchOwner) return false;
        }
        return true;
      })
      .sort((a, b) => {
        let valA: any = a[sortField];
        let valB: any = b[sortField];

        if (sortField === 'updated_at' || sortField === 'created_at') {
          valA = new Date(valA || 0).getTime();
          valB = new Date(valB || 0).getTime();
        } else if (typeof valA === 'string') {
          valA = valA.toLowerCase();
          valB = (valB || '').toLowerCase();
        }

        if (valA < valB) return sortAsc ? -1 : 1;
        if (valA > valB) return sortAsc ? 1 : -1;
        return 0;
      });
  }, [domains, searchQuery, sourceFilter, ownerFilter, showHidden, sortField, sortAsc]);

  // Pagination slice
  const paginatedDomains = useMemo(() => {
    const startIndex = (currentPage - 1) * rowsPerPage;
    return filteredDomains.slice(startIndex, startIndex + rowsPerPage);
  }, [filteredDomains, currentPage, rowsPerPage]);

  const totalPages = Math.max(1, Math.ceil(filteredDomains.length / rowsPerPage));

  const handleSort = (field: keyof Domain) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  return (
    <div>
      {/* 1. TOP HEADER */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.25rem',
        }}
      >
        <h1
          style={{
            fontSize: '1.5rem',
            fontWeight: 600,
            color: 'var(--text-main)',
            margin: 0,
            letterSpacing: '-0.02em',
          }}
        >
          Domains
        </h1>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            className="btn-ghost"
            title="Documentation"
            style={{
              padding: '6px',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-muted)',
            }}
          >
            <BookOpen size={18} />
          </button>
          <button
            className="btn-ghost"
            title="Share & Permissions"
            style={{
              padding: '6px',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-muted)',
            }}
          >
            <Share2 size={18} />
          </button>
        </div>
      </div>

      {/* 2. FILTER & ACTION TOOLBAR */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '1rem',
        }}
      >
        {/* Left Side: Search + Dropdowns + Show Hidden */}
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          {/* Search Box */}
          <div
            style={{
              position: 'relative',
              width: '240px',
            }}
          >
            <Search
              size={15}
              style={{
                position: 'absolute',
                left: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-faint)',
              }}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Search Domains"
              style={{
                width: '100%',
                padding: '7px 12px 7px 32px',
                fontSize: '13px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: 'var(--text-main)',
                outline: 'none',
              }}
            />
          </div>

          {/* Filter by data source type */}
          <div style={{ position: 'relative' }}>
            <select
              value={sourceFilter}
              onChange={(e) => {
                setSourceFilter(e.target.value);
                setCurrentPage(1);
              }}
              style={{
                appearance: 'none',
                padding: '7px 28px 7px 12px',
                fontSize: '13px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: sourceFilter === 'all' ? 'var(--text-muted)' : 'var(--text-main)',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              <option value="all">Filter by data source type</option>
              <option value="postgres">PostgreSQL</option>
              <option value="mysql">MySQL</option>
              <option value="excel">Excel (.xlsx)</option>
              <option value="snowflake">Snowflake</option>
              <option value="bigquery">BigQuery</option>
              <option value="mssql">SQL Server</option>
            </select>
            <ChevronDown
              size={14}
              style={{
                position: 'absolute',
                right: '9px',
                top: '50%',
                transform: 'translateY(-50%)',
                pointerEvents: 'none',
                color: 'var(--text-faint)',
              }}
            />
          </div>

          {/* Filter by owner */}
          <div style={{ position: 'relative' }}>
            <select
              value={ownerFilter}
              onChange={(e) => {
                setOwnerFilter(e.target.value);
                setCurrentPage(1);
              }}
              style={{
                appearance: 'none',
                padding: '7px 28px 7px 12px',
                fontSize: '13px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: ownerFilter === 'all' ? 'var(--text-muted)' : 'var(--text-main)',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              <option value="all">Filter by owner</option>
              <option value="admin">Admin</option>
              <option value="shailesh">Shailesh Kulkarni</option>
              <option value="girish">Girish Ch...</option>
            </select>
            <ChevronDown
              size={14}
              style={{
                position: 'absolute',
                right: '9px',
                top: '50%',
                transform: 'translateY(-50%)',
                pointerEvents: 'none',
                color: 'var(--text-faint)',
              }}
            />
          </div>

          {/* Show hidden Switch Toggle */}
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '13px',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              userSelect: 'none',
              marginLeft: '4px',
            }}
          >
            <div
              onClick={() => setShowHidden(!showHidden)}
              style={{
                width: '36px',
                height: '20px',
                borderRadius: '10px',
                background: showHidden ? 'var(--primary)' : '#CBD5E1',
                position: 'relative',
                transition: 'background 0.2s',
                cursor: 'pointer',
              }}
            >
              <div
                style={{
                  width: '16px',
                  height: '16px',
                  borderRadius: '50%',
                  background: '#FFFFFF',
                  position: 'absolute',
                  top: '2px',
                  left: showHidden ? '18px' : '2px',
                  transition: 'left 0.2s',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                }}
              />
            </div>
            Show hidden
          </label>
        </div>

        {/* Right Side: + Add domain Button */}
        <button
          className="btn-primary"
          onClick={openCreateModal}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 16px',
            fontSize: '13px',
            fontWeight: 500,
            borderRadius: 'var(--radius-sm)',
            background: '#4F46E5',
            color: '#FFFFFF',
            border: 'none',
            cursor: 'pointer',
            boxShadow: '0 1px 2px rgba(79, 70, 229, 0.2)',
          }}
        >
          <Plus size={16} /> Add domain
        </button>
      </div>

      {loadError && (
        <div
          style={{
            padding: '0.75rem 1rem',
            marginBottom: '1rem',
            background: 'var(--danger-light)',
            border: '1px solid var(--danger)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--danger)',
            fontSize: '13px',
          }}
        >
          {loadError}
        </div>
      )}

      {/* 3. TABULAR DOMAINS GRID */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md, 8px)',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-xs)',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              textAlign: 'left',
              fontSize: '13px',
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: '1px solid var(--border-color)',
                  background: '#FAFAFC',
                  color: 'var(--text-muted)',
                  fontWeight: 500,
                  userSelect: 'none',
                }}
              >
                {/* Domain & Last Modified */}
                <th
                  onClick={() => handleSort('name')}
                  style={{
                    padding: '10px 16px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    width: '28%',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    Domain & Last Modified
                    <ArrowUpDown size={12} style={{ opacity: 0.6 }} />
                  </div>
                </th>

                {/* Data Sources */}
                <th style={{ padding: '10px 14px', fontWeight: 500, width: '13%' }}>
                  Data Sources
                </th>

                {/* 30-day Activity */}
                <th
                  onClick={() => handleSort('activity_messages')}
                  style={{
                    padding: '10px 14px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    width: '18%',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    30-day Activity
                    <ArrowUpDown size={12} style={{ opacity: 0.6 }} />
                  </div>
                </th>

                {/* Dashboards */}
                <th
                  onClick={() => handleSort('dashboards_count')}
                  style={{
                    padding: '10px 12px',
                    fontWeight: 500,
                    textAlign: 'center',
                    cursor: 'pointer',
                    width: '9%',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                    Dashboards
                    <ArrowUpDown size={12} style={{ opacity: 0.6 }} />
                  </div>
                </th>

                {/* Agents */}
                <th
                  onClick={() => handleSort('agents_count')}
                  style={{
                    padding: '10px 12px',
                    fontWeight: 500,
                    textAlign: 'center',
                    cursor: 'pointer',
                    width: '7%',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                    Agents
                    <ArrowUpDown size={12} style={{ opacity: 0.6 }} />
                  </div>
                </th>

                {/* Users */}
                <th
                  onClick={() => handleSort('users_count')}
                  style={{
                    padding: '10px 12px',
                    fontWeight: 500,
                    textAlign: 'center',
                    cursor: 'pointer',
                    width: '7%',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                    Users
                    <ArrowUpDown size={12} style={{ opacity: 0.6 }} />
                  </div>
                </th>

                {/* Admins */}
                <th style={{ padding: '10px 14px', fontWeight: 500, width: '13%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    Admins
                    <ArrowUpDown size={12} style={{ opacity: 0.6 }} />
                  </div>
                </th>

                {/* Actions */}
                <th style={{ padding: '10px 16px', textAlign: 'right', fontWeight: 500, width: '5%' }}>
                  Actions
                </th>
              </tr>
            </thead>

            <tbody>
              {isLoading ? (
                // Loading Skeleton Rows
                [1, 2, 3, 4, 5].map((i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td colSpan={8} style={{ padding: '14px 16px' }}>
                      <div
                        className="skeleton"
                        style={{ height: '22px', width: '100%', borderRadius: '4px' }}
                      />
                    </td>
                  </tr>
                ))
              ) : paginatedDomains.length === 0 ? (
                // Empty state
                <tr>
                  <td colSpan={8} style={{ padding: '48px 16px', textAlign: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                      <Boxes size={36} style={{ color: 'var(--text-faint)', opacity: 0.5 }} />
                      <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                        {searchQuery ? 'No domains found matching your search' : 'No domains yet'}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '360px' }}>
                        {searchQuery
                          ? 'Try modifying your search or clearing your filters.'
                          : 'Create context-rich domains to ground your analytics and chat assistant.'}
                      </div>
                      {!searchQuery && (
                        <button
                          className="btn-primary"
                          onClick={openCreateModal}
                          style={{
                            marginTop: '8px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 14px',
                            fontSize: '13px',
                          }}
                        >
                          <Plus size={16} /> Add domain
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                // Data Rows
                paginatedDomains.map((domain) => {
                  const sources = domain.data_sources || (domain.source_name ? [domain.source_name] : []);
                  const dashCount = domain.dashboards_count ?? (domain.table_count ? Math.min(domain.table_count, 4) : 0);
                  const agentCount = domain.agents_count ?? 0;
                  const userCount = domain.users_count ?? 2;
                  const adminLabel = (domain.admins && domain.admins[0]) || 'Admin';

                  return (
                    <tr
                      key={domain.id}
                      onClick={() => openDomainDetail(domain)}
                      style={{
                        borderBottom: '1px solid var(--border-color)',
                        cursor: 'pointer',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#F8FAFC';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      {/* Column 1: Domain & Last Modified */}
                      <td style={{ padding: '12px 16px', verticalAlign: 'middle' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span
                            style={{
                              fontWeight: 600,
                              color: 'var(--text-main)',
                              fontSize: '13px',
                            }}
                          >
                            {domain.name}
                          </span>
                          {domain.description && (
                            <span
                              title={domain.description}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                color: 'var(--text-faint)',
                                cursor: 'help',
                              }}
                            >
                              <Info size={13} />
                            </span>
                          )}
                        </div>
                        <div
                          style={{
                            fontSize: '11px',
                            color: 'var(--text-faint)',
                            marginTop: '2px',
                          }}
                        >
                          {formatDateTime(domain.updated_at || domain.created_at)}
                        </div>
                      </td>

                      {/* Column 2: Data Sources */}
                      <td
                        onClick={(e) => {
                          e.stopPropagation();
                          openDomainDetail(domain, 'data-sources');
                        }}
                        style={{ padding: '12px 14px', verticalAlign: 'middle' }}
                      >
                        {sources.length === 0 ? (
                          <span style={{ color: 'var(--text-faint)', fontSize: '13px' }}>—</span>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                            {sources.map((src, i) => (
                              <div
                                key={i}
                                title={src}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  width: '24px',
                                  height: '24px',
                                  borderRadius: '4px',
                                  background: 'var(--bg-dark)',
                                }}
                              >
                                <SourceLogo type={src} size={16} />
                              </div>
                            ))}
                          </div>
                        )}
                      </td>

                      {/* Column 3: 30-day Activity */}
                      <td style={{ padding: '12px 14px', verticalAlign: 'middle' }}>
                        {/* Mini Activity Line / Sparkline */}
                        <div
                          style={{
                            width: '120px',
                            height: '3px',
                            borderRadius: '2px',
                            background: '#E2E8F0',
                            marginBottom: '6px',
                            overflow: 'hidden',
                          }}
                        >
                          <div
                            style={{
                              width: `${Math.min(100, Math.max(15, ((domain.activity_messages || 1) / 15) * 100))}%`,
                              height: '100%',
                              background: '#38BDF8',
                              borderRadius: '2px',
                            }}
                          />
                        </div>

                        {/* Metric Indicators */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            fontSize: '11px',
                            color: 'var(--text-faint)',
                          }}
                        >
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                            <MessageSquare size={11} /> {domain.activity_messages ?? 0}
                          </span>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                            <FileText size={11} /> {domain.activity_queries ?? domain.document_count ?? 0}
                          </span>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                            <ThumbsUp size={11} /> {domain.activity_thumbs_up ?? 0}
                          </span>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                            <ThumbsDown size={11} /> {domain.activity_thumbs_down ?? 0}
                          </span>
                        </div>
                      </td>

                      {/* Column 4: Dashboards */}
                      <td style={{ padding: '12px 12px', textAlign: 'center', verticalAlign: 'middle', color: 'var(--text-main)' }}>
                        {dashCount}
                      </td>

                      {/* Column 5: Agents */}
                      <td style={{ padding: '12px 12px', textAlign: 'center', verticalAlign: 'middle', color: 'var(--text-main)' }}>
                        {agentCount}
                      </td>

                      {/* Column 6: Users */}
                      <td style={{ padding: '12px 12px', textAlign: 'center', verticalAlign: 'middle' }}>
                        <span
                          style={{
                            color: 'var(--text-main)',
                            textDecoration: 'underline',
                            cursor: 'pointer',
                          }}
                        >
                          {userCount}
                        </span>
                      </td>

                      {/* Column 7: Admins */}
                      <td style={{ padding: '12px 14px', verticalAlign: 'middle', color: 'var(--text-main)', fontSize: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span style={{ maxWidth: '90px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {adminLabel}
                          </span>
                          <span style={{ color: 'var(--text-faint)', fontSize: '11px' }}>+1</span>
                        </div>
                      </td>

                      {/* Column 8: Actions */}
                      <td
                        style={{
                          padding: '12px 16px',
                          textAlign: 'right',
                          verticalAlign: 'middle',
                          position: 'relative',
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          className="btn-ghost"
                          onClick={() =>
                            setActiveMenuId(activeMenuId === domain.id ? null : domain.id)
                          }
                          style={{
                            padding: '4px',
                            borderRadius: 'var(--radius-sm)',
                            color: 'var(--text-muted)',
                          }}
                        >
                          <MoreVertical size={16} />
                        </button>

                        {/* Dropdown Menu */}
                        {activeMenuId === domain.id && (
                          <div
                            ref={menuRef}
                            style={{
                              position: 'absolute',
                              right: '16px',
                              top: '40px',
                              background: '#FFFFFF',
                              border: '1px solid var(--border-color)',
                              borderRadius: 'var(--radius-sm)',
                              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                              zIndex: 100,
                              minWidth: '150px',
                              padding: '4px 0',
                              textAlign: 'left',
                            }}
                          >
                            <button
                              onClick={() => {
                                setActiveMenuId(null);
                                openDomainDetail(domain);
                              }}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                width: '100%',
                                padding: '8px 12px',
                                fontSize: '12px',
                                color: 'var(--text-main)',
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.background = '#F1F5F9')}
                              onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                            >
                              <Edit2 size={14} /> Edit domain
                            </button>

                            <button
                              onClick={() => toggleHideDomain(domain.id)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                width: '100%',
                                padding: '8px 12px',
                                fontSize: '12px',
                                color: 'var(--text-main)',
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.background = '#F1F5F9')}
                              onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                            >
                              {domain.is_hidden ? <Eye size={14} /> : <EyeOff size={14} />}
                              {domain.is_hidden ? 'Unhide domain' : 'Hide domain'}
                            </button>

                            <button
                              onClick={() => deleteDomain(domain.id)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                width: '100%',
                                padding: '8px 12px',
                                fontSize: '12px',
                                color: 'var(--danger)',
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--danger-light)')}
                              onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                            >
                              <Trash2 size={14} /> Delete domain
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* 4. TABLE FOOTER / PAGINATION */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 16px',
            borderTop: '1px solid var(--border-color)',
            fontSize: '12px',
            color: 'var(--text-muted)',
            background: '#FFFFFF',
          }}
        >
          {/* Page Counter & Navigation */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              style={{
                background: 'none',
                border: 'none',
                cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                opacity: currentPage === 1 ? 0.3 : 0.8,
                padding: '2px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <ChevronLeft size={16} />
            </button>
            <span>
              Showing {filteredDomains.length === 0 ? 0 : (currentPage - 1) * rowsPerPage + 1} -{' '}
              {Math.min(currentPage * rowsPerPage, filteredDomains.length)} of {filteredDomains.length} domains
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              style={{
                background: 'none',
                border: 'none',
                cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
                opacity: currentPage >= totalPages ? 0.3 : 0.8,
                padding: '2px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <ChevronRight size={16} />
            </button>
          </div>

          {/* Rows per page selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Rows per page</span>
            <div style={{ position: 'relative' }}>
              <select
                value={rowsPerPage}
                onChange={(e) => {
                  setRowsPerPage(Number(e.target.value));
                  setCurrentPage(1);
                }}
                style={{
                  appearance: 'none',
                  padding: '4px 22px 4px 8px',
                  fontSize: '12px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-card)',
                  color: 'var(--text-main)',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
              <ChevronDown
                size={12}
                style={{
                  position: 'absolute',
                  right: '6px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  pointerEvents: 'none',
                  color: 'var(--text-faint)',
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 5. DOMAIN MODAL */}
      {isModalOpen && (
        <DomainModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={loadDomains}
          existingDomainId={selectedDomainId}
          existingDomainName={selectedDomainName}
        />
      )}
    </div>
  );
};
