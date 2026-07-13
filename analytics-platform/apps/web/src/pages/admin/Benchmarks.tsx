import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { Target, Play, Plus, BookOpen } from 'lucide-react';

export const Benchmarks = () => {
  const [collections, setCollections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi('/eval/collections')
      .then(data => {
        setCollections(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const triggerRun = async (id: string) => {
    try {
      await fetchApi(`/eval/runs/${id}`, { method: 'POST' });
      alert('Benchmark Run started successfully! Check the dashboard for results.');
    } catch (e: any) {
      alert(`Failed to trigger run: ${e.message}`);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Benchmark Collections</h1>
          <p className="text-sm text-gray-500 mt-1">Manage and run evaluation datasets</p>
        </div>
        <button className="bg-primary text-white px-4 py-2 rounded shadow-sm hover:bg-primary/90 flex items-center space-x-2 text-sm font-medium transition-colors">
          <Plus size={16} />
          <span>New Collection</span>
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {collections.map((col, i) => (
            <div key={i} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
                  <BookOpen size={24} />
                </div>
                <span className="text-xs font-medium bg-gray-100 text-gray-600 px-2 py-1 rounded">
                  {col.domain || 'General'}
                </span>
              </div>
              
              <h3 className="text-lg font-bold text-gray-900 mb-1">{col.name}</h3>
              <p className="text-sm text-gray-500 mb-6 line-clamp-2 h-10">
                {col.description || 'No description provided.'}
              </p>
              
              <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
                <span className="text-xs text-gray-500">Created by {col.created_by}</span>
                <button 
                  onClick={() => triggerRun(col.id)}
                  className="flex items-center space-x-1 text-sm font-medium text-emerald-600 hover:text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-3 py-1.5 rounded transition-colors"
                >
                  <Play size={14} />
                  <span>Run Suite</span>
                </button>
              </div>
            </div>
          ))}
          {collections.length === 0 && (
            <div className="col-span-full py-12 text-center text-gray-500 bg-white rounded-xl border border-gray-100 border-dashed">
              No benchmark collections found. Create one to get started.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
