import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertCircle, RefreshCw, Home } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in React component tree:', error, errorInfo);
    this.setState({ errorInfo });
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            padding: '24px',
            backgroundColor: '#F8FAFC',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          }}
        >
          <div
            style={{
              background: '#FFFFFF',
              borderRadius: '12px',
              padding: '32px',
              maxWidth: '560px',
              width: '100%',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
              border: '1px solid #E2E8F0',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: '#FEF2F2',
                color: '#EF4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
              }}
            >
              <AlertCircle size={24} />
            </div>

            <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#1E293B', margin: '0 0 8px' }}>
              Application Render Issue
            </h2>
            <p style={{ fontSize: '14px', color: '#64748B', margin: '0 0 20px', lineHeight: 1.5 }}>
              {this.state.error?.message || 'An unexpected error occurred while rendering the page.'}
            </p>

            {this.state.error?.stack && (
              <pre
                style={{
                  textAlign: 'left',
                  background: '#F1F5F9',
                  padding: '12px',
                  borderRadius: '6px',
                  fontSize: '11.5px',
                  color: '#475569',
                  overflowX: 'auto',
                  maxHeight: '140px',
                  marginBottom: '20px',
                  fontFamily: 'monospace',
                }}
              >
                {this.state.error.stack}
              </pre>
            )}

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null, errorInfo: null });
                  window.location.reload();
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '9px 18px',
                  borderRadius: '6px',
                  background: '#4F46E5',
                  color: '#FFFFFF',
                  border: 'none',
                  fontSize: '13.5px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <RefreshCw size={14} />
                <span>Reload Page</span>
              </button>

              <button
                onClick={() => {
                  window.location.href = '/domains';
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '9px 18px',
                  borderRadius: '6px',
                  background: '#FFFFFF',
                  color: '#475569',
                  border: '1px solid #CBD5E1',
                  fontSize: '13.5px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <Home size={14} />
                <span>Go to Domains</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
