import React, { useState, useEffect } from 'react';

export function ChatInterface({ token }: { token: string }) {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);

  useEffect(() => {
    // Create conversation on mount
    fetch('http://localhost:8000/engine/conversations', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => setConvId(data.id))
    .catch(console.error);
  }, [token]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !convId) return;

    const userMsg = { id: Date.now(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`http://localhost:8000/engine/conversations/${convId}/query`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: userMsg.content })
      });
      const data = await res.json();
      setMessages(prev => [...prev, data]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: 'An error occurred.', error: String(err) }]);
    } finally {
      setLoading(false);
    }
  };

  const renderData = (msg: any) => {
    if (!msg.result_data || !msg.result_data.rows || msg.result_data.rows.length === 0) return null;
    const { columns, rows } = msg.result_data;

    return (
      <div style={{ marginTop: '1rem', overflowX: 'auto', background: '#fff', borderRadius: '8px', padding: '1rem' }}>
        <table className="table" style={{ width: '100%' }}>
          <thead>
            <tr>
              {columns.map((c: string) => <th key={c}>{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any, idx: number) => (
              <tr key={idx}>
                {columns.map((c: string) => <td key={c}>{String(r[c])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {messages.map((m, i) => (
          <div key={i} style={{ 
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            background: m.role === 'user' ? '#007bff' : '#f1f1f1',
            color: m.role === 'user' ? '#fff' : '#333',
            padding: '1rem',
            borderRadius: '12px',
            maxWidth: '80%'
          }}>
            <p style={{ margin: 0 }}>{m.content}</p>
            {m.role === 'assistant' && renderData(m)}
            {m.role === 'assistant' && (m.query_plan || m.generated_sql) && (
              <details style={{ marginTop: '0.5rem', fontSize: '0.8rem', opacity: 0.8 }}>
                <summary style={{ cursor: 'pointer' }}>Debug Trace</summary>
                {m.query_plan && <pre>{JSON.stringify(m.query_plan, null, 2)}</pre>}
                {m.generated_sql && <pre>{m.generated_sql}</pre>}
                {m.execution_time_ms && <p>Execution Time: {m.execution_time_ms}ms</p>}
              </details>
            )}
          </div>
        ))}
        {loading && <div style={{ alignSelf: 'flex-start' }}>Typing...</div>}
      </div>
      <form onSubmit={sendMessage} style={{ display: 'flex', gap: '0.5rem', padding: '1rem', borderTop: '1px solid #ddd' }}>
        <input 
          style={{ flex: 1, padding: '0.75rem', borderRadius: '8px', border: '1px solid #ccc' }}
          placeholder="Ask a question about your data..."
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading} style={{ padding: '0 2rem' }}>Send</button>
      </form>
    </div>
  );
}
