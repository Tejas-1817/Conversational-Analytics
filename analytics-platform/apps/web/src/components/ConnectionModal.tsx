import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  X,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Upload,
  FileSpreadsheet,
  Layers,
  ArrowLeft,
  Search,
  Database,
  Cloud,
  Sparkles,
  Check,
  ExternalLink,
} from 'lucide-react';
import { z } from 'zod';
import { fetchApi } from '../services/api';
import { SourceLogo } from './SourceLogos';

const connectionSchema = z.object({
  name: z.string().min(1, 'Connection Name is required').max(200, 'Name must be 200 characters or less'),
  type: z.enum(['postgres', 'mysql', 'mssql', 'excel', 'snowflake', 'sqlite']),
  host: z.string().optional(),
  port: z.number().int().positive().optional().or(z.literal('')),
  database_name: z.string().optional(),
  username: z.string().optional(),
  password: z.string().optional(),
});

type ConnectionFormData = z.infer<typeof connectionSchema>;

interface SheetPreviewItem {
  sheet_name: string;
  suggested_table_name: string;
  row_count: number;
  column_names: string[];
  suggested_header_row: number;
  preview_rows: any[];
  is_empty: boolean;
  warning?: string;
}

interface SheetOverrideConfig {
  table_name: string;
  header_row: number;
  include: boolean;
  forward_fill_columns?: string[];
}

interface ConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface ConnectorOption {
  id: string;
  name: string;
  type: 'postgres' | 'mysql' | 'mssql' | 'excel' | 'snowflake' | 'sqlite' | 'coming_soon';
  category: 'database' | 'warehouse' | 'files' | 'tools';
  description: string;
  isAvailable: boolean;
  iconBg?: string;
  renderIcon: () => React.ReactNode;
}

