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

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`border border-gray-200 rounded-lg overflow-hidden bg-gray-50 ${className}`}>
      {/* Header / Toggle bar */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2 bg-gray-100 hover:bg-gray-200 transition-colors focus:outline-none"
      >
        <div className="flex items-center space-x-2 text-sm font-medium text-gray-700">
          <Terminal className="w-4 h-4" />
          <span>{isOpen ? "Hide SQL" : "Show SQL"}</span>
        </div>
      </button>

      {/* Code Body */}
      {isOpen && (
        <div className="relative group border-t border-gray-200">
          <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleCopy}
              className="p-1.5 bg-gray-800 text-gray-300 rounded hover:text-white hover:bg-gray-700 transition-colors shadow-sm"
              title="Copy SQL"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <SyntaxHighlighter
            language="sql"
            style={atomDark}
            customStyle={{
              margin: 0,
              padding: "1rem",
              background: "#1e1e1e", // Custom dark background
              fontSize: "0.875rem",
              borderRadius: "0",
            }}
          >
            {sql}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  );
}
