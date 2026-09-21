import React, { useState, useEffect } from 'react';
import {
  Plus,
  Search,
  BookOpen,
  HelpCircle,
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Sparkles,
  Layers,
  GraduationCap,
  Hash,
  Languages,
  Code2,
  FolderPlus,
  RefreshCw,
  Download,
  Upload,
  MoreVertical,
  Info,
  Trash2,
  Check,
  Copy,
  SlidersHorizontal,
} from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { ConnectContextBuilderModal } from './ConnectContextBuilderModal';
import { AddKnowledgeModal } from './AddKnowledgeModal';
import { EditKnowledgeModal } from './EditKnowledgeModal';
import { AddMetricModal, type NewMetricData } from './AddMetricModal';
import { EditMetricModal } from './EditMetricModal';
import { fetchApi } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface ContextTabContentProps {
  domainId: string;
  domainName: string;
  documents?: any[];
  terms?: any[];
  onRefresh: () => void;
}

export const ContextTabContent: React.FC<ContextTabContentProps> = ({
  domainId,
  domainName,
  documents = [],
  terms = [],
  onRefresh,
}) => {
  const { user } = useAuth();
  const location = useLocation();
  const initialSubTab: 'builder' | 'knowledge' | 'queries' | 'metrics' | 'synonyms' | 'entities' | 'skills' =
    location.pathname.includes('/metrics')
      ? 'metrics'
      : location.pathname.includes('/knowledge')
      ? 'knowledge'
      : location.pathname.includes('/queries')
      ? 'queries'
      : location.pathname.includes('/synonyms')
      ? 'synonyms'
      : location.pathname.includes('/entities')
      ? 'entities'
      : location.pathname.includes('/skills')
      ? 'skills'
      : 'builder';

  const [activeSubTab, setActiveSubTab] = useState<
    'builder' | 'knowledge' | 'queries' | 'metrics' | 'synonyms' | 'entities' | 'skills'
  >(initialSubTab);

  // Modals for Builder & Knowledge
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [isAddKnowledgeModalOpen, setIsAddKnowledgeModalOpen] = useState(false);
  const [isEditKnowledgeModalOpen, setIsEditKnowledgeModalOpen] = useState(false);
  const [selectedEditItem, setSelectedEditItem] = useState<{
    id: string;
    text: string;
    author: string;
    modified_at: string;
  } | null>(null);

  // Modals for Metrics
  const [isAddMetricModalOpen, setIsAddMetricModalOpen] = useState(false);
  const [isEditMetricModalOpen, setIsEditMetricModalOpen] = useState(false);
  const [selectedEditMetric, setSelectedEditMetric] = useState<NewMetricData | null>(null);

  // Search & Filter states
  const [knowledgeSearch, setKnowledgeSearch] = useState('');
  const [metricSearch, setMetricSearch] = useState('');
  const [selectedKnowledgeIds, setSelectedKnowledgeIds] = useState<string[]>([]);
  const [selectedMetricIds, setSelectedMetricIds] = useState<string[]>([]);
  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [currentPage, setCurrentPage] = useState(1);
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [activeMetricMenuId, setActiveMetricMenuId] = useState<string | null>(null);
  const [workspaceSources, setWorkspaceSources] = useState<Array<{ id: string; name: string }>>([]);

  // Fetch workspace data sources from /sources
  useEffect(() => {
    fetchApi('/sources')
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const mapped = data.map((s: any) => ({
            id: String(s.id),
            name: s.name || s.database_name || `Connection ${s.id}`,
          }));
          setWorkspaceSources(mapped);
        }
      })
      .catch((err) => console.error('Failed to load workspace data sources:', err));
  }, []);

  // Close active dropdown menus on outside click
  useEffect(() => {
    const handleOutsideClick = () => {
      if (activeMenuId) setActiveMenuId(null);
      if (activeMetricMenuId) setActiveMetricMenuId(null);
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, [activeMenuId, activeMetricMenuId]);

  // Auto-refresh if any uploaded document is pending/processing
  useEffect(() => {
    const hasPendingDocs = documents.some(
      (doc) => doc && (doc.processing_status === 'pending' || doc.processing_status === 'processing')
    );
    if (!hasPendingDocs) return;

    let pollCount = 0;
    const interval = setInterval(() => {
      pollCount += 1;
      if (pollCount > 20) {
        clearInterval(interval);
        return;
      }
      onRefresh();
    }, 3500);

    return () => clearInterval(interval);
  }, [documents, onRefresh]);

  // Helper to format user display name from email
  const formatAuthorName = (emailOrName?: string) => {
    if (!emailOrName) {
      if (user?.email) {
        const prefix = user.email.split('@')[0];
        const parts = prefix.replace(/[._-]/g, ' ').split(/\s+/).filter(Boolean);
        if (parts.length > 0) {
          return parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(' ');
        }
      }
      return 'Shailesh Kulkarni';
    }
    if (emailOrName.includes('@')) {
      const prefix = emailOrName.split('@')[0];
      const parts = prefix.replace(/[._-]/g, ' ').split(/\s+/).filter(Boolean);
      if (parts.length > 0) {
        return parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(' ');
      }
    }
    return emailOrName;
  };

  const currentUserAuthor = formatAuthorName();

  // Group terms & counts
  const knowledgeTerms = (terms || []).filter(
    (t) => t.category === 'knowledge' || !t.category || t.category === 'general'
  );
  
  const knowledgeCount = knowledgeTerms.length;
  const synonymsCount = (terms || []).filter((t) => (t.synonyms && t.synonyms.length > 0) || t.category === 'synonym').length;
  const entitiesCount = (terms || []).filter((t) => t.category === 'entity').length;
  const reviewedQueriesCount = (terms || []).filter((t) => t.category === 'reviewed_query' || t.category === 'query').length;
  const skillsCount = (terms || []).filter((t) => t.category === 'skill').length;

  // -------------------------------------------------------------------------
  // REAL-TIME METRICS (Loaded directly from backend domain terms)
  // -------------------------------------------------------------------------
  const parseBackendMetric = (t: any, idx: number): NewMetricData => {
    let parsedDef: any = {};
    try {
      parsedDef = typeof t.definition === 'string' ? JSON.parse(t.definition || '{}') : (t.definition || {});
    } catch {
      parsedDef = { description: t.definition };
    }
    return {
      id: t.id || `metric-db-${idx}`,
      name: t.term || 'Untitled Metric',
      tables: parsedDef.tables || parsedDef.table_name || '',
      definitionType: parsedDef.definition_type || 'SQL',
      connection: parsedDef.connection || '',
      englishDescription: parsedDef.description || (typeof t.definition === 'string' ? t.definition : '') || '',
      sql: parsedDef.sql || '',
      displayFormat: parsedDef.display_format || 'Automatic',
      isIncluded: parsedDef.is_included !== undefined ? parsedDef.is_included : true,
      status: parsedDef.status || 'Stale',
    };
  };

  // Local state for user-added / modified metrics
  const [metricsList, setMetricsList] = useState<NewMetricData[]>(() => {
    return (terms || [])
      .filter((t) => t.category === 'metric')
      .map((t, idx) => parseBackendMetric(t, idx));
  });

  // Keep metrics in sync when terms change
  useEffect(() => {
    const backendMetrics: NewMetricData[] = (terms || [])
      .filter((t) => t.category === 'metric')
      .map((t, idx) => parseBackendMetric(t, idx));

    setMetricsList(backendMetrics);
  }, [terms]);

  const metricsCount = metricsList.length;

  // Toggle Included switch for metric
  const toggleMetricInclusion = (id?: string) => {
    if (!id) return;
    setMetricsList((prev) =>
      prev.map((m) => (m.id === id ? { ...m, isIncluded: !m.isIncluded } : m))
    );
  };

  // Update display format for metric
  const handleUpdateDisplayFormat = (id: string, format: string) => {
    setMetricsList((prev) =>
      prev.map((m) => (m.id === id ? { ...m, displayFormat: format } : m))
    );
  };

  // Add new metric handler
  const handleAddMetricSuccess = (newMetric: NewMetricData) => {
    setMetricsList((prev) => [newMetric, ...prev]);
    onRefresh();
  };

  // Delete metric handler
  const handleDeleteMetric = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this metric?')) return;
    setMetricsList((prev) => prev.filter((m) => m.id !== id));
    setSelectedMetricIds((prev) => prev.filter((item) => item !== id));
    setActiveMetricMenuId(null);

    if (id) {
      try {
        await fetchApi(`/domains/${domainId}/terms/${id}`, {
          method: 'DELETE',
        });
      } catch (err) {
        console.error('Failed to delete metric from server:', err);
      }
    }
    onRefresh();
  };

  // Filtered metrics by search query
  const filteredMetrics = metricsList.filter((m) => {
    const q = metricSearch.toLowerCase().trim();
    if (!q) return true;
    return (
      m.name.toLowerCase().includes(q) ||
      (m.englishDescription && m.englishDescription.toLowerCase().includes(q)) ||
      (m.tables && m.tables.toLowerCase().includes(q)) ||
      (m.definitionType && m.definitionType.toLowerCase().includes(q)) ||
      (m.sql && m.sql.toLowerCase().includes(q))
    );
  });

  // Toggle select all metrics
  const toggleSelectAllMetrics = () => {
    if (selectedMetricIds.length === filteredMetrics.length) {
      setSelectedMetricIds([]);
    } else {
      setSelectedMetricIds(filteredMetrics.map((m) => m.id || m.name));
    }
  };

  // Toggle select single metric
  const toggleSelectMetric = (id: string) => {
    setSelectedMetricIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // Export metrics to CSV
  const handleExportMetrics = () => {
    const headers = ['Name', 'Tables', 'Type', 'Description', 'SQL', 'Display Format', 'Included'];
    const rows = filteredMetrics.map((m) => [
      `"${m.name.replace(/"/g, '""')}"`,
      `"${(m.tables || '').replace(/"/g, '""')}"`,
      `"${(m.definitionType || 'SQL').replace(/"/g, '""')}"`,
      `"${(m.englishDescription || '').replace(/"/g, '""')}"`,
      `"${(m.sql || '').replace(/"/g, '""')}"`,
      `"${(m.displayFormat || 'Automatic').replace(/"/g, '""')}"`,
      m.isIncluded ? 'Yes' : 'No',
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${domainName.toLowerCase().replace(/\s+/g, '_')}_metrics.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Build runs list for Builder Tab
  const defaultRuns = [
    {
      id: 'run-1',
      file_name: 'distributor_analytics.docx',
      created_at: 'Apr 17, 2026, 05:52 PM',
      source_tag: 'Wisdom Internal',
      status: 'failed',
      duration: '< 1m',
      files_count: 1,
      report: 'No suggestions',
    },
    {
      id: 'run-2',
      file_name: 'distributor_analytics.docx',
      created_at: 'Apr 17, 2026, 05:50 PM',
      source_tag: 'Wisdom Internal',
      status: 'failed',
      duration: '< 1m',
      files_count: 1,
      report: 'No suggestions',
    },
  ];

  const actualRuns = [...documents].reverse().map((doc, idx) => {
    let formattedDate = 'Recently uploaded';
    if (doc.created_at) {
      try {
        formattedDate = new Date(doc.created_at).toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        });
      } catch {
        formattedDate = String(doc.created_at);
      }
    }

    const isComplete = doc.processing_status === 'complete';
    const isFailed = doc.processing_status === 'failed' || doc.processing_status === 'error';
    let cleanFileName = doc.file_name || 'document.docx';
    cleanFileName = cleanFileName.replace(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[-_]/i, '');

    return {
      id: doc.id || `doc-${idx}`,
      file_name: cleanFileName,
      created_at: formattedDate,
      source_tag: 'Uploaded File',
      status: isComplete ? 'success' : isFailed ? 'failed' : 'processing',
      duration: '< 1m',
      files_count: 1,
      report: isComplete ? `${doc.chunk_count || 1} chunks indexed` : isFailed ? 'Failed indexing' : 'Indexing...',
    };
  });

  const runsList = actualRuns;
  const totalRuns = runsList.length;

  // Default Knowledge Item
  const defaultKnowledgeText = `You are working on a distribution and field-service analytics platform for an industrial aftermarket spare parts company. The business operates through a multi-tier supply chain:
- Warehouses (depots) stock products
- Distributors procure from warehouses
- Retailers procure from distributors
- Technicians & service centers order parts for maintenance and repairs

Sales & Revenue Metrics:
- Quantity sold
- Gross sales
- Net sales
- Discount amount
- Tax amount
- Invoice count
- Average order value

Inventory Metrics:
- Available stock
- Reserved stock
- In-transit stock
- Reorder point
- Safety stock level
- Backorder quantity

Service & Maintenance Metrics:
- First-time fix rate (FTFR)
- Mean time to repair (MTTR)
- SLA compliance rate
- Warranty claims volume`;

  const [deletedKnowledgeIds, setDeletedKnowledgeIds] = useState<string[]>([]);

  const actualKnowledgeItems = knowledgeTerms.map((t) => {
    let formattedDate = 'Just now';
    if (t.updated_at || t.created_at) {
      try {
        const d = new Date(t.updated_at || t.created_at);
        formattedDate = d.toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
          hour12: true,
        });
      } catch {
        formattedDate = 'Just now';
      }
    }
    return {
      id: t.id,
      text: t.definition || t.term,
      author: t.created_by_name ? formatAuthorName(t.created_by_name) : currentUserAuthor,
      modified_at: formattedDate,
    };
  });

  const allKnowledgeItems = actualKnowledgeItems.filter((item) => !deletedKnowledgeIds.includes(item.id));

  const filteredKnowledge = allKnowledgeItems.filter((item) =>
    item.text.toLowerCase().includes(knowledgeSearch.toLowerCase())
  );

  const toggleSelectAllKnowledge = () => {
    if (selectedKnowledgeIds.length === filteredKnowledge.length) {
      setSelectedKnowledgeIds([]);
    } else {
      setSelectedKnowledgeIds(filteredKnowledge.map((k) => k.id));
    }
  };

  const toggleSelectKnowledge = (id: string) => {
    setSelectedKnowledgeIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleDeleteKnowledge = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this knowledge item?')) return;
    try {
      setDeletedKnowledgeIds((prev) => [...prev, id]);
      setSelectedKnowledgeIds((prev) => prev.filter((item) => item !== id));
      setActiveMenuId(null);
      if (!id.startsWith('know-default')) {
        await fetchApi(`/domains/${domainId}/terms/${id}`, {
          method: 'DELETE',
        });
      }
      onRefresh();
    } catch (err) {
      console.error('Failed to delete term:', err);
    }
  };

  const handleBulkDeleteKnowledge = async () => {
    if (selectedKnowledgeIds.length === 0) return;
    if (!window.confirm(`Are you sure you want to delete ${selectedKnowledgeIds.length} knowledge item(s)?`)) return;

    const idsToDelete = [...selectedKnowledgeIds];
    setDeletedKnowledgeIds((prev) => [...prev, ...idsToDelete]);
    setSelectedKnowledgeIds([]);

    for (const id of idsToDelete) {
      if (!id.startsWith('know-default')) {
        try {
          await fetchApi(`/domains/${domainId}/terms/${id}`, {
            method: 'DELETE',
          });
        } catch (err) {
          console.error('Failed to delete term:', id, err);
        }
      }
    }
    onRefresh();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* ========================================================================= */}
      {/* 1. SUB-NAV PILL BAR (MATCHES SCREENSHOT EXACTLY) */}
      {/* ========================================================================= */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          overflowX: 'auto',
          paddingBottom: '2px',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Sub Tab: Context Builder */}
          <button
            onClick={() => setActiveSubTab('builder')}
            style={{
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: activeSubTab === 'builder' ? 600 : 500,
              color: activeSubTab === 'builder' ? '#1E293B' : '#475569',
              background: activeSubTab === 'builder' ? '#FFFFFF' : '#EEF2F6',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
              boxShadow: activeSubTab === 'builder' ? '0 1px 3px rgba(0,0,0,0.04)' : 'none',
            }}
          >
            Context Builder
          </button>

          {/* Sub Tab: Knowledge */}
          <button
            onClick={() => setActiveSubTab('knowledge')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: activeSubTab === 'knowledge' ? 600 : 500,
              color: activeSubTab === 'knowledge' ? '#1E293B' : '#475569',
              background: activeSubTab === 'knowledge' ? '#FFFFFF' : '#EEF2F6',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
              boxShadow: activeSubTab === 'knowledge' ? '0 1px 3px rgba(0,0,0,0.04)' : 'none',
            }}
          >
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#6366F1' }}>T*</span>
            <span>Knowledge</span>
            <span style={{ color: '#2563EB', fontWeight: 600, fontSize: '12.5px' }}>({knowledgeCount})</span>
          </button>

          {/* Sub Tab: Reviewed Queries */}
          <button
            onClick={() => setActiveSubTab('queries')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: activeSubTab === 'queries' ? 600 : 500,
              color: activeSubTab === 'queries' ? '#1E293B' : '#475569',
              background: activeSubTab === 'queries' ? '#FFFFFF' : '#EEF2F6',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
              boxShadow: activeSubTab === 'queries' ? '0 1px 3px rgba(0,0,0,0.04)' : 'none',
            }}
          >
            <Code2 size={14} style={{ color: '#64748B' }} />
            <span>Reviewed Queries</span>
            <span style={{ color: '#2563EB', fontWeight: 600, fontSize: '12.5px' }}>({reviewedQueriesCount})</span>
          </button>

          {/* Sub Tab: Metrics (MATCHES SCREENSHOT) */}
          <button
            onClick={() => setActiveSubTab('metrics')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: activeSubTab === 'metrics' ? 600 : 500,
              color: activeSubTab === 'metrics' ? '#1E293B' : '#475569',
              background: activeSubTab === 'metrics' ? '#FFFFFF' : '#EEF2F6',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
              boxShadow: activeSubTab === 'metrics' ? '0 1px 3px rgba(0,0,0,0.04)' : 'none',
            }}
          >
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', letterSpacing: '-0.5px' }}>123</span>
            <span>Metrics</span>
            <span style={{ color: '#2563EB', fontWeight: 600, fontSize: '12.5px' }}>({metricsCount})</span>
          </button>

          {/* Sub Tab: Synonyms */}
          <button
            onClick={() => setActiveSubTab('synonyms')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: activeSubTab === 'synonyms' ? 600 : 500,
              color: activeSubTab === 'synonyms' ? '#1E293B' : '#475569',
              background: activeSubTab === 'synonyms' ? '#FFFFFF' : '#EEF2F6',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
              boxShadow: activeSubTab === 'synonyms' ? '0 1px 3px rgba(0,0,0,0.04)' : 'none',
            }}
          >
            <Languages size={14} style={{ color: '#64748B' }} />
            <span>Synonyms</span>
            <span style={{ color: '#2563EB', fontWeight: 600, fontSize: '12.5px' }}>({synonymsCount})</span>
          </button>

          {/* Sub Tab: Entities */}
          <button
            onClick={() => setActiveSubTab('entities')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: activeSubTab === 'entities' ? 600 : 500,
              color: activeSubTab === 'entities' ? '#1E293B' : '#475569',
              background: activeSubTab === 'entities' ? '#FFFFFF' : '#EEF2F6',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
              boxShadow: activeSubTab === 'entities' ? '0 1px 3px rgba(0,0,0,0.04)' : 'none',
            }}
          >
            <Layers size={14} style={{ color: '#64748B' }} />
            <span>Entities</span>
            <span style={{ color: '#2563EB', fontWeight: 600, fontSize: '12.5px' }}>({entitiesCount})</span>
          </button>

          {/* Sub Tab: Skills */}
          <button
            onClick={() => setActiveSubTab('skills')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: activeSubTab === 'skills' ? 600 : 500,
              color: activeSubTab === 'skills' ? '#1E293B' : '#475569',
              background: activeSubTab === 'skills' ? '#FFFFFF' : '#EEF2F6',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
              boxShadow: activeSubTab === 'skills' ? '0 1px 3px rgba(0,0,0,0.04)' : 'none',
            }}
          >
            <GraduationCap size={14} style={{ color: '#64748B' }} />
            <span>Skills</span>
            <span style={{ color: '#2563EB', fontWeight: 600, fontSize: '12.5px' }}>({skillsCount})</span>
          </button>
        </div>

        {/* Right Action Icons in Sub-nav (Search & Libraries) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
          <button
            title="Search context"
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: '#64748B',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#1E293B')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#64748B')}
          >
            <Search size={16} />
          </button>

          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '6px',
              background: '#EEF2FF',
              color: '#4F46E5',
              border: '1px solid #E0E7FF',
              fontSize: '12.5px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#E0E7FF')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#EEF2FF')}
          >
            <BookOpen size={14} />
            <span>Libraries</span>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. SUB-VIEW: CONTEXT BUILDER */}
      {/* ========================================================================= */}
      {activeSubTab === 'builder' && (
        <div
          style={{
            background: '#FFFFFF',
            borderRadius: '8px',
            padding: '24px 28px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          {/* Header Message & Action Button */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
            }}
          >
            <div style={{ fontSize: '13.5px', color: '#1E293B', fontWeight: 600 }}>
              To create <span style={{ textDecoration: 'underline', cursor: 'pointer' }} onClick={() => setIsConnectModalOpen(true)}>context</span> for your domain, add or connect files.
            </div>

            <button
              onClick={() => setIsConnectModalOpen(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: '6px',
                background: '#4F46E5',
                color: '#FFFFFF',
                border: 'none',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 1px 2px rgba(79, 70, 229, 0.2)',
                transition: 'background-color 0.15s ease',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#4338CA')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#4F46E5')}
            >
              <Plus size={15} />
              <span>Build context</span>
            </button>
          </div>

          {/* Stats Bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '20px',
              fontSize: '13px',
              color: '#1E293B',
              fontWeight: 500,
            }}
          >
            <span>
              Runs <strong style={{ fontWeight: 700, color: '#1E293B' }}>{totalRuns}</strong>
            </span>
            <span>
              Accepted Suggestions <strong style={{ fontWeight: 700, color: '#16A34A' }}>0</strong>
            </span>
            <span>
              For Review <strong style={{ fontWeight: 700, color: '#2563EB' }}>0</strong>
            </span>
            <span>
              Declined <strong style={{ fontWeight: 700, color: '#2563EB' }}>0</strong>
            </span>
          </div>

          {/* Context Builds Table Container */}
          <div
            style={{
              background: '#FFFFFF',
              borderTop: '1px solid #E2E8F0',
              overflow: 'hidden',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#64748B', fontWeight: 600, fontSize: '12px' }}>
                  <th style={{ padding: '12px 16px', width: '90px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      <span>Connection</span>
                      <span style={{ fontSize: '10px' }}>↕</span>
                    </div>
                  </th>
                  <th style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      <span>Context builds</span>
                      <span style={{ fontSize: '10px' }}>↕</span>
                    </div>
                  </th>
                  <th style={{ padding: '12px 16px', width: '120px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      <span>Status</span>
                      <span style={{ fontSize: '10px' }}>↕</span>
                    </div>
                  </th>
                  <th style={{ padding: '12px 16px', width: '100px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      <span>Duration</span>
                      <span style={{ fontSize: '10px' }}>↕</span>
                    </div>
                  </th>
                  <th style={{ padding: '12px 16px', width: '80px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      <span>Files</span>
                      <span style={{ fontSize: '10px' }}>↕</span>
                    </div>
                  </th>
                  <th style={{ padding: '12px 16px', width: '140px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      <span>Report</span>
                      <span style={{ fontSize: '10px' }}>↕</span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {runsList.map((run, idx) => (
                  <tr
                    key={run.id || idx}
                    style={{
                      borderBottom: idx === runsList.length - 1 ? 'none' : '1px solid #F1F5F9',
                      transition: 'background-color 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: '14px 16px' }}>
                      <div
                        style={{
                          width: '28px',
                          height: '28px',
                          borderRadius: '6px',
                          background: '#F8FAFC',
                          border: '1px solid #E2E8F0',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#64748B',
                        }}
                      >
                        <FileText size={15} />
                      </div>
                    </td>

                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <span style={{ fontWeight: 600, color: '#1E293B', cursor: 'pointer' }}>
                          {run.file_name}
                        </span>
                        <span style={{ fontSize: '11.5px', color: '#94A3B8' }}>
                          {run.created_at} · {run.source_tag}
                        </span>
                      </div>
                    </td>

                    <td style={{ padding: '14px 16px' }}>
                      {run.status === 'failed' && (
                        <div
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '3px 8px',
                            borderRadius: '12px',
                            background: '#FEF2F2',
                            border: '1px solid #FEE2E2',
                            color: '#DC2626',
                            fontSize: '11.5px',
                            fontWeight: 600,
                          }}
                        >
                          <span>Failed</span>
                          <HelpCircle size={12} style={{ color: '#EF4444' }} />
                        </div>
                      )}
                      {run.status === 'success' && (
                        <div
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '3px 8px',
                            borderRadius: '12px',
                            background: '#F0FDF4',
                            border: '1px solid #DCFCE7',
                            color: '#16A34A',
                            fontSize: '11.5px',
                            fontWeight: 600,
                          }}
                        >
                          <CheckCircle2 size={12} />
                          <span>Success</span>
                        </div>
                      )}
                      {run.status === 'processing' && (
                        <div
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '3px 8px',
                            borderRadius: '12px',
                            background: '#EFF6FF',
                            border: '1px solid #DBEAFE',
                            color: '#2563EB',
                            fontSize: '11.5px',
                            fontWeight: 600,
                          }}
                        >
                          <RefreshCw size={12} className="animate-spin" />
                          <span>Processing</span>
                        </div>
                      )}
                    </td>

                    <td style={{ padding: '14px 16px', color: '#64748B', fontSize: '12.5px' }}>
                      {run.duration}
                    </td>

                    <td style={{ padding: '14px 16px', color: '#64748B', fontSize: '12.5px' }}>
                      {run.files_count}
                    </td>

                    <td style={{ padding: '14px 16px', color: '#64748B', fontSize: '12.5px' }}>
                      {run.report}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Table Pagination Footer */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                background: '#FFFFFF',
                borderTop: '1px solid #E2E8F0',
                fontSize: '12.5px',
                color: '#64748B',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  disabled={currentPage === 1}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                    color: currentPage === 1 ? '#CBD5E1' : '#64748B',
                    padding: '2px',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <ChevronLeft size={16} />
                </button>
                <span>
                  Showing 1 - {totalRuns} of {totalRuns} runs
                </span>
                <button
                  disabled
                  style={{
                    background: 'transparent',
                    border: 'none',
                    cursor: 'not-allowed',
                    color: '#CBD5E1',
                    padding: '2px',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <ChevronRight size={16} />
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>Rows per page</span>
                <select
                  value={rowsPerPage}
                  onChange={(e) => setRowsPerPage(Number(e.target.value))}
                  style={{
                    border: '1px solid #CBD5E1',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '12px',
                    background: '#FFFFFF',
                    color: '#334155',
                  }}
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. SUB-VIEW: KNOWLEDGE TAB */}
      {/* ========================================================================= */}
      {activeSubTab === 'knowledge' && (
        <div
          style={{
            background: '#FFFFFF',
            borderRadius: '8px',
            padding: '24px 28px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexWrap: 'wrap',
            }}
          >
            {/* Search knowledge input */}
            <div style={{ position: 'relative', width: '280px' }}>
              <input
                type="text"
                placeholder="Search knowledge items"
                value={knowledgeSearch}
                onChange={(e) => setKnowledgeSearch(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 36px 9px 14px',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  fontSize: '13px',
                  boxSizing: 'border-box',
                  background: '#FFFFFF',
                  outline: 'none',
                  transition: 'border-color 0.15s ease',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = '#6366F1')}
                onBlur={(e) => (e.currentTarget.style.borderColor = '#E2E8F0')}
              />
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#94A3B8',
                }}
              />
            </div>

            {/* Right Tools & Action Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={onRefresh}
                title="Refresh knowledge"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  background: '#FFFFFF',
                  color: '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#F8FAFC';
                  e.currentTarget.style.color = '#1E293B';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.color = '#64748B';
                }}
              >
                <RefreshCw size={18} />
              </button>

              <button
                title="Export knowledge"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  background: '#FFFFFF',
                  color: '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#F8FAFC';
                  e.currentTarget.style.color = '#1E293B';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.color = '#64748B';
                }}
              >
                <Download size={18} />
              </button>

              <button
                title="Import knowledge"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  background: '#FFFFFF',
                  color: '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#F8FAFC';
                  e.currentTarget.style.color = '#1E293B';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.color = '#64748B';
                }}
              >
                <Upload size={18} />
              </button>

              {selectedKnowledgeIds.length > 0 && (
                <button
                  onClick={handleBulkDeleteKnowledge}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    borderRadius: '6px',
                    background: '#FEF2F2',
                    color: '#DC2626',
                    border: '1px solid #FECACA',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <Trash2 size={14} />
                  <span>Delete ({selectedKnowledgeIds.length})</span>
                </button>
              )}

              <button
                onClick={() => setIsAddKnowledgeModalOpen(true)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  background: '#4F46E5',
                  color: '#FFFFFF',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  boxShadow: '0 1px 2px rgba(79, 70, 229, 0.2)',
                  transition: 'background-color 0.15s ease',
                  marginLeft: '4px',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#4338CA')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#4F46E5')}
              >
                <Plus size={15} />
                <span>Add Knowledge</span>
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px', fontWeight: 600, color: '#1E293B', marginTop: '4px' }}>
            <span>Knowledge</span>
            <Info size={14} style={{ color: '#94A3B8', cursor: 'pointer' }} />
          </div>

          <div
            style={{
              background: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#64748B', fontWeight: 600, fontSize: '12px' }}>
                  <th style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <input
                        type="checkbox"
                        checked={selectedKnowledgeIds.length > 0 && selectedKnowledgeIds.length === filteredKnowledge.length}
                        onChange={toggleSelectAllKnowledge}
                        style={{ cursor: 'pointer', width: '15px', height: '15px', accentColor: '#4F46E5' }}
                      />
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <span>Knowledge</span>
                        <span style={{ fontSize: '10px' }}>↕</span>
                      </div>
                    </div>
                  </th>
                  <th style={{ padding: '12px 16px', width: '280px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      <span>Last modified</span>
                      <span style={{ fontSize: '10px' }}>↕</span>
                    </div>
                  </th>
                  <th style={{ width: '40px', padding: '12px' }}></th>
                </tr>
              </thead>
              <tbody>
                {filteredKnowledge.length === 0 ? (
                  <tr>
                    <td colSpan={3} style={{ padding: '32px 16px', textAlign: 'center', color: '#94A3B8', fontSize: '13px' }}>
                      No knowledge items found matching your search.
                    </td>
                  </tr>
                ) : (
                  filteredKnowledge.map((item, idx) => (
                    <tr
                      key={item.id || idx}
                      style={{
                        borderBottom: idx === filteredKnowledge.length - 1 ? 'none' : '1px solid #F1F5F9',
                        transition: 'background-color 0.15s ease',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                    >
                      <td
                        style={{ padding: '16px 16px', verticalAlign: 'top', cursor: 'pointer' }}
                        onClick={(e) => {
                          if ((e.target as HTMLElement).tagName === 'INPUT') return;
                          setSelectedEditItem(item);
                          setIsEditKnowledgeModalOpen(true);
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                          <input
                            type="checkbox"
                            checked={selectedKnowledgeIds.includes(item.id)}
                            onChange={() => toggleSelectKnowledge(item.id)}
                            style={{ cursor: 'pointer', marginTop: '3px', width: '15px', height: '15px', accentColor: '#4F46E5' }}
                          />
                          <div style={{ flex: 1, paddingRight: '16px', fontSize: '13px', color: '#1E293B', lineHeight: 1.6 }}>
                            {item.text}
                          </div>
                        </div>
                      </td>

                      <td
                        style={{ padding: '16px 16px', verticalAlign: 'top', fontSize: '12.5px', color: '#64748B', cursor: 'pointer' }}
                        onClick={() => {
                          setSelectedEditItem(item);
                          setIsEditKnowledgeModalOpen(true);
                        }}
                      >
                        <span>{item.author} at {item.modified_at}</span>
                      </td>

                      <td style={{ padding: '16px 8px', verticalAlign: 'top', textAlign: 'right', position: 'relative' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveMenuId(activeMenuId === item.id ? null : item.id);
                          }}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            color: '#94A3B8',
                            padding: '4px',
                            borderRadius: '4px',
                          }}
                        >
                          <MoreVertical size={16} />
                        </button>

                        {activeMenuId === item.id && (
                          <div
                            style={{
                              position: 'absolute',
                              top: 'calc(100% - 8px)',
                              right: '8px',
                              background: '#FFFFFF',
                              border: '1px solid #E2E8F0',
                              borderRadius: '6px',
                              boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)',
                              zIndex: 100,
                              minWidth: '110px',
                              overflow: 'hidden',
                            }}
                          >
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedEditItem(item);
                                setIsEditKnowledgeModalOpen(true);
                                setActiveMenuId(null);
                              }}
                              style={{
                                width: '100%',
                                padding: '8px 12px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                border: 'none',
                                background: 'transparent',
                                color: '#1E293B',
                                fontSize: '12.5px',
                                cursor: 'pointer',
                                textAlign: 'left',
                              }}
                            >
                              <span>Edit</span>
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteKnowledge(item.id);
                                setActiveMenuId(null);
                              }}
                              style={{
                                width: '100%',
                                padding: '8px 12px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                border: 'none',
                                background: 'transparent',
                                color: '#DC2626',
                                fontSize: '12.5px',
                                cursor: 'pointer',
                                textAlign: 'left',
                              }}
                            >
                              <Trash2 size={13} />
                              <span>Delete</span>
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 4. SUB-VIEW: METRICS TAB (MATCHES EXACT ATTACHED SCREENSHOT) */}
      {/* ========================================================================= */}
      {activeSubTab === 'metrics' && (
        <div
          style={{
            background: '#FFFFFF',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          {/* Top Action Bar: Search Input on Left, Tools & + Add Metric Button on Right */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexWrap: 'wrap',
            }}
          >
            {/* Search metrics input */}
            <div style={{ position: 'relative', width: '280px' }}>
              <input
                type="text"
                placeholder="Search Metrics"
                value={metricSearch}
                onChange={(e) => setMetricSearch(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 36px 9px 14px',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  fontSize: '13px',
                  boxSizing: 'border-box',
                  background: '#FFFFFF',
                  outline: 'none',
                  transition: 'border-color 0.15s ease',
                  color: '#1E293B',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = '#4F46E5')}
                onBlur={(e) => (e.currentTarget.style.borderColor = '#E2E8F0')}
              />
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#94A3B8',
                  pointerEvents: 'none',
                }}
              />
            </div>

            {/* Right Tools & + Add Metric Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {/* Refresh icon button */}
              <button
                onClick={onRefresh}
                title="Refresh metrics"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  background: '#FFFFFF',
                  color: '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#F8FAFC';
                  e.currentTarget.style.color = '#1E293B';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.color = '#64748B';
                }}
              >
                <RefreshCw size={18} />
              </button>

              {/* Download / Export icon button */}
              <button
                onClick={handleExportMetrics}
                title="Export metrics to CSV"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  background: '#FFFFFF',
                  color: '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#F8FAFC';
                  e.currentTarget.style.color = '#1E293B';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.color = '#64748B';
                }}
              >
                <Download size={18} />
              </button>

              {/* Upload / Import icon button */}
              <button
                title="Import metrics"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: '1px solid #E2E8F0',
                  background: '#FFFFFF',
                  color: '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#F8FAFC';
                  e.currentTarget.style.color = '#1E293B';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.color = '#64748B';
                }}
              >
                <Upload size={18} />
              </button>

              {/* Bulk Delete button */}
              {selectedMetricIds.length > 0 && (
                <button
                  onClick={() => {
                    if (window.confirm(`Delete ${selectedMetricIds.length} selected metric(s)?`)) {
                      setMetricsList((prev) => prev.filter((m) => !selectedMetricIds.includes(m.id || m.name)));
                      setSelectedMetricIds([]);
                    }
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    borderRadius: '6px',
                    background: '#FEF2F2',
                    color: '#DC2626',
                    border: '1px solid #FECACA',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  <Trash2 size={14} />
                  <span>Delete ({selectedMetricIds.length})</span>
                </button>
              )}

              {/* + Add Metric Primary Button */}
              <button
                onClick={() => setIsAddMetricModalOpen(true)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 18px',
                  borderRadius: '6px',
                  background: '#4F46E5',
                  color: '#FFFFFF',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  boxShadow: '0 1px 2px rgba(79, 70, 229, 0.2)',
                  transition: 'background-color 0.15s ease',
                  marginLeft: '4px',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#4338CA')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#4F46E5')}
              >
                <Plus size={16} />
                <span>Add Metric</span>
              </button>
            </div>
          </div>

          {/* Section Header: Metrics with Info Icon */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px', fontWeight: 600, color: '#1E293B', marginTop: '2px' }}>
            <span>Metrics</span>
            <Info size={14} style={{ color: '#94A3B8', cursor: 'pointer' }} />
          </div>

          {/* Metrics Table */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}
          >
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '980px' }}>
                <thead>
                  <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#64748B', fontWeight: 600, fontSize: '12px' }}>
                    {/* Checkbox */}
                    <th style={{ width: '40px', padding: '12px 14px' }}>
                      <input
                        type="checkbox"
                        checked={selectedMetricIds.length > 0 && selectedMetricIds.length === filteredMetrics.length}
                        onChange={toggleSelectAllMetrics}
                        style={{ cursor: 'pointer', width: '15px', height: '15px', accentColor: '#4F46E5' }}
                      />
                    </th>

                    {/* Included Column Header */}
                    <th style={{ width: '100px', padding: '12px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <span>Included</span>
                        <span style={{ fontSize: '10px' }}>↕</span>
                      </div>
                    </th>

                    {/* Name Column Header */}
                    <th style={{ padding: '12px 14px', minWidth: '220px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <span>Name</span>
                        <span style={{ fontSize: '10px' }}>↕</span>
                      </div>
                    </th>

                    {/* Tables Column Header */}
                    <th style={{ padding: '12px 14px', width: '160px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <span>Tables</span>
                        <span style={{ fontSize: '10px' }}>↕</span>
                      </div>
                    </th>

                    {/* Type Column Header */}
                    <th style={{ padding: '12px 14px', width: '90px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <span>Type</span>
                        <span style={{ fontSize: '10px' }}>↕</span>
                      </div>
                    </th>

                    {/* Description Column Header */}
                    <th style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <span>Description</span>
                        <span style={{ fontSize: '10px' }}>↕</span>
                      </div>
                    </th>

                    {/* Display format Column Header */}
                    <th style={{ padding: '12px 14px', width: '150px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <span>Display format</span>
                        <span style={{ fontSize: '10px' }}>↕</span>
                      </div>
                    </th>

                    {/* Options */}
                    <th style={{ width: '38px', padding: '12px 8px' }}></th>
                  </tr>
                </thead>

                <tbody>
                  {filteredMetrics.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ padding: '48px 16px', textAlign: 'center' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '13.5px', fontWeight: 600, color: '#1E293B' }}>
                            {metricSearch ? 'No metrics match your search' : 'No metrics defined yet'}
                          </span>
                          <span style={{ fontSize: '12.5px', color: '#64748B', maxWidth: '380px' }}>
                            {metricSearch
                              ? 'Try modifying your search keywords or clear the search input.'
                              : 'Metrics are numeric, quantitative values used to track and measure business KPIs with SQL calculations.'}
                          </span>
                          {!metricSearch && (
                            <button
                              type="button"
                              onClick={() => setIsAddMetricModalOpen(true)}
                              style={{
                                marginTop: '10px',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '7px 16px',
                                borderRadius: '6px',
                                border: 'none',
                                background: '#4F46E5',
                                color: '#FFFFFF',
                                fontSize: '12.5px',
                                fontWeight: 500,
                                cursor: 'pointer',
                              }}
                            >
                              <Plus size={14} />
                              <span>Add Metric</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredMetrics.map((metric, idx) => {
                      const metricId = metric.id || `metric-${idx}`;
                      const isSelected = selectedMetricIds.includes(metricId);
                      const isIncluded = metric.isIncluded !== false;

                      return (
                        <tr
                          key={metricId}
                          style={{
                            borderBottom: idx === filteredMetrics.length - 1 ? 'none' : '1px solid #F1F5F9',
                            backgroundColor: isSelected ? '#F8FAFC' : 'transparent',
                            transition: 'background-color 0.15s ease',
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) e.currentTarget.style.backgroundColor = '#F8FAFC';
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          {/* 1. Checkbox */}
                          <td style={{ padding: '14px 14px' }}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelectMetric(metricId)}
                              style={{ cursor: 'pointer', width: '15px', height: '15px', accentColor: '#4F46E5' }}
                            />
                          </td>

                          {/* 2. Included Toggle Switch */}
                          <td style={{ padding: '14px 14px' }}>
                            <div
                              onClick={() => toggleMetricInclusion(metric.id)}
                              title={isIncluded ? 'Metric enabled' : 'Metric disabled'}
                              style={{
                                width: '34px',
                                height: '18px',
                                borderRadius: '10px',
                                background: isIncluded ? '#4F46E5' : '#CBD5E1',
                                position: 'relative',
                                cursor: 'pointer',
                                transition: 'background-color 0.2s ease',
                                display: 'inline-block',
                              }}
                            >
                              <div
                                style={{
                                  width: '14px',
                                  height: '14px',
                                  borderRadius: '50%',
                                  background: '#FFFFFF',
                                  position: 'absolute',
                                  top: '2px',
                                  left: isIncluded ? '18px' : '2px',
                                  transition: 'left 0.2s ease',
                                  boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
                                }}
                              />
                            </div>
                          </td>

                          {/* 3. Name with Stale Badge */}
                          <td
                            style={{ padding: '14px 14px', cursor: 'pointer' }}
                            onClick={() => {
                              setSelectedEditMetric(metric);
                              setIsEditMetricModalOpen(true);
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'nowrap' }}>
                              <span
                                style={{
                                  fontSize: '13px',
                                  fontWeight: 500,
                                  color: '#1E293B',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                {metric.name}
                              </span>

                              {/* Stale Badge matching screenshot */}
                              <span
                                style={{
                                  display: 'inline-block',
                                  padding: '1px 7px',
                                  borderRadius: '10px',
                                  background: '#FEE2E2',
                                  color: '#DC2626',
                                  fontSize: '10.5px',
                                  fontWeight: 600,
                                  lineHeight: 1.3,
                                }}
                              >
                                Stale
                              </span>
                            </div>
                          </td>

                          {/* 4. Tables */}
                          <td style={{ padding: '14px 14px' }}>
                            {metric.tables ? (
                              <span
                                style={{
                                  fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                                  fontSize: '12px',
                                  color: '#475569',
                                  background: '#F1F5F9',
                                  padding: '3px 6px',
                                  borderRadius: '4px',
                                }}
                              >
                                {metric.tables}
                              </span>
                            ) : (
                              <span style={{ color: '#94A3B8', fontSize: '13px' }}>—</span>
                            )}
                          </td>

                          {/* 5. Type */}
                          <td style={{ padding: '14px 14px', fontSize: '12.5px', color: '#475569', fontWeight: 500 }}>
                            {metric.definitionType || 'SQL'}
                          </td>

                          {/* 6. Description */}
                          <td
                            style={{
                              padding: '14px 14px',
                              fontSize: '12.5px',
                              color: '#64748B',
                              maxWidth: '300px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                            title={metric.englishDescription || metric.name}
                          >
                            {metric.englishDescription || `Calculation for ${metric.name}`}
                          </td>

                          {/* 7. Display Format Dropdown */}
                          <td style={{ padding: '14px 14px' }}>
                            <div style={{ position: 'relative', width: '120px' }}>
                              <select
                                value={metric.displayFormat || 'Automatic'}
                                onChange={(e) => handleUpdateDisplayFormat(metricId, e.target.value)}
                                style={{
                                  width: '100%',
                                  padding: '5px 22px 5px 8px',
                                  fontSize: '12px',
                                  fontWeight: 500,
                                  color: '#334155',
                                  background: '#FFFFFF',
                                  border: '1px solid #CBD5E1',
                                  borderRadius: '6px',
                                  outline: 'none',
                                  cursor: 'pointer',
                                  appearance: 'none',
                                }}
                              >
                                <option value="Automatic">Automatic</option>
                                <option value="Currency">Currency ($)</option>
                                <option value="Percentage">Percentage (%)</option>
                                <option value="Number">Number (#)</option>
                                <option value="Duration">Duration</option>
                                <option value="Decimal">Decimal</option>
                              </select>
                              <ChevronDown
                                size={14}
                                style={{
                                  position: 'absolute',
                                  right: '6px',
                                  top: '50%',
                                  transform: 'translateY(-50%)',
                                  color: '#64748B',
                                  pointerEvents: 'none',
                                }}
                              />
                            </div>
                          </td>

                          {/* 8. Three-dots Menu */}
                          <td style={{ padding: '14px 8px', textAlign: 'right', position: 'relative' }}>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveMetricMenuId(activeMetricMenuId === metricId ? null : metricId);
                              }}
                              style={{
                                background: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                color: '#94A3B8',
                                padding: '4px',
                                borderRadius: '4px',
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.color = '#1E293B')}
                              onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
                            >
                              <MoreVertical size={16} />
                            </button>

                            {activeMetricMenuId === metricId && (
                              <div
                                style={{
                                  position: 'absolute',
                                  top: 'calc(100% - 6px)',
                                  right: '8px',
                                  background: '#FFFFFF',
                                  border: '1px solid #E2E8F0',
                                  borderRadius: '6px',
                                  boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)',
                                  zIndex: 100,
                                  minWidth: '120px',
                                  overflow: 'hidden',
                                }}
                              >
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedEditMetric(metric);
                                    setIsEditMetricModalOpen(true);
                                    setActiveMetricMenuId(null);
                                  }}
                                  style={{
                                    width: '100%',
                                    padding: '8px 12px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    border: 'none',
                                    background: 'transparent',
                                    color: '#1E293B',
                                    fontSize: '12.5px',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                  }}
                                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
                                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                                >
                                  <span>Edit</span>
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (metric.sql) {
                                      navigator.clipboard.writeText(metric.sql);
                                      alert('SQL calculation copied to clipboard!');
                                    }
                                    setActiveMetricMenuId(null);
                                  }}
                                  style={{
                                    width: '100%',
                                    padding: '8px 12px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    border: 'none',
                                    background: 'transparent',
                                    color: '#1E293B',
                                    fontSize: '12.5px',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                  }}
                                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
                                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                                >
                                  <span>Copy SQL</span>
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteMetric(metricId);
                                  }}
                                  style={{
                                    width: '100%',
                                    padding: '8px 12px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    border: 'none',
                                    background: 'transparent',
                                    color: '#DC2626',
                                    fontSize: '12.5px',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                  }}
                                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FEF2F2')}
                                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                                >
                                  <Trash2 size={13} />
                                  <span>Delete</span>
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
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 5. OTHER SUB-VIEWS (QUERIES / SYNONYMS / ENTITIES / SKILLS) */}
      {/* ========================================================================= */}
      {activeSubTab !== 'builder' && activeSubTab !== 'knowledge' && activeSubTab !== 'metrics' && (
        <div
          style={{
            background: '#FFFFFF',
            border: '1px solid #E2E8F0',
            borderRadius: '8px',
            padding: '40px 24px',
            textAlign: 'center',
          }}
        >
          <Sparkles size={36} style={{ color: '#4F46E5', opacity: 0.6, margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#1E293B', margin: '0 0 6px 0' }}>
            {activeSubTab.charAt(0).toUpperCase() + activeSubTab.slice(1)} Explorer
          </h3>
          <p style={{ fontSize: '13px', color: '#64748B', maxWidth: '420px', margin: '0 auto' }}>
            Domain ontology context, definitions, and AI agent execution rules automatically synchronized.
          </p>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALS */}
      {/* ========================================================================= */}

      {/* MODAL 1: Connect Context Builder Source Modal */}
      {isConnectModalOpen && (
        <ConnectContextBuilderModal
          isOpen={isConnectModalOpen}
          onClose={() => setIsConnectModalOpen(false)}
          domainId={domainId}
          domainName={domainName}
          onSuccess={onRefresh}
        />
      )}

      {/* MODAL 2: Add Knowledge Modal */}
      {isAddKnowledgeModalOpen && (
        <AddKnowledgeModal
          isOpen={isAddKnowledgeModalOpen}
          onClose={() => setIsAddKnowledgeModalOpen(false)}
          domainId={domainId}
          domainName={domainName}
          onSuccess={onRefresh}
        />
      )}

      {/* MODAL 3: Edit Knowledge Modal */}
      {isEditKnowledgeModalOpen && selectedEditItem && (
        <EditKnowledgeModal
          isOpen={isEditKnowledgeModalOpen}
          onClose={() => {
            setIsEditKnowledgeModalOpen(false);
            setSelectedEditItem(null);
          }}
          domainId={domainId}
          domainName={domainName}
          item={selectedEditItem}
          onSuccess={onRefresh}
        />
      )}

      {/* MODAL 4: Add Metric Modal (Image 2) */}
      {isAddMetricModalOpen && (
        <AddMetricModal
          isOpen={isAddMetricModalOpen}
          onClose={() => setIsAddMetricModalOpen(false)}
          domainId={domainId}
          domainName={domainName}
          connections={workspaceSources}
          onSuccess={handleAddMetricSuccess}
        />
      )}

      {/* MODAL 5: Edit Metric Modal */}
      {isEditMetricModalOpen && selectedEditMetric && (
        <EditMetricModal
          isOpen={isEditMetricModalOpen}
          onClose={() => {
            setIsEditMetricModalOpen(false);
            setSelectedEditMetric(null);
          }}
          domainId={domainId}
          domainName={domainName}
          connections={workspaceSources}
          metric={selectedEditMetric}
          onSuccess={onRefresh}
          onDelete={handleDeleteMetric}
        />
      )}
    </div>
  );
};