export const ConnectionModal: React.FC<ConnectionModalProps> = ({ isOpen, onClose, onSuccess }) => {
  // Navigation step: 'catalog' -> 'configure'
  const [step, setStep] = useState<'catalog' | 'configure'>('catalog');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [comingSoonNotice, setComingSoonNotice] = useState<string | null>(null);

  const [formData, setFormData] = useState<ConnectionFormData>({
    name: '',
    type: 'postgres',
    host: '',
    port: 5432,
    database_name: '',
    username: '',
    password: '',
  });

  // Excel Upload State
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [tempFileId, setTempFileId] = useState<string | null>(null);
  const [sheetPreviews, setSheetPreviews] = useState<SheetPreviewItem[]>([]);
  const [sheetOverrides, setSheetOverrides] = useState<Record<string, SheetOverrideConfig>>({});
  const [isPreviewing, setIsPreviewing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [testSuccess, setTestSuccess] = useState<boolean>(false);

  // Catalog definition matching the WisdomAI / Conversational Analytics connector grid
  const connectors: ConnectorOption[] = [
    {
      id: 'postgres',
      name: 'PostgreSQL',
      type: 'postgres',
      category: 'database',
      description: 'Connect directly to PostgreSQL 12+ instances and read-only replicas.',
      isAvailable: true,
      renderIcon: () => <SourceLogo type="postgres" size={32} />,
    },
    {
      id: 'mysql',
      name: 'MySQL',
      type: 'mysql',
      category: 'database',
      description: 'Connect to MySQL 8.0+ or MariaDB database servers.',
      isAvailable: true,
      renderIcon: () => <SourceLogo type="mysql" size={32} />,
    },
    {
      id: 'excel',
      name: 'Excel (.xlsx)',
      type: 'excel',
      category: 'files',
      description: 'Upload multi-sheet spreadsheets with automatic schema introspection.',
      isAvailable: true,
      renderIcon: () => <SourceLogo type="excel" size={32} />,
    },
    {
      id: 'snowflake',
      name: 'Snowflake',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Query enterprise Snowflake cloud data warehouses securely.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="snowflake" size={32} />,
    },
    {
      id: 'redshift',
      name: 'Redshift',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Amazon Redshift petabyte-scale data warehouse.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="redshift" size={32} />,
    },
    {
      id: 'bigquery',
      name: 'BigQuery',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Google Cloud BigQuery serverless data warehouse.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="bigquery" size={32} />,
    },
    {
      id: 'mssql',
      name: 'SQL Server',
      type: 'mssql',
      category: 'database',
      description: 'Microsoft SQL Server enterprise relational database.',
      isAvailable: true,
      renderIcon: () => <SourceLogo type="mssql" size={32} />,
    },
    {
      id: 'databricks',
      name: 'Databricks',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Databricks Lakehouse Platform with Delta Lake.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="databricks" size={32} />,
    },
    {
      id: 'clickhouse',
      name: 'ClickHouse',
      type: 'coming_soon',
      category: 'database',
      description: 'Fast open-source columnar database management system.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="clickhouse" size={32} />,
    },
    {
      id: 'athena',
      name: 'Athena',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Amazon Athena interactive serverless SQL query service.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="athena" size={32} />,
    },
    {
      id: 's3',
      name: 'Amazon S3',
      type: 'coming_soon',
      category: 'files',
      description: 'Query CSV, Parquet, and JSON files in Amazon S3 buckets.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="s3" size={32} />,
    },
    {
      id: 'mcp_server',
      name: 'MCP Server',
      type: 'coming_soon',
      category: 'tools',
      description: 'Connect Model Context Protocol server endpoints.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="mcpserver" size={32} />,
    },
    {
      id: 'azure_synapse',
      name: 'Azure Synapse',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Azure Synapse Analytics enterprise data warehouse.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="azuresynapse" size={32} />,
    },
    {
      id: 'azure_blob',
      name: 'Azure Blob Storage',
      type: 'coming_soon',
      category: 'files',
      description: 'Scalable cloud object storage for modern data workloads.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="azureblob" size={32} />,
    },
    {
      id: 'trino',
      name: 'Trino',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Fast distributed SQL query engine for big data analytics.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="trino" size={32} />,
    },
    {
      id: 'sharepoint',
      name: 'SharePoint',
      type: 'coming_soon',
      category: 'files',
      description: 'Microsoft SharePoint document libraries and lists.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="sharepoint" size={32} />,
    },
    {
      id: 'spanner',
      name: 'Google Spanner',
      type: 'coming_soon',
      category: 'database',
      description: 'Google Cloud globally distributed relational database.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="spanner" size={32} />,
    },
    {
      id: 'teradata',
      name: 'Teradata',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Enterprise analytical database and cloud analytics platform.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="teradata" size={32} />,
    },
    {
      id: 'oracle',
      name: 'Oracle',
      type: 'coming_soon',
      category: 'database',
      description: 'Oracle Cloud and on-premise Autonomous Database.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="oracle" size={32} />,
    },
    {
      id: 'github',
      name: 'GitHub',
      type: 'coming_soon',
      category: 'tools',
      description: 'Repository issues, pull requests, and commit metadata.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="github" size={32} />,
    },
    {
      id: 'gitlab',
      name: 'GitLab',
      type: 'coming_soon',
      category: 'tools',
      description: 'GitLab project commits, pipelines, and issue analytics.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="gitlab" size={32} />,
    },
    {
      id: 'azure_devops',
      name: 'Azure DevOps',
      type: 'coming_soon',
      category: 'tools',
      description: 'Azure Boards work items, sprint metrics, and CI/CD pipelines.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="azuredevops" size={32} />,
    },
    {
      id: 'dremio',
      name: 'Dremio',
      type: 'coming_soon',
      category: 'warehouse',
      description: 'Dremio SQL Lakehouse engine with semantic data virtualization.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="dremio" size={32} />,
    },
    {
      id: 'outlook_calendar',
      name: 'Outlook Calendar',
      type: 'coming_soon',
      category: 'tools',
      description: 'Microsoft 365 calendar schedules, meeting events, and attendees.',
      isAvailable: false,
      renderIcon: () => <SourceLogo type="outlook" size={32} />,
    },
  ];

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setStep('catalog');
      setSearchQuery('');
      setSelectedCategory('all');
      setComingSoonNotice(null);
      setFormData({
        name: '',
        type: 'postgres',
        host: '',
        port: 5432,
        database_name: '',
        username: '',
        password: '',
      });
      setExcelFile(null);
      setTempFileId(null);
      setSheetPreviews([]);
      setSheetOverrides({});
      setErrors({});
      setBackendError(null);
      setTestSuccess(false);
    }
  }, [isOpen]);

  // Handle escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isTesting && !isSaving && !isPreviewing) {
        if (step === 'configure') {
          setStep('catalog');
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, step, isTesting, isSaving, isPreviewing, onClose]);

  // Filtered connectors
  const filteredConnectors = useMemo(() => {
    return connectors.filter((c) => {
      const matchesSearch =
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.description.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCat = selectedCategory === 'all' || c.category === selectedCategory;
      return matchesSearch && matchesCat;
    });
  }, [searchQuery, selectedCategory]);

  if (!isOpen) return null;

  const handleSelectConnector = (connector: ConnectorOption) => {
    if (!connector.isAvailable) {
      setComingSoonNotice(`${connector.name} connector is coming soon! You can request early access.`);
      setTimeout(() => setComingSoonNotice(null), 4000);
      return;
    }

    // Set defaults based on selection
    const defaultPorts: Record<string, number | undefined> = {
      postgres: 5432,
      mysql: 3306,
      mssql: 1433,
    };

    const defaultPort = defaultPorts[connector.type];

    setFormData({
      name: '',
      type: connector.type as any,
      host:
        connector.type === 'postgres' ||
          connector.type === 'mysql' ||
          connector.type === 'mssql'
          ? 'localhost'
          : '',
      port: defaultPort,
      database_name: '',
      username: '',
      password: '',
    });

    setExcelFile(null);
    setTempFileId(null);
    setSheetPreviews([]);
    setSheetOverrides({});
    setErrors({});
    setBackendError(null);
    setTestSuccess(false);

    setStep('configure');
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;

    if (name === 'type') {
      const defaultPorts: Record<string, number | undefined> = {
        postgres: 5432,
        mysql: 3306,
        mssql: 1433,
      };

      const defaultPort = defaultPorts[value];
      setFormData((prev) => ({ ...prev, type: value as any, port: defaultPort }));
      setBackendError(null);
      setTestSuccess(false);
      return;
    }

    setFormData((prev) => ({
      ...prev,
      [name]: name === 'port' ? (value === '' ? '' : parseInt(value, 10)) : value,
    }));

    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
    setTestSuccess(false);
  };

  const handleFileUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      setBackendError('Please select a valid Excel (.xlsx) file.');
      return;
    }

    setExcelFile(file);
    setBackendError(null);
    setIsPreviewing(true);
    setSheetPreviews([]);

    if (!formData.name.trim()) {
      const suggestedName = file.name.replace(/\.xlsx$/i, '').replace(/[_-]/g, ' ');
      setFormData((prev) => ({ ...prev, name: suggestedName }));
    }

    const uploadData = new FormData();
    uploadData.append('file', file);

    try {
      const previewRes = await fetchApi('/sources/excel/preview', {
        method: 'POST',
        body: uploadData,
      });

      setTempFileId(previewRes.temp_file_id);
      setSheetPreviews(previewRes.sheets || []);

      const initialOverrides: Record<string, SheetOverrideConfig> = {};
      (previewRes.sheets || []).forEach((s: SheetPreviewItem) => {
        initialOverrides[s.sheet_name] = {
          table_name: s.suggested_table_name,
          header_row: s.suggested_header_row ?? 0,
          include: !s.is_empty,
        };
      });
      setSheetOverrides(initialOverrides);
    } catch (err: any) {
      setBackendError(err.message || 'Failed to preview Excel file.');
      setExcelFile(null);
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleSheetOverrideChange = (sheetName: string, field: keyof SheetOverrideConfig, value: any) => {
    setSheetOverrides((prev) => ({
      ...prev,
      [sheetName]: {
        ...prev[sheetName],
        [field]: value,
      },
    }));
  };

  const validateForm = (): boolean => {
    const errs: Record<string, string> = {};

    if (!formData.name.trim()) {
      errs.name = 'Connection Name is required';
    }

    if (formData.type === 'excel') {
      if (!tempFileId || !excelFile) {
        errs.file = 'Please upload an Excel file.';
      }
      const includedCount = Object.values(sheetOverrides).filter((s) => s.include).length;
      if (sheetPreviews.length > 0 && includedCount === 0) {
        errs.sheets = 'Please select at least one sheet to include.';
      }
    } else {
      if (!formData.host?.trim()) errs.host = 'Host is required';
      if (!formData.database_name?.trim()) errs.database_name = 'Database Name is required';
      if (!formData.username?.trim()) errs.username = 'Username is required';
      if (!formData.password) errs.password = 'Password is required';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const buildSourcePayload = () => ({
    ...formData,
  });

  const handleTestConnection = async () => {
    if (!validateForm()) return false;

    setIsTesting(true);
    setBackendError(null);
    setTestSuccess(false);

    try {
      await fetchApi('/sources/test', {
        method: 'POST',
        body: JSON.stringify(buildSourcePayload()),
      });
      setTestSuccess(true);
      return true;
    } catch (err: any) {
      const msg = err.message || 'Connection test failed.';
      setBackendError(msg);
      return false;
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async () => {
    if (!validateForm()) return;

    if (formData.type !== 'excel') {
      const testPassed = await handleTestConnection();
      if (!testPassed) return;
    }

    setIsSaving(true);
    setBackendError(null);

    try {
      if (formData.type === 'excel') {
        await fetchApi('/sources/excel', {
          method: 'POST',
          body: JSON.stringify({
            name: formData.name.trim(),
            temp_file_id: tempFileId,
            sheet_overrides: sheetOverrides,
            options: {},
          }),
        });
      } else {
        await fetchApi('/sources', {
          method: 'POST',
          body: JSON.stringify(buildSourcePayload()),
        });
      }
      onSuccess();
      onClose();
    } catch (err: any) {
      setBackendError(err.message || 'Failed to save connection.');
    } finally {
      setIsSaving(false);
    }
  };

  // Get display name for current selected type in header
  const getSelectedTypeName = () => {
    const found = connectors.find((c) => c.type === formData.type);
    return found ? found.name : formData.type;
  };

  return (
    <div className="modal-overlay">
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: step === 'catalog' ? '880px' : formData.type === 'excel' ? '700px' : '560px',
          transition: 'max-width 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* MODAL HEADER */}
        <div className="modal-header" style={{ padding: '1rem 1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {step === 'configure' && (
              <button
                className="btn-ghost"
                onClick={() => setStep('catalog')}
                disabled={isTesting || isSaving || isPreviewing}
                title="Back to all sources"
                style={{ padding: '6px', borderRadius: 'var(--radius-sm)' }}
              >
                <ArrowLeft size={18} />
              </button>
            )}
            {step === 'configure' && (
              <SourceLogo type={formData.type} size={28} />
            )}
            <div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>
                {step === 'catalog' ? 'Connect Data Source' : `Configure ${getSelectedTypeName()} Connection`}
              </h2>
              {step === 'configure' && (
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Provide connection credentials to ingest schema and metadata.
                </div>
              )}
            </div>
          </div>
          <button
            className="btn-ghost"
            onClick={onClose}
            disabled={isTesting || isSaving || isPreviewing}
            style={{ padding: '6px', borderRadius: 'var(--radius-sm)' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* MODAL BODY */}
        <div className="modal-body" style={{ maxHeight: '78vh', overflowY: 'auto', padding: '1.25rem 1.5rem' }}>
          {/* STEP 1: CONNECTOR CATALOG SELECTION */}
          {step === 'catalog' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              {/* Top Banner with Illustration & Description */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  padding: '8px 16px 4px 16px',
                }}
              >
                <div
                  style={{
                    width: '64px',
                    height: '64px',
                    borderRadius: '16px',
                    background: 'linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)',
                    border: '1px solid #BFDBFE',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '12px',
                    boxShadow: '0 4px 12px rgba(59, 130, 246, 0.12)',
                    position: 'relative',
                  }}
                >
                  <Database size={30} style={{ color: 'var(--primary)' }} />
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '-4px',
                      right: '-4px',
                      background: '#10B981',
                      color: '#FFFFFF',
                      borderRadius: '50%',
                      width: '20px',
                      height: '20px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: '2px solid #FFFFFF',
                      fontSize: '12px',
                      fontWeight: 'bold',
                    }}
                  >
                    +
                  </div>
                </div>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-main)', margin: '0 0 6px 0' }}>
                  Select a Data Source
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '640px', margin: 0, lineHeight: 1.5 }}>
                  Link your existing data sources and tools to Conversational Analytics to scan metadata, build a knowledge graph, and fetch warehouse data to answer natural language queries.
                </p>
              </div>

              {/* Toast / Coming Soon Notice */}
              {comingSoonNotice && (
                <div
                  style={{
                    background: '#FFFBEB',
                    border: '1px solid #FCD34D',
                    color: '#92400E',
                    padding: '8px 14px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '13px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    animation: 'slideUp 0.2s ease-out',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Sparkles size={16} color="#D97706" />
                    <span>{comingSoonNotice}</span>
                  </div>
                  <button
                    className="btn-ghost"
                    onClick={() => setComingSoonNotice(null)}
                    style={{ padding: '2px', color: '#92400E' }}
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

              {/* Search & Category Filter Bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                  flexWrap: 'wrap',
                }}
              >
                {/* Search Bar */}
                <div
                  style={{
                    position: 'relative',
                    flex: '1',
                    minWidth: '220px',
                  }}
                >
                  <Search
                    size={16}
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
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search connectors (e.g. PostgreSQL, Excel, Snowflake)..."
                    style={{
                      width: '100%',
                      padding: '8px 10px 8px 34px',
                      fontSize: '13px',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      style={{
                        position: 'absolute',
                        right: '8px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--text-muted)',
                      }}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>

                {/* Category Pills */}
                <div style={{ display: 'flex', gap: '6px' }}>
                  {[
                    { id: 'all', label: 'All' },
                    { id: 'database', label: 'Databases' },
                    { id: 'warehouse', label: 'Warehouses' },
                    { id: 'files', label: 'Files' },
                    { id: 'tools', label: 'Tools' },
                  ].map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setSelectedCategory(cat.id)}
                      style={{
                        padding: '6px 12px',
                        fontSize: '12px',
                        fontWeight: 500,
                        borderRadius: 'var(--radius-full)',
                        border: '1px solid',
                        borderColor: selectedCategory === cat.id ? 'var(--primary)' : 'var(--border-color)',
                        background: selectedCategory === cat.id ? 'var(--primary-light)' : 'transparent',
                        color: selectedCategory === cat.id ? 'var(--primary)' : 'var(--text-muted)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Connector Cards Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                  gap: '12px',
                }}
              >
                {filteredConnectors.map((connector) => {
                  return (
                    <div
                      key={connector.id}
                      onClick={() => handleSelectConnector(connector)}
                      style={{
                        border: connector.isAvailable ? '1px solid var(--border-color)' : '1px solid #ECEEF3',
                        borderRadius: 'var(--radius)',
                        padding: '14px 12px',
                        background: 'var(--bg-card)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        textAlign: 'center',
                        gap: '8px',
                        position: 'relative',
                        transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                        boxShadow: 'var(--shadow-xs)',
                        userSelect: 'none',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = connector.isAvailable ? 'var(--primary)' : '#D1D5DB';
                        e.currentTarget.style.transform = 'translateY(-2px)';
                        e.currentTarget.style.boxShadow = connector.isAvailable
                          ? '0 6px 16px rgba(59, 130, 246, 0.12)'
                          : '0 4px 10px rgba(0, 0, 0, 0.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = connector.isAvailable ? 'var(--border-color)' : '#ECEEF3';
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = 'var(--shadow-xs)';
                      }}
                    >
                      {/* Active Status Badge */}
                      {connector.isAvailable && (
                        <div
                          style={{
                            position: 'absolute',
                            top: '8px',
                            right: '8px',
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            background: '#10B981',
                          }}
                          title="Active Connector"
                        />
                      )}

                      {/* Icon */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '36px' }}>
                        {connector.renderIcon()}
                      </div>

                      {/* Name */}
                      <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-main)' }}>
                        {connector.name}
                      </div>

                      {/* Badge if coming soon */}
                      {!connector.isAvailable && (
                        <span
                          style={{
                            fontSize: '10px',
                            color: 'var(--text-faint)',
                            background: 'var(--bg-dark)',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontWeight: 500,
                          }}
                        >
                          Coming Soon
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>

              {filteredConnectors.length === 0 && (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '36px 16px',
                    color: 'var(--text-muted)',
                  }}
                >
                  <Search size={32} style={{ opacity: 0.3, marginBottom: '8px' }} />
                  <div style={{ fontWeight: 500, color: 'var(--text-main)' }}>No matching connectors found</div>
                  <div style={{ fontSize: '12px', marginTop: '4px' }}>
                    Try searching with another keyword or selecting a different category.
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: CONNECTOR CONFIGURATION */}
          {step === 'configure' && (
            <div>
              {backendError && (
                <div className="error-banner" style={{ marginBottom: '16px' }}>
                  <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ display: 'block', marginBottom: '2px' }}>Connection Failed</strong>
                    {backendError}
                  </div>
                </div>
              )}

              {testSuccess && !backendError && (
                <div
                  className="error-banner"
                  style={{
                    background: 'rgba(34, 197, 94, 0.1)',
                    borderColor: 'var(--success)',
                    color: 'var(--success)',
                    marginBottom: '16px',
                  }}
                >
                  <CheckCircle2 size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>Connection test succeeded! Ready to ingest.</div>
                </div>
              )}

              <div className="form-group">
                <label htmlFor="name">Connection Name</label>
                <input
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  placeholder={`e.g., Production ${getSelectedTypeName()} Data`}
                  disabled={isTesting || isSaving || isPreviewing}
                />
                {errors.name && <div className="form-error">{errors.name}</div>}
              </div>

              {/* EXCEL UPLOAD WORKFLOW */}
              {formData.type === 'excel' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '12px' }}>
                  {/* Dropzone */}
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (e.dataTransfer.files?.[0]) {
                        handleFileUpload(e.dataTransfer.files[0]);
                      }
                    }}
                    style={{
                      border: '2px dashed var(--border-color)',
                      borderRadius: 'var(--radius-md)',
                      padding: '24px',
                      textAlign: 'center',
                      background: 'var(--bg-secondary)',
                      cursor: isPreviewing ? 'not-allowed' : 'pointer',
                      transition: 'border-color 0.2s',
                    }}
                  >
                    <input
                      type="file"
                      ref={fileInputRef}
                      accept=".xlsx"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        if (e.target.files?.[0]) {
                          handleFileUpload(e.target.files[0]);
                        }
                      }}
                    />
                    {isPreviewing ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                        <Loader2 size={32} className="animate-spin text-primary" />
                        <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Analyzing Excel sheets and schema...</span>
                      </div>
                    ) : excelFile ? (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
                        <FileSpreadsheet size={32} style={{ color: 'var(--primary)' }} />
                        <div style={{ textAlign: 'left' }}>
                          <div style={{ fontWeight: 600, fontSize: '14px' }}>{excelFile.name}</div>
                          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                            {(excelFile.size / 1024).toFixed(1)} KB • Click or drop to replace
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                        <Upload size={32} style={{ color: 'var(--text-muted)' }} />
                        <div style={{ fontSize: '14px', fontWeight: 500 }}>Click to upload or drag & drop an Excel file</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Supports .xlsx workbooks with multiple sheets (up to 50MB)</div>
                      </div>
                    )}
                  </div>
                  {errors.file && <div className="form-error">{errors.file}</div>}

                  {/* Sheet Configuration List */}
                  {sheetPreviews.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Layers size={16} /> Discovered Sheets ({sheetPreviews.length})
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Each included sheet becomes an independent SQL table</div>
                      </div>
                      {errors.sheets && <div className="form-error">{errors.sheets}</div>}

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '280px', overflowY: 'auto' }}>
                        {sheetPreviews.map((sheet) => {
                          const override = sheetOverrides[sheet.sheet_name] || {
                            table_name: sheet.suggested_table_name,
                            header_row: 0,
                            include: !sheet.is_empty,
                          };

                          return (
                            <div
                              key={sheet.sheet_name}
                              style={{
                                border: '1px solid var(--border-color)',
                                borderRadius: 'var(--radius-sm)',
                                padding: '12px',
                                background: override.include ? 'var(--bg-main)' : 'var(--bg-secondary)',
                                opacity: override.include ? 1 : 0.6,
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '8px',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '14px' }}>
                                  <input
                                    type="checkbox"
                                    checked={override.include}
                                    onChange={(e) => handleSheetOverrideChange(sheet.sheet_name, 'include', e.target.checked)}
                                  />
                                  Sheet: <span style={{ color: 'var(--primary)' }}>{sheet.sheet_name}</span>
                                </label>
                                <span style={{ fontSize: '12px', color: 'var(--text-muted)', background: 'var(--bg-secondary)', padding: '2px 8px', borderRadius: '12px' }}>
                                  {sheet.row_count} rows • {sheet.column_names.length} cols
                                </span>
                              </div>

                              {override.include && (
                                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '8px', marginTop: '4px' }}>
                                  <div>
                                    <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>
                                      SQL Table Name
                                    </label>
                                    <input
                                      value={override.table_name}
                                      onChange={(e) => handleSheetOverrideChange(sheet.sheet_name, 'table_name', e.target.value)}
                                      placeholder="table_name"
                                      style={{ padding: '6px 8px', fontSize: '13px' }}
                                    />
                                  </div>
                                  <div>
                                    <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>
                                      Header Row
                                    </label>
                                    <input
                                      type="number"
                                      min="0"
                                      value={override.header_row}
                                      onChange={(e) => handleSheetOverrideChange(sheet.sheet_name, 'header_row', parseInt(e.target.value, 10) || 0)}
                                      style={{ padding: '6px 8px', fontSize: '13px' }}
                                    />
                                  </div>
                                </div>
                              )}

                              {override.include && sheet.column_names.length > 0 && (
                                <div style={{ fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                  Columns: {sheet.column_names.slice(0, 6).join(', ')}{sheet.column_names.length > 6 ? ` +${sheet.column_names.length - 6} more` : ''}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                /* RELATIONAL DATABASE / WAREHOUSE WORKFLOW */
                <>
                  <div className="grid grid-cols-2 gap-3" style={{ marginBottom: 'var(--space-3)' }}>
                    <div>
                      <label htmlFor="database_name" style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: 500 }}>
                        Database Name
                      </label>
                      <input
                        id="database_name"
                        name="database_name"
                        value={formData.database_name}
                        onChange={handleChange}
                        placeholder={formData.type === 'mysql' ? 'app_db' : 'postgres'}
                        disabled={isTesting || isSaving}
                      />
                      {errors.database_name && <div className="form-error">{errors.database_name}</div>}
                    </div>
                    <div>
                      <label htmlFor="port" style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: 500 }}>
                        Port
                      </label>
                      <input
                        id="port"
                        name="port"
                        type="number"
                        value={formData.port ?? ''}
                        onChange={handleChange}
                        disabled={isTesting || isSaving}
                      />
                      {errors.port && <div className="form-error">{errors.port}</div>}
                    </div>
                  </div>

                  <div className="form-group">
                    <label htmlFor="host">Host / Hostname</label>
                    <input
                      id="host"
                      name="host"
                      value={formData.host}
                      onChange={handleChange}
                      placeholder="localhost or db.company.internal"
                      disabled={isTesting || isSaving}
                    />
                    {errors.host && <div className="form-error">{errors.host}</div>}
                  </div>

                  <div className="grid grid-cols-2 gap-3 form-group">
                    <div>
                      <label htmlFor="username">Username</label>
                      <input
                        id="username"
                        name="username"
                        value={formData.username}
                        onChange={handleChange}
                        placeholder={formData.type === 'postgres' ? 'postgres' : 'root'}
                        disabled={isTesting || isSaving}
                      />
                      {errors.username && <div className="form-error">{errors.username}</div>}
                    </div>
                    <div>
                      <label htmlFor="password">Password</label>
                      <input
                        id="password"
                        name="password"
                        type="password"
                        value={formData.password}
                        onChange={handleChange}
                        placeholder="••••••••"
                        disabled={isTesting || isSaving}
                      />
                      {errors.password && <div className="form-error">{errors.password}</div>}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* MODAL FOOTER */}
        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {step === 'catalog' ? (
            <>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {connectors.filter((c) => c.isAvailable).length} available connectors • More arriving weekly
              </div>
              <button className="btn-secondary" onClick={onClose}>
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                className="btn-secondary"
                onClick={() => setStep('catalog')}
                disabled={isTesting || isSaving || isPreviewing}
              >
                <ArrowLeft size={16} style={{ marginRight: '6px' }} /> Back
              </button>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="btn-secondary"
                  onClick={onClose}
                  disabled={isTesting || isSaving || isPreviewing}
                >
                  Cancel
                </button>
                {formData.type !== 'excel' && (
                  <button
                    className="btn-secondary"
                    onClick={handleTestConnection}
                    disabled={isTesting || isSaving}
                  >
                    {isTesting ? <><Loader2 size={16} className="animate-spin" /> Testing...</> : 'Test Connection'}
                  </button>
                )}
                <button
                  onClick={handleSave}
                  disabled={isTesting || isSaving || isPreviewing || (formData.type === 'excel' && !tempFileId)}
                >
                  {isSaving ? (
                    <><Loader2 size={16} className="animate-spin" /> Ingesting...</>
                  ) : formData.type === 'excel' ? (
                    'Import & Ingest'
                  ) : (
                    'Connect & Ingest'
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
