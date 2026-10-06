import React, { useState, useEffect, useRef } from 'react';
import { fetchApi } from '../../services/api';
import { ChartRenderer } from '../../components/visualizations/ChartRenderer';
import { Download, Save, Send, AlertTriangle, Info, CheckCircle2, Copy, Check, RefreshCcw, ThumbsUp, ThumbsDown, User, Bot, Database, Code, Table, Plus, MessageSquare, Search, Trash2, Edit2, Clock, BarChart2, X, ChevronLeft, ChevronRight, GitBranch, FileCode2, FolderGit2 } from 'lucide-react';
import { PipelineProgress } from '../../components/chat/PipelineProgress';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function SqlAccordion({ sql }: { sql: string }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden', fontSize: '0.85rem' }}>
      {/* Single header bar */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.5rem 1rem',
          cursor: 'pointer',
          background: 'var(--bg-card)',
          borderBottom: isOpen ? '1px solid var(--border-color)' : 'none',
          userSelect: 'none',
        }}
      >
        <span style={{ fontWeight: 600, color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          {isOpen ? '▾ Hide Generated SQL Query' : '▸ Show Generated SQL Query'}
        </span>
        <button
          onClick={handleCopy}
          title="Copy SQL"
          style={{
            padding: '0.2rem 0.4rem',
            borderRadius: '4px',
            background: 'transparent',
            border: '1px solid var(--border-color)',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-main)'; e.currentTarget.style.borderColor = 'var(--text-muted)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--border-color)'; }}
        >
          {copied ? <Check size={13} style={{ color: '#22c55e' }} /> : <Copy size={13} />}
        </button>
      </div>
      {/* Code body */}
      {isOpen && (
        <pre
          style={{
            margin: 0,
            padding: '1rem',
            background: '#F8FAFC',
            fontSize: '0.85rem',
            color: '#0F172A',
            fontFamily: 'Consolas, Monaco, "Courier New", monospace',
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.5,
          }}
        >
          <code>{sql}</code>
        </pre>
      )}
    </div>
  );
}

