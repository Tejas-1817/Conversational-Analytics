import React, { useState, useEffect, useRef } from 'react';
import { fetchApi } from '../../services/api';
import { ChartRenderer } from '../../components/visualizations/ChartRenderer';
import { Save, Send, AlertTriangle, Info, CheckCircle2, Copy, RefreshCcw, ThumbsUp, ThumbsDown, User, Bot, Database, Code, Table, Plus, MessageSquare, Search, Trash2, Edit2 } from 'lucide-react';

export const ChatInterface = () => {
  const [conversations, setConversations] = useState<any[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadConversations = async () => {
    try {
      const data = await fetchApi('/engine/conversations');
      setConversations(data);
      if (data.length > 0 && !convId) {
        loadConversation(data[0].id);
      } else if (data.length === 0 && !convId) {
        handleNewChat();
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversation = async (id: string) => {
    try {
      const data = await fetchApi(`/engine/conversations/${id}`);
      setConvId(data.id);
      setMessages(data.messages || []);
    } catch (e) {
      console.error(e);
    }
  };

  const handleNewChat = async () => {
    try {
      const data = await fetchApi('/engine/conversations', { method: 'POST' });
      setConvId(data.id);
      setMessages([]);
      loadConversations();
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
        if (msg.status === 'complete' || msg.status === 'error') {
          clearInterval(intervalId);
          setMessages(prev => prev.map(m => m.id === messageId ? msg : m));
          setLoading(false);
          loadConversations();
        }
      } catch (err) {
        console.error('Polling error', err);
        clearInterval(intervalId);
        setLoading(false);
      }
    }, 3000);
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !convId) return;

    const userMsg = { id: Date.now(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await fetchApi(`/engine/conversations/${convId}/query`, {
        method: 'POST',
        body: JSON.stringify({ message: userMsg.content })
      });
      setMessages(prev => [...prev, data]);

      if (data.status === 'processing') {
        // Async job — poll until complete or error
        pollMessageStatus(convId, data.id);
      } else {
        // Synchronous completion (shouldn't happen with current backend, but safe)
        setLoading(false);
        loadConversations();
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: err.message || 'An error occurred.', isError: true }]);
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
          query: msg.intent?.original_query || 'Saved Insight',
          chart_config: { chartType: msg.chart_recommendation, data: msg.result_data }
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
    <div style={{ display: 'flex', gap: '2rem', height: '100%' }}>
      {/* Sidebar */}
      <div style={{ width: '280px', display: 'flex', flexDirection: 'column', gap: '1.5rem', flexShrink: 0, borderRight: '1px solid var(--border-color)', paddingRight: '1rem' }}>
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
                gap: '0.5rem',
                fontSize: '0.85rem'
              }}
              className="hover-bg-light"
            >
              <MessageSquare size={14} style={{ flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{c.title || 'New Conversation'}</span>
            </div>
          ))}
          {filteredConversations.length === 0 && (
            <div className="text-muted text-sm text-center py-4">No conversations found.</div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-container" style={{ flex: 1, height: '100%' }}>
        <div className="chat-messages" style={{ padding: '0 1rem' }}>
          {messages.length === 0 && (
            <div style={{ margin: 'auto', textAlign: 'center', opacity: 0.6, maxWidth: '500px' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(79, 70, 229, 0.1)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
                <Bot size={32} />
              </div>
              <h2 style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>How can I help you today?</h2>
              <p>Ask a question about your business data in plain English.</p>
              
              <div className="grid grid-cols-2 gap-3 mt-4" style={{ textAlign: 'left', opacity: 0.8 }}>
                <div className="card hover-bg-light" style={{ padding: '1rem', cursor: 'pointer', transition: 'all 0.2s' }} onClick={() => setInput("Show me revenue by region for 2026")}>
                  <span className="text-sm">"Show me revenue by region for 2026"</span>
                </div>
                <div className="card hover-bg-light" style={{ padding: '1rem', cursor: 'pointer', transition: 'all 0.2s' }} onClick={() => setInput("What is our average order value?")}>
                  <span className="text-sm">"What is our average order value?"</span>
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
                    
                    {m.route && !m.isError && (
                      <div style={{ marginBottom: '1rem', display: 'flex' }}>
                        {m.route === 'analytics' && <div className="badge badge-primary"><Database size={12} style={{ marginRight: '4px' }} /> Analytics Mode</div>}
                        {m.route === 'conversation' && <div className="badge badge-secondary" style={{ background: 'var(--bg-card)' }}><MessageSquare size={12} style={{ marginRight: '4px' }} /> Conversation Mode</div>}
                        {m.route === 'help' && <div className="badge badge-secondary" style={{ background: 'var(--bg-card)' }}><Info size={12} style={{ marginRight: '4px' }} /> Help Mode</div>}
                        {m.route === 'greeting' && <div className="badge badge-secondary" style={{ background: 'var(--bg-card)' }}><Bot size={12} style={{ marginRight: '4px' }} /> Assistant</div>}
                      </div>
                    )}

                    {!m.isError && (
                      <div style={{ lineHeight: 1.6 }}>
                        {m.content}
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
          {loading && (
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
                  <span className="text-sm">Analyzing query...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} style={{ height: '1px' }} />
        </div>
        
        <div style={{ paddingBottom: '2rem', paddingTop: '1rem', background: 'var(--bg-main)', position: 'sticky', bottom: 0, borderTop: '1px solid var(--border-color)' }}>
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
          <div className="text-center text-muted mt-2" style={{ fontSize: '0.75rem' }}>
            AI Agent can make mistakes. Consider verifying important information against your Data Sources.
          </div>
        </div>
      </div>
    </div>
  );
};
