import React, { useState, useEffect, useRef } from 'react';
import { fetchApi } from '../../services/api';
import { ChartRenderer } from '../../components/visualizations/ChartRenderer';
import { Save, Send, AlertTriangle, Info, CheckCircle2, Copy, RefreshCcw, ThumbsUp, ThumbsDown, User, Bot, Database, Code, Table, Plus, MessageSquare, Search, Trash2, Edit2, Clock, X } from 'lucide-react';
import { PipelineProgress } from '../../components/chat/PipelineProgress';
import { SqlBlock } from '../../components/chat/SqlBlock';

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

      const normalizedMessages = (data.messages || []).map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        answer: m.role === 'assistant' ? m.content : undefined,
        sql: m.generated_sql,
        result_data: m.result_data?.rows || (Array.isArray(m.result_data) ? m.result_data : []),
        execution_time_ms: m.execution_time_ms,
        status: m.status,
        generated_at: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : undefined,
        database: 'analytics_db'
      }));
      setMessages(normalizedMessages);
    } catch (e) {
      console.error(e);
    }
  };

  const handleNewChat = async () => {
    try {
      const data = await fetchApi('/engine/conversations', { method: 'POST' });
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

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const questionText = input.trim();
    const userMsg = { id: Date.now(), role: 'user', content: questionText };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await fetchApi('/api/v1/chat/sql', {
        method: 'POST',
        body: JSON.stringify({
          question: questionText,
          conversation_id: convId
        })
      });

      if (data.conversation_id && data.conversation_id !== convId) {
        setConvId(data.conversation_id);
        localStorage.setItem('active_conversation_id', data.conversation_id);
      }

      const botMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        question: data.question,
        answer: data.answer,
        sql: data.sql,
        result_data: Array.isArray(data.rows) ? data.rows : (Array.isArray(data.result_data) ? data.result_data : []),
        rows: Array.isArray(data.rows) ? data.rows : (Array.isArray(data.result_data) ? data.result_data : []),
        columns: data.columns || (Array.isArray(data.rows) && data.rows.length > 0 ? Object.keys(data.rows[0]) : []),
        row_count: data.row_count !== undefined ? data.row_count : (Array.isArray(data.rows) ? data.rows.length : 0),
        execution_time_ms: data.execution_time_ms,
        generated_at: data.generated_at,
        database: data.database || 'analytics_db',
        content: data.answer || data.sql
      };
      setMessages(prev => [...prev, botMsg]);
      await loadConversationsList();
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: err.message || 'Failed to generate SQL query.', isError: true }]);
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
          chart_config: { chartType: 'table', data: msg.result_data || [] }
        })
      });
      alert('Insight saved successfully! You can add it to a Dashboard.');
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const filteredConversations = conversations.filter(c =>
    c.title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', gap: '2rem', height: '100%', flex: 1, minHeight: 0 }}>
      {/* Sidebar */}
      <div style={{ width: '220px', display: 'flex', flexDirection: 'column', gap: '1.5rem', flexShrink: 0, borderRight: '1px solid var(--border-color)', paddingRight: '1rem', height: '100%', minHeight: 0 }}>
        <div>
          <button className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={handleNewChat}>
            <Plus size={16} style={{ marginRight: '0.5rem' }} /> New Chat
          </button>
        </div>

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

      {/* Main Chat Area */}
      <div className="chat-container" style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0, margin: '0 auto', maxWidth: '860px', width: '100%' }}>
        <div className="chat-messages" style={{ flex: 1, overflowY: 'auto', padding: '0 1rem', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {messages.length === 0 && (
            <div style={{ margin: 'auto', textAlign: 'center', maxWidth: '500px' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(91, 82, 232, 0.1)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
                <Bot size={32} />
              </div>
              <h2 style={{ fontSize: '1.75rem', marginBottom: '0.5rem', color: 'var(--text-main)' }}>How can I help you today?</h2>
              <p style={{ color: 'var(--text-muted)' }}>Ask a question about your business data in plain English to generate SQL & view live results.</p>

              <div className="grid grid-cols-2 gap-3 mt-4" style={{ textAlign: 'left' }}>
                <div className="card hover-bg-light" style={{ padding: '1rem', cursor: 'pointer', transition: 'all 0.2s' }} onClick={() => setInput("How many customers currently have an ACTIVE status?")}>
                  <span className="text-sm">"How many customers currently have an ACTIVE status?"</span>
                </div>
                <div className="card hover-bg-light" style={{ padding: '1rem', cursor: 'pointer', transition: 'all 0.2s' }} onClick={() => setInput("Show me top 5 users by created_at date")}>
                  <span className="text-sm">"Show me top 5 users by created_at date"</span>
                </div>
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
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
                        {m.answer && (
                          <div style={{ fontSize: '0.95rem', lineHeight: 1.6, fontWeight: 500, color: 'var(--text-main)' }}>
                            {m.answer}
                          </div>
                        )}

                        {m.result_data && m.result_data.length > 0 && (
                          <div className="card" style={{ padding: '1.25rem', border: '1px solid var(--border-color)', background: 'var(--bg-dark)' }}>
                            <div className="flex justify-between items-center mb-3">
                              <div className="flex items-center gap-2">
                                <Table size={16} className="text-muted" />
                                <span className="text-sm font-semibold">Result Data ({m.row_count || m.result_data.length} rows)</span>
                              </div>
                              <button className="btn-secondary" onClick={() => handleSaveInsight(m)} style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}>
                                <Save size={14} /> Save Insight
                              </button>
                            </div>
                            <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                              <ChartRenderer data={m.result_data} chartType="table" />
                            </div>
                          </div>
                        )}

                        {m.sql && (
                          <div className="my-1">
                            <SqlBlock sql={m.sql} defaultOpen={false} />
                          </div>
                        )}

                        {m.question && (
                          <div style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '1.25rem',
                            fontSize: '0.75rem',
                            color: 'var(--text-muted)',
                            padding: '0.5rem 0.75rem',
                            backgroundColor: 'var(--bg-input, #1e1e2d)',
                            borderRadius: '6px',
                            border: '1px solid var(--border-color, #2b2b40)',
                            marginTop: '0.25rem'
                          }}>
                            <div><strong style={{ color: 'var(--text-main)' }}>Question:</strong> {m.question}</div>
                            <div><strong style={{ color: 'var(--text-main)' }}>Database Name:</strong> {m.database || 'analytics_db'}</div>
                            {m.execution_time_ms !== undefined && (
                              <div><strong style={{ color: 'var(--text-main)' }}>Execution Time:</strong> {m.execution_time_ms}ms</div>
                            )}
                            <div><strong style={{ color: 'var(--text-main)' }}>Generation Time:</strong> {m.generated_at}</div>
                          </div>
                        )}
                      </div>
                    )}

                    {m.status === 'processing' && (
                      <div className="mt-4 p-4 border border-gray-100 rounded-lg bg-white shadow-sm">
                        <PipelineProgress trace={m.trace} />
                      </div>
                    )}

                    {m.result_data && (
                      <div className="card mt-4" style={{ padding: '1.5rem', border: '1px solid var(--border-color)', background: 'var(--bg-dark)' }}>
                        <div className="flex justify-between items-center mb-4">
                          <div className="flex items-center gap-2">
                            <Table size={16} className="text-muted" />
                            <span className="text-sm font-medium">Result Data</span>
                          </div>
                          <button className="btn-secondary" onClick={() => handleSaveInsight(m)} style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}>
                            <Save size={14} /> Save Insight
                          </button>
                        </div>
                        <div style={{ height: m.chart_recommendation === 'kpi_card' ? '120px' : '350px' }}>
                          <ChartRenderer data={m.result_data} chartType={m.chart_recommendation || 'table'} />
                        </div>
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
                          <button className="btn-ghost" style={{ padding: '0.25rem' }} onClick={() => handleCopy(m.content)} title="Copy response"><Copy size={14} /></button>
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
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <span className="skeleton" style={{ width: 8, height: 8, borderRadius: '50%', animationDelay: '0ms' }} />
                    <span className="skeleton" style={{ width: 8, height: 8, borderRadius: '50%', animationDelay: '150ms' }} />
                    <span className="skeleton" style={{ width: 8, height: 8, borderRadius: '50%', animationDelay: '300ms' }} />
                  </div>
                  <span className="text-sm">Connecting...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} style={{ height: '1px' }} />
        </div>

        <div style={{ background: 'var(--bg-main)', flexShrink: 0, paddingTop: '0.75rem', paddingBottom: '0.5rem', width: '100%', zIndex: 20 }}>
          <form onSubmit={sendMessage} className="chat-input-wrapper" style={{ margin: '0 auto', maxWidth: '800px' }}>
            <input
              style={{ flex: 1, padding: '1rem', fontSize: '0.95rem' }}
              placeholder="Ask a question about your data..."
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={loading}
              autoFocus
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                borderRadius: '50%',
                width: '40px',
                height: '40px',
                padding: 0,
                background: input.trim() ? 'var(--primary)' : 'var(--bg-hover)',
                color: input.trim() ? 'white' : 'var(--text-muted)',
                marginRight: '0.5rem',
                transition: 'all 0.2s'
              }}
            >
              <Send size={18} style={{ transform: 'translateX(-1px)' }} />
            </button>
          </form>
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