function CodeSnippetAccordion({ chunks }: { chunks: any[] }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [copiedIndex, setCopiedIndex] = React.useState<number | null>(null);

  if (!chunks || chunks.length === 0) return null;

  const handleCopyChunk = (code: string, idx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(code);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div style={{ border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden', fontSize: '0.85rem' }}>
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.55rem 1rem',
          cursor: 'pointer',
          background: 'var(--bg-card)',
          borderBottom: isOpen ? '1px solid var(--border-color)' : 'none',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <FileCode2 size={15} style={{ color: '#ec4899' }} />
          <span style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.85rem' }}>
            Retrieved Code Snippets ({chunks.length} blocks from Vector Search)
          </span>
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {isOpen ? '▾ Hide Snippets' : '▸ Show Snippets'}
        </span>
      </div>

      {isOpen && (
        <div style={{ padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', background: 'var(--bg-main, #0F172A)' }}>
          {chunks.map((chunk, idx) => {
            const meta = chunk.metadata || {};
            const code = chunk.text || chunk.code || '';
            const fp = meta.file_path || chunk.file_path || 'Unknown file';
            const sym = meta.name || chunk.symbol_name || '';
            const lStart = meta.line_start || chunk.start_line;
            const lEnd = meta.line_end || chunk.end_line;
            const lineInfo = lStart && lEnd ? `L${lStart}-${lEnd}` : '';
            const score = chunk.similarity ? `${Math.round(chunk.similarity * 100)}% match` : null;

            return (
              <div
                key={idx}
                style={{
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px',
                  overflow: 'hidden',
                  background: 'var(--bg-card, #1E293B)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.4rem 0.75rem',
                    background: 'rgba(255,255,255,0.04)',
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                    fontSize: '0.78rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#94A3B8', fontFamily: 'monospace' }}>
                    <span style={{ color: 'var(--text-main, #F1F5F9)', fontWeight: 600 }}>{fp}</span>
                    {lineInfo && <span style={{ color: '#64748B' }}>({lineInfo})</span>}
                    {sym && (
                      <span style={{ background: 'rgba(236,72,153,0.15)', color: '#F472B6', padding: '0.1rem 0.4rem', borderRadius: '4px', fontSize: '0.72rem' }}>
                        {sym}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {score && (
                      <span style={{ color: '#10B981', fontSize: '0.72rem', fontWeight: 600 }}>
                        {score}
                      </span>
                    )}
                    <button
                      onClick={(e) => handleCopyChunk(code, idx, e)}
                      title="Copy snippet"
                      style={{
                        padding: '0.2rem 0.4rem',
                        borderRadius: '4px',
                        background: 'transparent',
                        border: '1px solid rgba(255,255,255,0.15)',
                        color: 'var(--text-muted, #94A3B8)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      {copiedIndex === idx ? <Check size={12} style={{ color: '#22c55e' }} /> : <Copy size={12} />}
                    </button>
                  </div>
                </div>
                <pre
                  style={{
                    margin: 0,
                    padding: '0.75rem',
                    background: '#0F172A',
                    fontSize: '0.8rem',
                    color: '#E2E8F0',
                    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                    overflowX: 'auto',
                    whiteSpace: 'pre',
                    lineHeight: 1.45,
                    maxHeight: '260px',
                    overflowY: 'auto',
                  }}
                >
                  <code>{code}</code>
                </pre>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function GraphFactsAccordion({ facts }: { facts: string[] }) {
  const [isOpen, setIsOpen] = React.useState(false);

  if (!facts || facts.length === 0) return null;

  return (
    <div style={{ border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden', fontSize: '0.85rem' }}>
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.55rem 1rem',
          cursor: 'pointer',
          background: 'var(--bg-card)',
          borderBottom: isOpen ? '1px solid var(--border-color)' : 'none',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <GitBranch size={15} style={{ color: '#6366f1' }} />
          <span style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.85rem' }}>
            Graph Architecture Relationships ({facts.length} Neo4j relations)
          </span>
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {isOpen ? '▾ Hide Relations' : '▸ Show Relations'}
        </span>
      </div>

      {isOpen && (
        <div style={{ padding: '0.75rem 1rem', background: 'var(--bg-card)', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {facts.map((fact, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem',
                fontSize: '0.82rem',
                color: 'var(--text-main)',
                lineHeight: 1.5,
              }}
            >
              <span style={{ color: '#6366f1', marginTop: '2px' }}>•</span>
              <div>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <span>{children}</span>,
                    code: ({ children }) => (
                      <code style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--primary)', padding: '0.1rem 0.35rem', borderRadius: '4px', fontSize: '0.78rem', fontFamily: 'monospace' }}>
                        {children}
                      </code>
                    ),
                  }}
                >
                  {fact}
                </ReactMarkdown>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export const ChatInterface = () => {
  const [conversations, setConversations] = useState<any[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<any | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(260);
  const isDragging = useRef(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(260);

  const handleDragStart = (e: React.MouseEvent) => {
    isDragging.current = true;
    dragStartX.current = e.clientX;
    dragStartWidth.current = sidebarWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMove = (ev: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = ev.clientX - dragStartX.current;
      const newWidth = Math.min(480, Math.max(180, dragStartWidth.current + delta));
      setSidebarWidth(newWidth);
    };
    const onUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const handleDeleteClick = (e: React.MouseEvent, conversation: any) => {
    e.stopPropagation();
    setDeleteTarget(conversation);
  };

  const confirmDeleteChat = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await fetchApi(`/engine/conversations/${deleteTarget.id}`, { method: 'DELETE' });
      const updated = await loadConversationsList();

      if (convId === deleteTarget.id) {
        if (updated.length > 0) {
          await loadConversation(updated[0].id);
        } else {
          await handleNewChat();
        }
      }
      setDeleteTarget(null);
    } catch (e: any) {
      alert(e.message || 'Failed to delete chat');
    } finally {
      setIsDeleting(false);
    }
  };

  const loadConversationsList = async () => {
    try {
      const data = await fetchApi('/engine/conversations');
      setConversations(data);
      return data;
    } catch (e) {
      console.error(e);
      return [];
    }
  };

  const loadConversations = async () => {
    const data = await loadConversationsList();
    const savedConvId = localStorage.getItem('active_conversation_id');
    const targetConv = data.find((c: any) => c.id === savedConvId);

    if (targetConv) {
      await loadConversation(targetConv.id);
    } else if (data.length > 0) {
      await loadConversation(data[0].id);
    } else {
      await handleNewChat();
    }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversation = async (id: string) => {
    try {
      const data = await fetchApi(`/engine/conversations/${id}`);
      setConvId(data.id);
      localStorage.setItem('active_conversation_id', data.id);

      let effectiveSourceId = data.source_id ? String(data.source_id) : '';
      if (!effectiveSourceId && sources.length > 0) {
        effectiveSourceId = sources[0].id;
        fetchApi(`/engine/conversations/${data.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ source_id: effectiveSourceId }),
        }).catch(() => { });
      }

      if (effectiveSourceId) {
        setSelectedSourceId(effectiveSourceId);
        localStorage.setItem('active_chat_source_id', effectiveSourceId);
      }
      setSelectedDomainId(data.domain_id ? String(data.domain_id) : '');

      const rawMessages = [...(data.messages || [])].sort((a: any, b: any) => {
        const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
        if (Math.abs(timeA - timeB) <= 1000) {
          if (a.role === 'user' && b.role === 'assistant') return -1;
          if (a.role === 'assistant' && b.role === 'user') return 1;
        }
        return timeA - timeB;
      });

      const normalizedMessages = rawMessages.map((m: any) => {
        let parsedData = m.result_data;
        if (typeof parsedData === 'string') {
          try { parsedData = JSON.parse(parsedData); } catch (e) { }
        }
        const rows = Array.isArray(parsedData) ? parsedData : (parsedData?.rows || parsedData?.data || []);
        const cols = Array.isArray(parsedData?.columns) ? parsedData.columns : (rows.length > 0 && typeof rows[0] === 'object' ? Object.keys(rows[0]) : []);

        return {
          id: m.id,
          role: m.role,
          question: m.role === 'assistant' ? m.question : m.content,
          content: m.content,

          answer: m.role === 'assistant' ? m.content : undefined,
          answer_markdown: m.role === 'assistant' ? m.content : undefined,

          // Code Intelligence Metadata
          isCodeIntel: parsedData?.is_code_intel || Boolean(m.route === 'code_intel'),
          repo_id: parsedData?.repo_id,
          repo_name: parsedData?.repo_name || 'Git Repo',
          referenced_files: parsedData?.referenced_files || [],
          referenced_symbols: parsedData?.referenced_symbols || [],
          graph_facts: parsedData?.graph_facts || [],
          retrieved_chunks: parsedData?.retrieved_chunks || [],

          sql: m.generated_sql,
          result_data: rows,
          rows: rows,
          columns: cols,

          row_count: parsedData?.row_count ?? rows.length,
          data_truncated: Boolean(parsedData?.data_truncated),

          follow_up_questions: Array.isArray(parsedData?.follow_up_questions) ? parsedData.follow_up_questions : [],

          column_types: parsedData?.column_types || {},

          visualization: parsedData?.visualization || m.chart_recommendation || 'table',

          title: parsedData?.title || 'Query Result',

          chart_recommendation: parsedData?.visualization || m.recommended_visualization?.chart_type || m.chart_recommendation,

          recommended_visualization: m.recommended_visualization,

          execution_time_ms: m.execution_time_ms,
          status: m.status,

          generated_at: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : undefined,
          database: 'analytics_db',
        };
      });
      setMessages(normalizedMessages);
    } catch (e) {
      console.error(e);
    }
  };

  const handleNewChat = async () => {
    try {
      const data = await fetchApi('/engine/conversations', {
        method: 'POST',
        body: JSON.stringify({
          source_id: selectedSourceId || null,
          domain_id: selectedDomainId || null,
        }),
      });
      setConvId(data.id);
      localStorage.setItem('active_conversation_id', data.id);
      setMessages([]);
      await loadConversationsList();
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const pollMessageStatus = (conversationId: string, messageId: string) => {
    const intervalId = setInterval(async () => {
      try {
        const msg = await fetchApi(`/engine/conversations/${conversationId}/messages/${messageId}`);
        setMessages(prev => prev.map(m => m.id === messageId ? msg : m));

        if (msg.status === 'complete' || msg.status === 'error') {
          clearInterval(intervalId);
          setLoading(false);
          loadConversationsList();
        }
      } catch (err) {
        console.error('Polling error', err);
        clearInterval(intervalId);
        setLoading(false);
      }
    }, 2000);
  };

  const [domains, setDomains] = useState<any[]>([]);
  const [selectedDomainId, setSelectedDomainId] = useState<string>('');
  const [showDomainPicker, setShowDomainPicker] = useState(false);

  const [sources, setSources] = useState<any[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>(() => localStorage.getItem('active_chat_source_id') || '');
  const [showSourcePicker, setShowSourcePicker] = useState(false);

  // Code repositories (Git repos for GraphRAG querying)
  const [codeRepos, setCodeRepos] = useState<any[]>([]);
  const isCodeRepoSelected = codeRepos.some((r: any) => r.repo_id === selectedSourceId);



  useEffect(() => {
    fetchApi('/domains')
      .then((data: any) => setDomains(Array.isArray(data) ? data : []))
      .catch(() => setDomains([]));

    Promise.allSettled([
      fetchApi('/sources'),
      fetchApi('/code-repos')
    ]).then(([sourcesRes, reposRes]) => {
      const srcList = sourcesRes.status === 'fulfilled' && Array.isArray(sourcesRes.value) ? sourcesRes.value : [];
      const repoList = reposRes.status === 'fulfilled' && Array.isArray(reposRes.value) ? reposRes.value : [];

      setSources(srcList);
      setCodeRepos(repoList);

      const saved = localStorage.getItem('active_chat_source_id');
      const hasSavedSource = srcList.some((s: any) => s.id === saved);
      const hasSavedRepo = repoList.some((r: any) => r.repo_id === saved);

      if (hasSavedSource || hasSavedRepo) {
        setSelectedSourceId(saved!);
      } else if (srcList.length > 0) {
        setSelectedSourceId(srcList[0].id);
        localStorage.setItem('active_chat_source_id', srcList[0].id);
      } else if (repoList.length > 0) {
        setSelectedSourceId(repoList[0].repo_id);
        localStorage.setItem('active_chat_source_id', repoList[0].repo_id);
      }
    }).catch(() => {
      setSources([]);
      setCodeRepos([]);
    });
  }, []);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    if (!selectedSourceId) {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now(),
          role: 'assistant',
          content: 'Please select a connected data source or git repository first.',
          isError: true,
        },
      ]);
      return;
    }

    const questionText = input.trim();
    const userMsg = { id: Date.now(), role: 'user', content: questionText };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    // Check if a code repository is selected
    const matchedRepo = codeRepos.find((r: any) => r.repo_id === selectedSourceId);
    const isRepoQuery = Boolean(matchedRepo);

    try {
      if (isRepoQuery) {
        const startTime = Date.now();
        // Route to GraphRAG code intelligence endpoint
        const data = await fetchApi(`/code-repos/${selectedSourceId}/query`, {
          method: 'POST',
          body: JSON.stringify({
            question: questionText,
            conversation_id: convId || undefined,
            n_chunks: 6,
          })
        });

        if (data.conversation_id && data.conversation_id !== convId) {
          setConvId(data.conversation_id);
          localStorage.setItem('active_conversation_id', data.conversation_id);
        }

        const repoName = matchedRepo?.name || matchedRepo?.url?.split('/').pop()?.replace('.git', '') || 'Git Repo';

        const botMsg = {
          id: Date.now() + 1,
          role: 'assistant',
          content: data.answer || '',
          answer_markdown: data.answer || '',
          isCodeIntel: true,
          question: questionText,
          repo_name: repoName,
          repo_id: selectedSourceId,
          referenced_files: data.referenced_files || [],
          referenced_symbols: data.referenced_symbols || [],
          graph_facts: data.graph_facts || [],
          retrieved_chunks: data.retrieved_chunks || [],
          execution_time_ms: Date.now() - startTime,
          generated_at: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setMessages(prev => [...prev, botMsg]);
      } else {
        // Route to SQL chat endpoint
        const data = await fetchApi('/api/v1/chat/sql', {
          method: 'POST',
          body: JSON.stringify({
            question: questionText,
            conversation_id: convId,
            domain_id: selectedDomainId || null,
            source_id: selectedSourceId,
            mode: 'auto'
          })
        });

        if (data.conversation_id && data.conversation_id !== convId) {
          setConvId(data.conversation_id);
          localStorage.setItem('active_conversation_id', data.conversation_id);
        }

        const recVis = data.recommended_visualization || data.chart_recommendation;
        const chartTypeRes = typeof recVis === 'object' && recVis !== null ? recVis.chart_type : (typeof recVis === 'string' ? recVis : undefined);

        const botMsg = {
          id: Date.now() + 1,
          role: 'assistant',
          content: data.answer_markdown || data.answer || '',
          intent: data.intent,
          question: data.question,
          answer: data.answer,
          answer_markdown: data.answer_markdown || data.answer,
          sql: data.sql,
          result_data: Array.isArray(data.rows) ? data.rows : [],
          rows: Array.isArray(data.rows) ? data.rows : [],
          columns: data.columns || [],
          column_types: data.column_types || {},
          row_count: data.row_count || 0,
          data_truncated: Boolean(data.data_truncated),
          follow_up_questions: Array.isArray(data.follow_up_questions)
            ? data.follow_up_questions
            : [],
          recommended_visualization: data.recommended_visualization,
          visualization: data.visualization,
          title: data.title,
          execution_time_ms: data.execution_time_ms,
          generated_at: data.generated_at,
          database: data.database,
        };
        setMessages(prev => [...prev, botMsg]);
      }
      await loadConversationsList();
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: err.message || 'Failed to process query.', isError: true }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveInsight = async (msg: any) => {
    const name = prompt('Enter a name for this insight:');
    if (!name) return;
    try {
      await fetchApi('/dashboards/insights', {
        method: 'POST',
        body: JSON.stringify({
          name,
          query: msg.question || msg.intent?.original_query || 'Saved Insight',
          chart_config: {
            chartType: msg.chart_recommendation || (msg.recommended_visualization && msg.recommended_visualization.chart_type) || 'table',
            data: msg.result_data || [],
            columns: msg.columns,
            columnTypes: msg.column_types || (msg.result_data && typeof msg.result_data === 'object' && !Array.isArray(msg.result_data) ? msg.result_data.column_types : undefined) || (msg.recommended_visualization && msg.recommended_visualization.profile?.column_types)
          }
        })
      });
      alert('Insight saved successfully! You can add it to a Dashboard.');
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleDownloadCSV = (msg: any) => {
    const rows = msg.rows || msg.result_data || [];
    if (!rows.length) return;
    const columns = msg.columns || Object.keys(rows[0]);
    const csvLines = [
      columns.join(','),
      ...rows.map((row: any) => columns.map((col: string) => JSON.stringify(row[col] ?? '')).join(','))
    ];
    const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `query_result_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const filteredConversations = conversations.filter(c =>
    c.title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Sidebar */}
      <div style={{
        width: sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
        minWidth: sidebarCollapsed ? '48px' : '180px',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        borderRight: '1px solid var(--border-color)',
        transition: sidebarCollapsed ? 'width 0.2s ease' : undefined,
        overflow: 'hidden',
        background: 'var(--bg-sidebar)',
      }}>
        {/* Collapse toggle row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: sidebarCollapsed ? 'center' : 'space-between', padding: '0.75rem 0.75rem 0.5rem' }}>
          {!sidebarCollapsed && (
            <span style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>Conversations</span>
          )}
          <button
            className="btn-ghost"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setSidebarCollapsed(c => !c)}
            style={{ padding: '0.25rem', borderRadius: 'var(--radius-sm)', flexShrink: 0 }}
          >
            {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {!sidebarCollapsed && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '0 0.75rem 1rem', flex: 1, overflow: 'hidden' }}>
            <button className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={handleNewChat}>
              <Plus size={16} style={{ marginRight: '0.5rem' }} /> New Chat
            </button>

            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search history..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: '100%', padding: '0.5rem 0.5rem 0.5rem 2.25rem', fontSize: '0.85rem' }}
              />
            </div>

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <h3 style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
                Recent Chats
              </h3>
              {filteredConversations.map(c => (
                <div
                  key={c.id}
                  onClick={() => loadConversation(c.id)}
                  style={{
                    padding: '0.5rem 0.75rem',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer',
                    background: convId === c.id ? 'rgba(79, 70, 229, 0.1)' : 'transparent',
                    color: convId === c.id ? 'var(--primary)' : 'var(--text-main)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.5rem',
                    fontSize: '0.85rem'
                  }}
                  className="hover-bg-light group"
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden', flex: 1 }}>
                    <MessageSquare size={14} style={{ flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title || 'New Conversation'}</span>
                  </div>
                  <button
                    className="btn-ghost"
                    title="Delete Chat"
                    onClick={(e) => handleDeleteClick(e, c)}
                    style={{
                      padding: '0.2rem 0.35rem',
                      borderRadius: '4px',
                      color: 'var(--text-muted)',
                      opacity: convId === c.id ? 0.9 : 0.6,
                      transition: 'all 0.15s ease',
                      lineHeight: 1
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.opacity = '1'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.opacity = convId === c.id ? '0.9' : '0.6'; }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              {filteredConversations.length === 0 && (
                <div className="text-muted text-sm text-center py-4">No conversations found.</div>
              )}
            </div>
          </div>
        )}

        {sidebarCollapsed && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 0' }}>
            <button className="btn-ghost" title="New Chat" onClick={handleNewChat} style={{ padding: '0.4rem' }}>
              <Plus size={16} />
            </button>
            <button className="btn-ghost" title="Search" style={{ padding: '0.4rem' }}>
              <Search size={16} />
            </button>
          </div>
        )}
      </div>

      {/* Drag-to-resize handle */}
      {!sidebarCollapsed && (
        <div
          onMouseDown={handleDragStart}
          style={{
            width: '5px',
            cursor: 'col-resize',
            flexShrink: 0,
            background: 'transparent',
            transition: 'background 0.15s',
            zIndex: 10,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--primary)'; e.currentTarget.style.opacity = '0.3'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
        />
      )}

      {/* Main Chat Area */}
      <div className="chat-container" style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column' }}>


        <div className="chat-messages" style={{ padding: '0 1rem', flex: 1 }}>
          {messages.length === 0 && (
            <div style={{ margin: 'auto', textAlign: 'center', opacity: 0.85, maxWidth: '560px' }}>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                background: isCodeRepoSelected ? 'rgba(236, 72, 153, 0.12)' : 'rgba(79, 70, 229, 0.1)',
                color: isCodeRepoSelected ? '#ec4899' : 'var(--primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 1.5rem',
              }}>
                {isCodeRepoSelected ? <FolderGit2 size={32} /> : <Bot size={32} />}
              </div>
              <h2 style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>
                {isCodeRepoSelected ? 'Ask Code Intelligence' : 'How can I help you today?'}
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                {isCodeRepoSelected
                  ? 'Ask questions about repository architecture, call hierarchies, AST functions, and API logic.'
                  : 'Ask a question about your business data in plain English to generate SQL & view live results.'}
              </p>

              <div className="grid grid-cols-2 gap-3 mt-4" style={{ textAlign: 'left' }}>
                {isCodeRepoSelected ? (
                  <>
                    <div className="card hover-bg-light" style={{ padding: '0.9rem 1rem', cursor: 'pointer', transition: 'all 0.2s', border: '1px solid var(--border-color)' }} onClick={() => setInput("How does request authentication and token verification work?")}>
                      <span className="text-sm">"How does request authentication and token verification work?"</span>
                    </div>
                    <div className="card hover-bg-light" style={{ padding: '0.9rem 1rem', cursor: 'pointer', transition: 'all 0.2s', border: '1px solid var(--border-color)' }} onClick={() => setInput("What are the main API routes and their handler functions?")}>
                      <span className="text-sm">"What are the main API routes and their handler functions?"</span>
                    </div>
                    <div className="card hover-bg-light" style={{ padding: '0.9rem 1rem', cursor: 'pointer', transition: 'all 0.2s', border: '1px solid var(--border-color)' }} onClick={() => setInput("Explain the core data models and database connections used.")}>
                      <span className="text-sm">"Explain the core data models and database connections used."</span>
                    </div>
                    <div className="card hover-bg-light" style={{ padding: '0.9rem 1rem', cursor: 'pointer', transition: 'all 0.2s', border: '1px solid var(--border-color)' }} onClick={() => setInput("Which functions execute background tasks or jobs?")}>
                      <span className="text-sm">"Which functions execute background tasks or jobs?"</span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="card hover-bg-light" style={{ padding: '1rem', cursor: 'pointer', transition: 'all 0.2s' }} onClick={() => setInput("How many customers currently have an ACTIVE status?")}>
                      <span className="text-sm">"How many customers currently have an ACTIVE status?"</span>
                    </div>
                    <div className="card hover-bg-light" style={{ padding: '1rem', cursor: 'pointer', transition: 'all 0.2s' }} onClick={() => setInput("Show me top 5 users by created_at date")}>
                      <span className="text-sm">"Show me top 5 users by created_at date"</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`message-bubble ${m.role}`}>
              <div className={`message-avatar ${m.role}`}>
                {m.role === 'user' ? <User size={20} /> : <Bot size={20} />}
              </div>

              <div className="message-content">
                {m.role === 'user' ? (
                  <div>{m.content}</div>
                ) : (
                  <div style={{ width: '100%' }}>
                    {m.isError && (
                      <div className="badge badge-danger" style={{ marginBottom: '1rem', padding: '0.5rem', borderRadius: '8px' }}>
                        <AlertTriangle size={16} style={{ marginRight: '8px' }} /> {m.content}
                      </div>
                    )}

                    {!m.isError && (m.sql || m.content || m.answer) && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', width: '100%' }}>
                        {/* 1. Executive Summary — suppress for pure single-metric KPI cards */}
                        {m.answer_markdown && (
                          <div className="business-answer">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                h2: ({ children }) => (
                                  <h2 style={{
                                    fontSize: '1.05rem',
                                    margin: '1rem 0 0.4rem',
                                    color: 'var(--text-main)',
                                  }}>
                                    {children}
                                  </h2>
                                ),
                                p: ({ children }) => (
                                  <p style={{
                                    margin: '0.35rem 0',
                                    lineHeight: 1.65,
                                  }}>
                                    {children}
                                  </p>
                                ),
                                ul: ({ children }) => (
                                  <ul style={{
                                    paddingLeft: '1.25rem',
                                    margin: '0.4rem 0',
                                  }}>
                                    {children}
                                  </ul>
                                ),
                                li: ({ children }) => (
                                  <li style={{ marginBottom: '0.3rem' }}>
                                    {children}
                                  </li>
                                ),
                              }}
                            >
                              {m.answer_markdown}
                            </ReactMarkdown>
                          </div>
                        )}

                        {/* 2. Primary Visualization */}
                        {m.result_data && m.result_data.length > 0 && (
                          <div style={{ marginTop: '0.5rem', width: '100%' }}>
                            <div className="flex justify-between items-center mb-4">
                              <div className="flex items-center gap-2">
                                <BarChart2 size={18} className="text-primary" style={{ color: '#6366F1' }} />
                                <span className="text-base font-bold" style={{ color: 'var(--text-main)' }}>
                                  {m.title || (m.recommended_visualization && typeof m.recommended_visualization === 'object' ? m.recommended_visualization.title : null) || m.question || 'Query Result'}
                                </span>
                              </div>
                              <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button className="btn-secondary" onClick={() => handleDownloadCSV(m)} style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem' }} title="Download CSV">
                                  <Download size={14} style={{ marginRight: '0.25rem' }} /> Download CSV
                                </button>
                                <button className="btn-secondary" onClick={() => handleSaveInsight(m)} style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem' }}>
                                  <Save size={14} style={{ marginRight: '0.25rem' }} /> Save Insight
                                </button>
                              </div>
                            </div>
                            {m.data_truncated && (
                              <div
                                className="badge badge-warning"
                                style={{
                                  marginBottom: '1rem',
                                  padding: '0.5rem 0.75rem',
                                  borderRadius: '8px',
                                  display: 'block',
                                }}
                              >
                                Showing the first {m.row_count} rows. Download or refine the query for a complete result.
                              </div>
                            )}

                            {(() => {
                              const rows = m.result_data || m.rows || [];
                              const cols = m.columns || (rows.length > 0 && typeof rows[0] === 'object' ? Object.keys(rows[0]) : []);

                              let resolvedType = m.visualization || m.chart_recommendation;
                              if (typeof m.recommended_visualization === 'object' && m.recommended_visualization !== null) {
                                resolvedType = m.recommended_visualization.visualization || m.recommended_visualization.chart_type || resolvedType;
                              } else if (typeof m.recommended_visualization === 'string') {
                                resolvedType = m.recommended_visualization;
                              }

                              if (!resolvedType) {
                                if (rows.length === 1 && cols.length === 1) resolvedType = 'kpi_card';
                                else if (rows.length === 1 && cols.length > 1) resolvedType = 'detail_card';
                                else if (rows.length > 20) resolvedType = 'table';
                                else if (rows.length > 1 && cols.length >= 2) resolvedType = 'bar_chart';
                                else resolvedType = 'table';
                              }

                              const cardTitle = m.title || (m.result_data && m.result_data.title) || (m.recommended_visualization && typeof m.recommended_visualization === 'object' ? m.recommended_visualization.title : undefined) || m.question;

                              // Resolve column_types from API response or persisted result_data
                              const columnTypes: Record<string, string> =
                                m.column_types ||
                                (m.result_data && typeof m.result_data === 'object' && !Array.isArray(m.result_data) ? m.result_data.column_types : undefined) ||
                                (m.recommended_visualization && typeof m.recommended_visualization === 'object' ? m.recommended_visualization.profile?.column_types : undefined) ||
                                {};

                              const containerHeight = resolvedType === 'kpi_card' ? '180px' : (resolvedType === 'detail_card' ? '220px' : (resolvedType === 'multi_kpi' ? '160px' : '380px'));

                              return (
                                <div style={{ height: containerHeight, width: '100%' }}>
                                  <ChartRenderer
                                    data={rows}
                                    chartType={resolvedType}
                                    title={cardTitle}
                                    columns={cols}
                                    columnTypes={columnTypes}
                                    onPointClick={(pt) => {
                                      if (pt.category) {
                                        setInput(`Break down ${pt.category} in more detail`);
                                      }
                                    }}
                                  />
                                </div>
                              );
                            })()}
                          </div>
                        )}

                        {/* 3. Collapsible SQL Accordion */}
                        {m.sql && (
                          <SqlAccordion sql={m.sql} />
                        )}

                        {/* 4. Collapsible Raw Data Accordion — renders a proper HTML table, never ChartRenderer */}
                        {m.result_data && m.result_data.length > 0 && (() => {
                          const rawRows: any[] = m.result_data || [];
                          const rawCols: string[] = m.columns || (rawRows.length > 0 ? Object.keys(rawRows[0]) : []);
                          return (
                            <details className="raw-data-accordion" style={{
                              backgroundColor: 'var(--bg-card, #1a1a24)',
                              border: '1px solid var(--border-color, #2b2b40)',
                              borderRadius: '10px',
                              padding: '0.6rem 1rem',
                              fontSize: '0.85rem'
                            }}>
                              <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--text-muted)', fontSize: '0.85rem', userSelect: 'none', outline: 'none' }}>
                                View Raw Data Grid ({m.row_count || rawRows.length} rows)
                              </summary>
                              <div style={{ marginTop: '0.75rem', maxHeight: '320px', overflowY: 'auto', overflowX: 'auto' }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                                  <thead>
                                    <tr>
                                      {rawCols.map(col => (
                                        <th key={col} style={{
                                          padding: '0.4rem 0.75rem',
                                          textAlign: 'left',
                                          borderBottom: '2px solid var(--border-color)',
                                          color: 'var(--text-muted)',
                                          fontWeight: 700,
                                          textTransform: 'uppercase',
                                          letterSpacing: '0.05em',
                                          whiteSpace: 'nowrap'
                                        }}>{col.replace(/_/g, ' ')}</th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {rawRows.map((row, ri) => (
                                      <tr key={ri} style={{ borderBottom: '1px solid var(--border-color)', background: ri % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.02)' }}>
                                        {rawCols.map(col => (
                                          <td key={col} style={{ padding: '0.4rem 0.75rem', color: 'var(--text-main)', fontVariantNumeric: 'tabular-nums' }}>
                                            {row[col] === null || row[col] === undefined ? <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>null</span> : String(row[col])}
                                          </td>
                                        ))}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </details>
                          );
                        })()}

                        {/* Code Intelligence: Referenced Files & Symbols */}
                        {((m.referenced_files && m.referenced_files.length > 0) || (m.referenced_symbols && m.referenced_symbols.length > 0)) && (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
                            {m.referenced_files?.map((fp: string) => (
                              <span
                                key={fp}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.35rem',
                                  padding: '0.2rem 0.55rem',
                                  background: 'rgba(236,72,153,0.08)',
                                  border: '1px solid rgba(236,72,153,0.25)',
                                  borderRadius: '6px',
                                  fontSize: '0.75rem',
                                  color: '#ec4899',
                                  fontFamily: 'monospace',
                                }}
                                title={`Referenced File: ${fp}`}
                              >
                                <FileCode2 size={12} />
                                {fp}
                              </span>
                            ))}
                            {m.referenced_symbols?.map((sym: string) => (
                              <span
                                key={sym}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.35rem',
                                  padding: '0.2rem 0.55rem',
                                  background: 'rgba(99,102,241,0.08)',
                                  border: '1px solid rgba(99,102,241,0.25)',
                                  borderRadius: '6px',
                                  fontSize: '0.75rem',
                                  color: 'var(--primary)',
                                  fontFamily: 'monospace',
                                  cursor: 'pointer',
                                }}
                                onClick={() => setInput(`Explain how ${sym} is implemented and where it is called`)}
                                title={`Click to ask about ${sym}`}
                              >
                                <Code size={12} />
                                {sym}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Code Intelligence: Neo4j Graph Architecture Facts */}
                        {m.graph_facts && m.graph_facts.length > 0 && (
                          <GraphFactsAccordion facts={m.graph_facts} />
                        )}

                        {/* Code Intelligence: ChromaDB Retrieved Code Chunks */}
                        {m.retrieved_chunks && m.retrieved_chunks.length > 0 && (
                          <CodeSnippetAccordion chunks={m.retrieved_chunks} />
                        )}

                        {/* 5. Suggested follow-up questions */}
                        {m.follow_up_questions?.length > 0 && (
                          <div
                            style={{
                              display: 'flex',
                              flexWrap: 'wrap',
                              gap: '0.5rem',
                              marginTop: '1rem',
                            }}
                          >
                            {m.follow_up_questions.map(
                              (question: string) => (
                                <button
                                  key={question}
                                  type="button"
                                  className="btn-secondary"
                                  onClick={() => setInput(question)}
                                  style={{
                                    whiteSpace: 'normal',
                                    textAlign: 'left',
                                    fontSize: '0.8rem',
                                  }}
                                >
                                  {question}
                                </button>
                              ),
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {m.confidence_score && (
                      <div className="flex items-center gap-4 mt-4 text-muted text-sm flex-wrap">
                        <div className="flex items-center gap-1" title={m.confidence_reason}>
                          <CheckCircle2 size={14} className="text-success" />
                          <span>Confidence: {(m.confidence_score * 100).toFixed(0)}%</span>
                        </div>

                        {m.execution_time_ms !== undefined && (
                          <div className="flex items-center gap-1">
                            <Clock size={14} className="text-muted" />
                            <span>Executed in {m.execution_time_ms}ms</span>
                          </div>
                        )}

                        <details style={{ cursor: 'pointer', position: 'relative' }} className="group">
                          <summary className="flex items-center gap-1 hover:text-white" style={{ outline: 'none' }}>
                            <Code size={14} /> Execution Trace
                          </summary>
                          <div className="card" style={{ position: 'absolute', bottom: '100%', left: 0, width: '500px', maxWidth: '80vw', zIndex: 50, padding: '1rem', marginBottom: '0.5rem', background: 'var(--bg-dark)' }}>
                            <div className="flex justify-between items-center mb-2">
                              <h4 className="text-sm text-muted m-0">Trace Details</h4>
                              <button className="btn-ghost" style={{ padding: '0.25rem' }} onClick={(e) => { e.preventDefault(); handleCopy(JSON.stringify({ sql: m.generated_sql, plan: m.query_plan, trace: m.trace }, null, 2)); }} title="Copy Trace">
                                <Copy size={12} />
                              </button>
                            </div>
                            <pre style={{ background: 'var(--bg-card)', padding: '1rem', borderRadius: 'var(--radius-sm)', overflowX: 'auto', fontSize: '0.75rem', border: '1px solid var(--border-color)', margin: 0, maxHeight: '300px', overflowY: 'auto' }}>
                              {m.generated_sql && `SQL:\n${m.generated_sql}\n\n`}
                              {m.query_plan && `Plan:\n${JSON.stringify(m.query_plan, null, 2)}\n\n`}
                              {m.trace && `Router Trace:\n${JSON.stringify(m.trace, null, 2)}`}
                            </pre>
                          </div>
                        </details>

                        <div className="flex-1" />

                        <div className="flex items-center gap-2">
                          <button className="btn-ghost" style={{ padding: '0.25rem' }} onClick={() => handleCopy(m.answer_markdown || m.answer || m.content || '')} title="Copy response"><Copy size={14} /></button>
                          <button className="btn-ghost" style={{ padding: '0.25rem' }} title="Regenerate"><RefreshCcw size={14} /></button>
                          <button className="btn-ghost" style={{ padding: '0.25rem' }} title="Good response"><ThumbsUp size={14} /></button>
                          <button className="btn-ghost" style={{ padding: '0.25rem' }} title="Bad response"><ThumbsDown size={14} /></button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {/* Initial loading skeleton for the POST request phase */}
          {loading && !messages.some(m => m.status === 'processing') && (
            <div className="message-bubble assistant">
              <div className="message-avatar assistant">
                <Bot size={20} />
              </div>
              <div className="message-content">
                <div className="flex items-center gap-2 text-muted mt-2">
                  <div style={{ display: 'flex', gap: '4px', color: 'var(--primary)' }}>
                    <span className="skeleton" style={{ width: 8, height: 8, borderRadius: '50%', animationDelay: '0ms' }} />
                    <span className="skeleton" style={{ width: 8, height: 8, borderRadius: '50%', animationDelay: '150ms' }} />
                    <span className="skeleton" style={{ width: 8, height: 8, borderRadius: '50%', animationDelay: '300ms' }} />
                  </div>
                  <span className="text-sm"></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} style={{ height: '1px' }} />
        </div>

        <div style={{ background: 'var(--bg-main)', position: 'sticky', bottom: 0, zIndex: 20, paddingBottom: '1.5rem', paddingTop: '1rem' }}>
          <div style={{ margin: '0 auto', maxWidth: '800px' }}>
            {/* Database & Domain Selection Bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem', paddingLeft: '0.25rem', flexWrap: 'wrap' }}>
              {/* Connected Database / Git Repo Selector */}
              {(() => {
                const src = sources.find((s: any) => s.id === selectedSourceId);
                const repo = codeRepos.find((r: any) => r.repo_id === selectedSourceId);
                const isRepo = Boolean(repo);
                const displayName = repo
                  ? (repo.name || repo.url?.split('/').pop()?.replace('.git', '') || 'Git Repo')
                  : (src ? src.name : (sources.length > 0 ? sources[0].name : (codeRepos.length > 0 ? (codeRepos[0].name || codeRepos[0].url?.split('/').pop()?.replace('.git', '')) : 'No Source')));

                return (
                  <div style={{ position: 'relative' }}>
                    <button
                      type="button"
                      onClick={() => { setShowSourcePicker(prev => !prev); setShowDomainPicker(false); }}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                        padding: '0.25rem 0.65rem',
                        background: 'var(--bg-card)',
                        border: isRepo ? '1px solid rgba(236, 72, 153, 0.4)' : '1px solid var(--border-color)',
                        borderRadius: '99px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        color: 'var(--text-main)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      title="Switch connected database or git repository"
                    >
                      {isRepo ? (
                        <FolderGit2 size={13} style={{ color: '#ec4899' }} />
                      ) : (
                        <Database size={13} style={{ color: 'var(--primary)' }} />
                      )}
                      <span>{isRepo ? `Repo: ${displayName}` : displayName}</span>
                      <span style={{ fontSize: '0.7rem', opacity: 0.6 }}>▾</span>
                    </button>

                    {/* Source Picker Popover */}
                    {showSourcePicker && (
                      <div
                        style={{
                          position: 'absolute', bottom: 'calc(100% + 8px)', left: 0,
                          background: 'var(--bg-card)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '12px',
                          boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
                          padding: '0.5rem',
                          minWidth: '280px',
                          maxHeight: '380px',
                          overflowY: 'auto',
                          zIndex: 100,
                        }}
                      >
                        {/* Section 1: SQL Databases */}
                        <div style={{ padding: '0.4rem 0.6rem 0.3rem', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <Database size={12} style={{ color: 'var(--primary)' }} /> Connected Databases
                        </div>
                        {sources.map((s: any) => (
                          <button
                            key={s.id}
                            type="button"
                            onClick={async () => {
                              setSelectedSourceId(s.id);
                              localStorage.setItem('active_chat_source_id', s.id);
                              setShowSourcePicker(false);
                              if (convId) {
                                setConversations(prev => prev.map(c => c.id === convId ? { ...c, source_id: s.id } : c));
                                try {
                                  await fetchApi(`/engine/conversations/${convId}`, {
                                    method: 'PATCH',
                                    body: JSON.stringify({ source_id: s.id }),
                                  });
                                  await loadConversationsList();
                                } catch (e) {
                                  console.error('Failed to update conversation source', e);
                                }
                              }
                            }}
                            style={{
                              display: 'flex', alignItems: 'center', gap: '0.5rem',
                              width: '100%', padding: '0.5rem 0.75rem',
                              background: selectedSourceId === s.id ? 'rgba(99,102,241,0.1)' : 'transparent',
                              border: 'none', borderRadius: '8px',
                              cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500,
                              color: selectedSourceId === s.id ? 'var(--primary)' : 'var(--text-main)',
                              textAlign: 'left',
                            }}
                          >
                            <Database size={14} style={{ color: selectedSourceId === s.id ? 'var(--primary)' : 'var(--text-muted)' }} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</div>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{s.database_name} ({s.type})</div>
                            </div>
                            {selectedSourceId === s.id && <span style={{ fontSize: '0.75rem', color: 'var(--primary)', fontWeight: 700 }}>✓</span>}
                          </button>
                        ))}
                        {sources.length === 0 && (
                          <div style={{ padding: '0.3rem 0.75rem 0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>No databases connected</div>
                        )}

                        {/* Section 2: Git Repositories */}
                        <div style={{ padding: '0.6rem 0.6rem 0.3rem', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', borderTop: '1px solid var(--border-color)', marginTop: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <FolderGit2 size={12} style={{ color: '#ec4899' }} /> Git Repositories
                        </div>
                        {codeRepos.map((r: any) => {
                          const rName = r.name || r.url?.split('/').pop()?.replace('.git', '') || 'Repository';
                          return (
                            <button
                              key={r.repo_id}
                              type="button"
                              onClick={async () => {
                                setSelectedSourceId(r.repo_id);
                                localStorage.setItem('active_chat_source_id', r.repo_id);
                                setShowSourcePicker(false);
                                if (convId) {
                                  setConversations(prev => prev.map(c => c.id === convId ? { ...c, source_id: r.repo_id } : c));
                                  try {
                                    await fetchApi(`/engine/conversations/${convId}`, {
                                      method: 'PATCH',
                                      body: JSON.stringify({ source_id: r.repo_id }),
                                    });
                                    await loadConversationsList();
                                  } catch (e) {
                                    console.error('Failed to update conversation source', e);
                                  }
                                }
                              }}
                              style={{
                                display: 'flex', alignItems: 'center', gap: '0.5rem',
                                width: '100%', padding: '0.5rem 0.75rem',
                                background: selectedSourceId === r.repo_id ? 'rgba(236,72,153,0.1)' : 'transparent',
                                border: 'none', borderRadius: '8px',
                                cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500,
                                color: selectedSourceId === r.repo_id ? '#ec4899' : 'var(--text-main)',
                                textAlign: 'left',
                              }}
                            >
                              <FolderGit2 size={14} style={{ color: selectedSourceId === r.repo_id ? '#ec4899' : 'var(--text-muted)' }} />
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rName}</div>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.url}</div>
                              </div>
                              {selectedSourceId === r.repo_id && <span style={{ fontSize: '0.75rem', color: '#ec4899', fontWeight: 700 }}>✓</span>}
                            </button>
                          );
                        })}
                        {codeRepos.length === 0 && (
                          <div style={{ padding: '0.3rem 0.75rem 0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>No git repositories connected</div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })()}
              {/* Selected domain chip */}
              {selectedDomainId && (() => {
                const dom = domains.find((d: any) => d.id === selectedDomainId);
                return dom ? (
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                    padding: '0.25rem 0.65rem',
                    background: 'rgba(99,102,241,0.12)',
                    border: '1px solid rgba(99,102,241,0.3)',
                    borderRadius: '99px',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    color: 'var(--primary)',
                  }}>
                    🎯 {dom.name}
                    <button
                      type="button"
                      onClick={async () => {
                        setSelectedDomainId('');
                        if (convId) {
                          try {
                            await fetchApi(`/engine/conversations/${convId}`, {
                              method: 'PATCH',
                              body: JSON.stringify({ domain_id: null }),
                            });
                          } catch (e) {
                            console.error('Failed to update conversation domain', e);
                          }
                        }
                      }}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, lineHeight: 1, color: 'var(--primary)', opacity: 0.7, marginLeft: '2px' }}
                      title="Remove domain context"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ) : null;
              })()}
            </div>

            <form onSubmit={sendMessage} className="chat-input-wrapper" style={{ position: 'relative' }}>
              {/* Domain picker + button */}
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center', marginLeft: '0.5rem', marginRight: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowDomainPicker(prev => !prev)}
                  title="Choose domain context"
                  style={{
                    width: '30px', height: '30px', borderRadius: '50%', padding: 0,
                    background: selectedDomainId ? 'rgba(99,102,241,0.1)' : 'transparent',
                    border: 'none',
                    color: selectedDomainId ? 'var(--primary)' : 'var(--text-main)',
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                    transition: 'all 0.15s',
                  }}
                >
                  <Plus size={20} />
                </button>

                {/* Domain Picker Popover */}
                {showDomainPicker && (
                  <div
                    style={{
                      position: 'absolute', bottom: 'calc(100% + 15px)', left: '-20px',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '12px',
                      // boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
                      padding: '0.5rem',
                      minWidth: '260px',
                      zIndex: 100,
                    }}
                  >
                    <div style={{ padding: '0.4rem 0.6rem 0.5rem', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Domain Context
                    </div>
                    {/* Default / clear option */}
                    <button
                      type="button"
                      onClick={async () => {
                        setSelectedDomainId('');
                        setShowDomainPicker(false);
                        if (convId) {
                          try {
                            await fetchApi(`/engine/conversations/${convId}`, {
                              method: 'PATCH',
                              body: JSON.stringify({ domain_id: null }),
                            });
                          } catch (e) {
                            console.error('Failed to update conversation domain', e);
                          }
                        }
                      }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '0.5rem',
                        width: '100%', padding: '0.5rem 0.75rem',
                        background: !selectedDomainId ? 'rgba(99,102,241,0.1)' : 'transparent',
                        border: 'none', borderRadius: '8px',
                        cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500,
                        color: !selectedDomainId ? 'var(--primary)' : 'var(--text-main)',
                        textAlign: 'left',
                      }}
                    >
                      All Database Tables
                      {!selectedDomainId && <span style={{ marginLeft: 'auto', fontSize: '0.7rem', opacity: 0.7 }}>✓</span>}
                    </button>
                    {domains.length > 0 && <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.3rem 0.25rem' }} />}
                    {domains.map((d: any) => (
                      <button
                        key={d.id}
                        type="button"
                        onClick={async () => {
                          setSelectedDomainId(d.id);
                          setShowDomainPicker(false);
                          if (convId) {
                            try {
                              await fetchApi(`/engine/conversations/${convId}`, {
                                method: 'PATCH',
                                body: JSON.stringify({ domain_id: d.id }),
                              });
                            } catch (e) {
                              console.error('Failed to update conversation domain', e);
                            }
                          }
                        }}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '0.5rem',
                          width: '100%', padding: '0.5rem 0.75rem',
                          background: selectedDomainId === d.id ? 'rgba(99,102,241,0.1)' : 'transparent',
                          border: 'none', borderRadius: '8px',
                          cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500,
                          color: selectedDomainId === d.id ? 'var(--primary)' : 'var(--text-main)',
                          textAlign: 'left',
                        }}
                      >
                        {d.name}
                        {d.source_name && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '0.25rem' }}>({d.source_name})</span>}
                        {selectedDomainId === d.id && <span style={{ marginLeft: 'auto', fontSize: '0.7rem', opacity: 0.7 }}>✓</span>}
                      </button>
                    ))}
                    {domains.length === 0 && (
                      <div style={{ padding: '0.5rem 0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>No domains created yet.</div>
                    )}
                  </div>
                )}
              </div>

              <textarea
                style={{
                  flex: 1,
                  padding: '0.65rem 0',
                  fontSize: '0.95rem',
                  resize: 'none',
                  minHeight: '40px',
                  maxHeight: '120px',
                  overflowY: 'auto',
                  lineHeight: '1.4',
                  background: 'transparent',
                  border: 'none',
                  color: 'inherit',
                  outline: 'none',
                  boxShadow: 'none',
                  fontFamily: 'inherit',
                }}
                rows={1}
                placeholder={isCodeRepoSelected ? "Ask about architecture, functions, call hierarchies, endpoints..." : "Ask a question about your business data..."}
                value={input}
                onChange={e => {
                  setInput(e.target.value);
                  e.target.style.height = 'auto';
                  e.target.style.height = `${e.target.scrollHeight}px`;
                }}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (!loading && input.trim()) {
                      sendMessage(e as any);
                    }
                  }
                }}
                disabled={loading}
                autoFocus
                onFocus={() => setShowDomainPicker(false)}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                style={{
                  borderRadius: '50%',
                  width: '32px',
                  height: '32px',
                  padding: 0,
                  background: input.trim() ? 'var(--primary)' : 'var(--bg-hover)',
                  color: input.trim() ? 'white' : 'var(--text-muted)',
                  marginRight: '0.5rem',
                  transition: 'all 0.2s',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}
              >
                <Send size={15} style={{ transform: 'translateX(-1px)' }} />
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="modal-overlay" onClick={() => setDeleteTarget(null)}>
          <div className="modal-content" style={{ maxWidth: '420px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: 'var(--text-main)' }}>
                <AlertTriangle size={18} style={{ color: '#ef4444' }} /> Delete Chat
              </div>
              <button className="btn-ghost" onClick={() => setDeleteTarget(null)} disabled={isDeleting} style={{ padding: '4px' }}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body" style={{ padding: '1.25rem 1.5rem' }}>
              <p style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-main)', lineHeight: 1.5 }}>
                Are you sure you want to delete this chat?
              </p>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem', background: 'var(--bg-main)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                "{deleteTarget.title || 'New Conversation'}"
              </div>
            </div>
            <div className="modal-footer" style={{ padding: '0.75rem 1.25rem', gap: '0.5rem' }}>
              <button className="btn-secondary" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
                Cancel
              </button>
              <button
                onClick={confirmDeleteChat}
                disabled={isDeleting}
                style={{ background: '#ef4444', borderColor: '#ef4444', color: 'white' }}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
