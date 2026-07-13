import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fetchApi } from '../../services/api';
import { Search, Database, Table2, LayoutList, Key, AlignLeft, Hash } from 'lucide-react';

export const SchemaExplorer = () => {
  const [searchParams] = useSearchParams();
  const sourceId = searchParams.get('source');
  const [tables, setTables] = useState<any[]>([]);
  const [selectedTable, setSelectedTable] = useState<any>(null);
  const [columns, setColumns] = useState<any[]>([]);

  useEffect(() => {
    if (sourceId) {
      fetchApi(`/metadata/sources/${sourceId}/tables`)
        .then(data => setTables(data))
        .catch(console.error);
    }
  }, [sourceId]);

  useEffect(() => {
    if (selectedTable) {
      fetchApi(`/metadata/tables/${selectedTable.id}/columns`)
        .then(data => setColumns(data))
        .catch(console.error);
    }
  }, [selectedTable]);

  if (!sourceId) {
    return (
      <div>
        <h2 className="title" style={{ margin: 0 }}>
          <Search size={24} style={{ color: 'var(--primary)' }} /> Schema Explorer
        </h2>
        <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: '2rem' }}>
          Inspect table structures, column profiles, and metadata.
        </p>
        <div className="card text-center" style={{ padding: '4rem 2rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
            <Database size={48} style={{ opacity: 0.2 }} />
            <div>
              <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem' }}>Select a Data Source</div>
              <div className="text-muted">Please select a data source from the Data Sources tab to explore its schema.</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Group tables by schema
  const schemas = tables.reduce((acc, t) => {
    if (!acc[t.schema_name]) acc[t.schema_name] = [];
    acc[t.schema_name].push(t);
    return acc;
  }, {} as Record<string, any[]>);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="mb-4">
        <h2 className="title" style={{ margin: 0 }}>
          <Search size={24} style={{ color: 'var(--primary)' }} /> Schema Explorer
        </h2>
        <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
          Inspect table structures, column profiles, and metadata.
        </p>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', flex: 1, minHeight: 0 }}>
        {/* Left Tree Pane */}
        <div className="card" style={{ width: '300px', display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)', background: 'var(--bg-dark)' }}>
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input type="text" placeholder="Filter tables..." style={{ paddingLeft: '2rem', fontSize: '0.8rem', padding: '0.5rem 0.5rem 0.5rem 2rem' }} />
            </div>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
            {Object.keys(schemas).map(schemaName => (
              <div key={schemaName} style={{ marginBottom: '1rem' }}>
                <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, padding: '0.25rem 0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Database size={12} /> {schemaName}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '0.25rem' }}>
                  {schemas[schemaName].map((t: any) => (
                    <div 
                      key={t.id} 
                      style={{ 
                        padding: '0.5rem 0.75rem', 
                        cursor: 'pointer', 
                        backgroundColor: selectedTable?.id === t.id ? 'rgba(79, 70, 229, 0.1)' : 'transparent', 
                        color: selectedTable?.id === t.id ? 'var(--primary)' : 'var(--text-main)',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        fontSize: '0.875rem',
                        fontWeight: selectedTable?.id === t.id ? 500 : 400
                      }} 
                      onClick={() => setSelectedTable(t)}
                    >
                      <Table2 size={14} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.table_name}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Detail Pane */}
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
          {selectedTable ? (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-color)', background: 'var(--bg-dark)' }}>
                <div className="flex items-center gap-3 mb-2">
                  <div style={{ width: 40, height: 40, borderRadius: 8, background: 'rgba(79, 70, 229, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)' }}>
                    <Table2 size={24} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem' }}>{selectedTable.table_name}</h3>
                    <div className="text-sm text-muted" style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem' }}>
                      <span>Schema: <span style={{ color: 'var(--text-main)' }}>{selectedTable.schema_name}</span></span>
                      <span>Rows: <span style={{ color: 'var(--text-main)' }}>{selectedTable.row_count?.toLocaleString() || 'Unknown'}</span></span>
                    </div>
                  </div>
                </div>
                <p className="text-muted text-sm mt-2">{selectedTable.description || 'No description available for this table.'}</p>
              </div>

              <div style={{ flex: 1, overflowY: 'auto' }}>
                <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Column Name</th>
                        <th>Type</th>
                        <th>Role</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {columns.map(c => {
                        const isNumber = c.data_type.includes('int') || c.data_type.includes('numeric') || c.data_type.includes('float');
                        return (
                          <tr key={c.id}>
                            <td>
                              <div className="flex items-center gap-2">
                                {c.is_primary_key ? (
                                  <Key size={14} className="text-warning" />
                                ) : isNumber ? (
                                  <Hash size={14} className="text-muted" />
                                ) : (
                                  <AlignLeft size={14} className="text-muted" />
                                )}
                                <strong style={{ fontWeight: 500 }}>{c.column_name}</strong>
                              </div>
                            </td>
                            <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                              {c.data_type}
                            </td>
                            <td>
                              <span className={`badge ${c.role === 'measure' ? 'badge-primary' : c.role === 'dimension' ? 'badge-success' : 'badge-default'}`}>
                                {c.role}
                              </span>
                            </td>
                            <td className="text-sm text-muted">
                              {c.description || <span style={{ opacity: 0.5 }}>-</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center text-muted" style={{ height: '100%', flexDirection: 'column', gap: '1rem' }}>
              <LayoutList size={48} style={{ opacity: 0.2 }} />
              <div>Select a table from the left pane to view its columns and metadata.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
