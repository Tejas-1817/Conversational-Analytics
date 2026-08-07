import { Check, Copy, Terminal } from "lucide-react";
import React, { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { atomDark } from "react-syntax-highlighter/dist/esm/styles/prism";

interface SqlBlockProps {
  sql: string;
  className?: string;
  defaultOpen?: boolean;
}

export function SqlBlock({ sql, className = "", defaultOpen = false }: SqlBlockProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`border border-gray-200 rounded-lg overflow-hidden bg-gray-50 ${className}`}>
      {/* Header / Toggle bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.4rem 1rem',
          background: 'var(--primary, #6366F1)',
          cursor: 'pointer',
        }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', fontWeight: 500, color: 'white' }}>
          <Terminal style={{ width: '14px', height: '14px' }} />
          <span>{isOpen ? "Hide SQL" : "Show SQL"}</span>
        </div>

        <button
          onClick={handleCopy}
          title="Copy SQL"
          style={{
            padding: '0.2rem 0.4rem',
            borderRadius: '4px',
            background: 'rgba(255,255,255,0.15)',
            border: 'none',
            color: 'white',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.25)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.15)')}
        >
          {copied ? <Check style={{ width: '13px', height: '13px', color: '#86efac' }} /> : <Copy style={{ width: '13px', height: '13px' }} />}
        </button>
      </div>

      {/* Code Body */}
      {isOpen && (
        <SyntaxHighlighter
          language="sql"
          style={atomDark}
          customStyle={{
            margin: 0,
            padding: "1rem",
            background: "#1e1e1e",
            fontSize: "0.875rem",
            borderRadius: "0",
          }}
        >
          {sql}
        </SyntaxHighlighter>
      )}
    </div>
  );
}
