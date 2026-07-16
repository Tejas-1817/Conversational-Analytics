import React, { useState, useEffect } from 'react';
import { X, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { z } from 'zod';
import { fetchApi } from '../services/api';

const connectionSchema = z.object({
  name: z.string().min(1, 'Connection Name is required').max(200, 'Name must be 200 characters or less'),
  type: z.enum(['postgres', 'mysql']),
  host: z.string().min(1, 'Host is required').trim(),
  port: z.number().int().positive().optional().or(z.literal('')),
  database_name: z.string().min(1, 'Database Name is required').trim(),
  username: z.string().min(1, 'Username is required').trim(),
  password: z.string().min(1, 'Password is required'),
});

type ConnectionFormData = z.infer<typeof connectionSchema>;

interface ConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ConnectionModal: React.FC<ConnectionModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [formData, setFormData] = useState<ConnectionFormData>({
    name: '',
    type: 'postgres',
    host: '',
    port: 5432,
    database_name: '',
    username: '',
    password: '',
  });

  const [errors, setErrors] = useState<Partial<Record<keyof ConnectionFormData, string>>>({});
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [testSuccess, setTestSuccess] = useState<boolean>(false);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: '',
        type: 'postgres',
        host: '',
        port: 5432,
        database_name: '',
        username: '',
        password: '',
      });
      setErrors({});
      setBackendError(null);
      setTestSuccess(false);
    }
  }, [isOpen]);

  // Handle escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isTesting && !isSaving) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isTesting, isSaving, onClose]);

  if (!isOpen) return null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    // Auto update default port when type changes
    if (name === 'type') {
      const defaultPort = value === 'postgres' ? 5432 : 3306;
      setFormData(prev => ({ ...prev, type: value as any, port: defaultPort }));
      return;
    }

    setFormData(prev => ({
      ...prev,
      [name]: name === 'port' ? (value === '' ? '' : parseInt(value, 10)) : value
    }));
    
    // Clear field specific error
    if (errors[name as keyof ConnectionFormData]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
    setTestSuccess(false);
  };

  const validateForm = (): boolean => {
    try {
      connectionSchema.parse(formData);
      setErrors({});
      return true;
    } catch (err) {
      if (err instanceof z.ZodError) {
        const fieldErrors: any = {};
        err.issues.forEach((e: any) => {
          if (e.path[0]) fieldErrors[e.path[0]] = e.message;
        });
        setErrors(fieldErrors);
      }
      return false;
    }
  };

  const handleTestConnection = async () => {
    if (!validateForm()) return false;
    
    setIsTesting(true);
    setBackendError(null);
    setTestSuccess(false);
    
    try {
      await fetchApi('/sources/test', {
        method: 'POST',
        body: JSON.stringify(formData),
      });
      setTestSuccess(true);
      return true;
    } catch (err: any) {
      // Parse backend HTTP Exception message
      const msg = err.message || 'Connection test failed.';
      setBackendError(msg);
      return false;
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async () => {
    if (!validateForm()) return;

    // Test first before saving as required by the workflow
    const testPassed = await handleTestConnection();
    if (!testPassed) return;

    setIsSaving(true);
    setBackendError(null);

    try {
      await fetchApi('/sources', {
        method: 'POST',
        body: JSON.stringify(formData),
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setBackendError(err.message || 'Failed to save connection.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" role="dialog" aria-modal="true">
        <div className="modal-header">
          <h2>Connect Data Source</h2>
          <button className="btn-ghost" onClick={onClose} disabled={isTesting || isSaving} style={{ padding: '4px' }}>
            <X size={20} />
          </button>
        </div>
        
        <div className="modal-body">
          {backendError && (
            <div className="error-banner">
              <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', marginBottom: '2px' }}>Connection Failed</strong>
                {backendError}
              </div>
            </div>
          )}

          {testSuccess && !backendError && (
            <div className="error-banner" style={{ background: 'rgba(34, 197, 94, 0.1)', borderColor: 'var(--success)', color: 'var(--success)' }}>
              <CheckCircle2 size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>Connection test succeeded!</div>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="name">Connection Name</label>
            <input 
              id="name" 
              name="name" 
              value={formData.name} 
              onChange={handleChange} 
              placeholder="e.g., Production Analytics" 
              disabled={isTesting || isSaving}
            />
            {errors.name && <div className="form-error">{errors.name}</div>}
          </div>

          <div className="grid grid-cols-2 gap-3" style={{ marginBottom: 'var(--space-3)' }}>
            <div>
              <label htmlFor="type" style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: 500 }}>Database Type</label>
              <select 
                id="type" 
                name="type" 
                value={formData.type} 
                onChange={handleChange}
                disabled={isTesting || isSaving}
              >
                <option value="postgres">PostgreSQL</option>
                <option value="mysql">MySQL</option>
              </select>
            </div>
            <div>
              <label htmlFor="database_name" style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: 500 }}>Database Name</label>
              <input 
                id="database_name" 
                name="database_name" 
                value={formData.database_name} 
                onChange={handleChange} 
                placeholder="postgres"
                disabled={isTesting || isSaving}
              />
              {errors.database_name && <div className="form-error">{errors.database_name}</div>}
            </div>
          </div>

          <div className="grid grid-cols-4 gap-3 form-group">
            <div style={{ gridColumn: 'span 3' }}>
              <label htmlFor="host">Host</label>
              <input 
                id="host" 
                name="host" 
                value={formData.host} 
                onChange={handleChange} 
                placeholder="localhost or DB URL"
                disabled={isTesting || isSaving}
              />
              {errors.host && <div className="form-error">{errors.host}</div>}
            </div>
            <div>
              <label htmlFor="port">Port</label>
              <input 
                id="port" 
                name="port" 
                type="number"
                value={formData.port} 
                onChange={handleChange} 
                disabled={isTesting || isSaving}
              />
              {errors.port && <div className="form-error">{errors.port}</div>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 form-group">
            <div>
              <label htmlFor="username">Username</label>
              <input 
                id="username" 
                name="username" 
                value={formData.username} 
                onChange={handleChange}
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
                disabled={isTesting || isSaving}
              />
              {errors.password && <div className="form-error">{errors.password}</div>}
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose} disabled={isTesting || isSaving}>
            Cancel
          </button>
          <button className="btn-secondary" onClick={handleTestConnection} disabled={isTesting || isSaving}>
            {isTesting ? <><Loader2 size={16} className="animate-spin" /> Testing...</> : 'Test Connection'}
          </button>
          <button onClick={handleSave} disabled={isTesting || isSaving}>
            {isSaving ? <><Loader2 size={16} className="animate-spin" /> Saving...</> : 'Save Connection'}
          </button>
        </div>
      </div>
    </div>
  );
};
