import React, { useState, useRef, useEffect } from 'react';
import { X, ChevronDown, ChevronUp, Check, AlertCircle } from 'lucide-react';

interface AddUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  domainName?: string;
  onInvite?: (email: string, role: string) => Promise<void> | void;
}

const ROLES = [
  { id: 'Explorer', label: 'Explorer', description: 'Can view dashboards, query data, and ask AI questions' },
  { id: 'Data Administrator', label: 'Data Administrator', description: 'Full access to schema, tables, and settings' },
  { id: 'Observer', label: 'Observer', description: 'Read-only access to published dashboards' },
];

export const AddUserModal: React.FC<AddUserModalProps> = ({
  isOpen,
  onClose,
  domainName,
  onInvite,
}) => {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('Explorer');
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const modalRef = useRef<HTMLDivElement | null>(null);

  // Reset state when opening
  useEffect(() => {
    if (isOpen) {
      setEmail('');
      setRole('Explorer');
      setIsRoleDropdownOpen(false);
      setSuccessMessage(null);
      setErrorMessage(null);
    }
  }, [isOpen]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsRoleDropdownOpen(false);
      }
    };
    if (isRoleDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isRoleDropdownOpen]);

  // Handle Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isRoleDropdownOpen) {
          setIsRoleDropdownOpen(false);
        } else {
          onClose();
        }
      }
    };
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isRoleDropdownOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setErrorMessage('Please enter a valid work email address');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setErrorMessage('Please enter a valid email format');
      return;
    }

    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      if (onInvite) {
        await onInvite(email.trim(), role);
      }
      setSuccessMessage(`Invitation sent to ${email.trim()} as ${role}!`);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to send invitation');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.45)',
        backdropFilter: 'blur(2px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        animation: 'fadeIn 0.15s ease-out',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        style={{
          background: '#FFFFFF',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '540px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          overflow: 'visible',
          position: 'relative',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '20px 24px 16px',
            borderBottom: '1px solid #F1F5F9',
          }}
        >
          <h2
            style={{
              fontSize: '1.2rem',
              fontWeight: 600,
              color: '#1E293B',
              margin: 0,
              letterSpacing: '-0.01em',
            }}
          >
            Add Users
          </h2>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: '#94A3B8',
              padding: '4px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#1E293B';
              e.currentTarget.style.backgroundColor = '#F1F5F9';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#94A3B8';
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '24px 24px 20px' }}>
          {errorMessage && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                borderRadius: '8px',
                background: '#FEF2F2',
                border: '1px solid #FEE2E2',
                color: '#DC2626',
                fontSize: '13px',
                marginBottom: '16px',
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                borderRadius: '8px',
                background: '#F0FDF4',
                border: '1px solid #DCFCE7',
                color: '#16A34A',
                fontSize: '13px',
                marginBottom: '16px',
              }}
            >
              <Check size={16} />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Work Email Input */}
          <div style={{ marginBottom: '20px' }}>
            <input
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (errorMessage) setErrorMessage(null);
              }}
              placeholder="Work email"
              autoFocus
              style={{
                width: '100%',
                padding: '12px 16px',
                fontSize: '14px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                color: '#1E293B',
                background: '#FFFFFF',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = '#6366F1';
                e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99, 102, 241, 0.1)';
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = '#CBD5E1';
                e.currentTarget.style.boxShadow = 'none';
              }}
            />
          </div>

          {/* Role Selector with Floating-style Label */}
          <div ref={dropdownRef} style={{ position: 'relative', marginBottom: '24px' }}>
            {/* Outline Box with Role Label floating on the border */}
            <div
              onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
              style={{
                position: 'relative',
                width: '100%',
                padding: '12px 16px',
                fontSize: '14px',
                borderRadius: '8px',
                border: isRoleDropdownOpen ? '1.5px solid #6366F1' : '1px solid #CBD5E1',
                background: '#FFFFFF',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                boxSizing: 'border-box',
                userSelect: 'none',
                transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
                boxShadow: isRoleDropdownOpen ? '0 0 0 3px rgba(99, 102, 241, 0.1)' : 'none',
              }}
            >
              {/* Floating Label */}
              <span
                style={{
                  position: 'absolute',
                  top: '-9px',
                  left: '12px',
                  background: '#FFFFFF',
                  padding: '0 4px',
                  fontSize: '11.5px',
                  fontWeight: 500,
                  color: isRoleDropdownOpen ? '#6366F1' : '#64748B',
                }}
              >
                Role
              </span>

              <span style={{ color: role ? '#1E293B' : '#94A3B8' }}>
                {role || 'Role'}
              </span>

              {isRoleDropdownOpen ? (
                <ChevronUp size={16} style={{ color: '#64748B' }} />
              ) : (
                <ChevronDown size={16} style={{ color: '#64748B' }} />
              )}
            </div>

            {/* Dropdown Options Menu */}
            {isRoleDropdownOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 4px)',
                  left: 0,
                  right: 0,
                  background: '#FFFFFF',
                  border: '1px solid #E2E8F0',
                  borderRadius: '8px',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                  zIndex: 1000,
                  padding: '4px 0',
                  animation: 'fadeIn 0.1s ease-out',
                }}
              >
                {ROLES.map((item) => {
                  const isSelected = role === item.id;
                  return (
                    <div
                      key={item.id}
                      onClick={() => {
                        setRole(item.id);
                        setIsRoleDropdownOpen(false);
                      }}
                      style={{
                        padding: '10px 16px',
                        fontSize: '13.5px',
                        color: isSelected ? '#4F46E5' : '#334155',
                        fontWeight: isSelected ? 600 : 400,
                        background: isSelected ? '#F8FAFC' : 'transparent',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        transition: 'background-color 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#F1F5F9';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = isSelected ? '#F8FAFC' : 'transparent';
                      }}
                    >
                      <span>{item.label}</span>
                      {isSelected && <Check size={15} style={{ color: '#4F46E5' }} />}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Action Footer */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '4px' }}>
            <button
              type="submit"
              disabled={isSubmitting || !email.trim()}
              style={{
                background: isSubmitting || !email.trim() ? '#93C5FD' : '#4F46E5',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                padding: '9px 24px',
                fontSize: '13.5px',
                fontWeight: 600,
                cursor: isSubmitting || !email.trim() ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.15s ease, transform 0.1s ease',
                boxShadow: '0 1px 2px rgba(79, 70, 229, 0.2)',
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting && email.trim()) {
                  e.currentTarget.style.backgroundColor = '#4338CA';
                }
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting && email.trim()) {
                  e.currentTarget.style.backgroundColor = '#4F46E5';
                }
              }}
            >
              {isSubmitting ? 'Inviting...' : 'Invite'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
