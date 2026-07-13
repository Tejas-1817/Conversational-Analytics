import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { Activity, CheckCircle, XCircle, Clock, Zap, Target } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const ReliabilityDashboard = () => {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchApi('/eval/runs')
      .then(data => {
        setRuns(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const latestRun = runs.length > 0 ? runs[0] : null;

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Reliability Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Continuous Evaluation & Benchmarks</p>
        </div>
        <button 
          onClick={() => navigate('/eval/benchmarks')}
          className="bg-primary text-white px-4 py-2 rounded shadow-sm hover:bg-primary/90 flex items-center space-x-2 text-sm font-medium transition-colors"
        >
          <Activity size={16} />
          <span>Manage Benchmarks</span>
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center p-12"><Activity className="animate-spin text-gray-400" /></div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-500">Overall Accuracy</h3>
                <Target size={20} className="text-blue-500" />
              </div>
              <div className="text-3xl font-bold text-gray-900">
                {latestRun?.overall_score ? `${(latestRun.overall_score * 100).toFixed(1)}%` : 'N/A'}
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-500">Pass Rate</h3>
                <CheckCircle size={20} className="text-emerald-500" />
              </div>
              <div className="text-3xl font-bold text-gray-900">
                {latestRun?.pass_rate ? `${(latestRun.pass_rate * 100).toFixed(1)}%` : 'N/A'}
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-500">Avg Latency</h3>
                <Clock size={20} className="text-amber-500" />
              </div>
              <div className="text-3xl font-bold text-gray-900">
                {latestRun?.avg_latency_ms ? `${latestRun.avg_latency_ms} ms` : 'N/A'}
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-500">Error Rate</h3>
                <XCircle size={20} className="text-red-500" />
              </div>
              <div className="text-3xl font-bold text-gray-900">
                {latestRun?.error_rate ? `${(latestRun.error_rate * 100).toFixed(1)}%` : 'N/A'}
              </div>
            </div>
          </div>

          <h2 className="text-lg font-bold text-gray-900 mb-4">Recent Evaluation Runs</h2>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50/50 border-b border-gray-100">
                  <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Date</th>
                  <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Score</th>
                  <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Pass Rate</th>
                  <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Triggered By</th>
                  <th className="px-6 py-4 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {runs.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-4 text-sm text-gray-900 font-medium">
                      {new Date(r.started_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        r.status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                      }`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {r.overall_score ? `${(r.overall_score * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {r.pass_rate ? `${(r.pass_rate * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">{r.triggered_by}</td>
                    <td className="px-6 py-4 text-right">
                      <button 
                        onClick={() => navigate(`/eval/runs/${r.id}`)}
                        className="text-primary hover:text-primary/80 font-medium text-sm"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
                {runs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-gray-500 text-sm">
                      No evaluation runs found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
