import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchApi } from '../../services/api';
import { ArrowLeft, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';

export const EvaluationRunDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi(`/eval/runs/${id}`)
      .then(data => {
        setRun(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="flex justify-center p-12">Loading...</div>;
  if (!run) return <div className="flex justify-center p-12">Run not found</div>;

  return (
    <div>
      <div className="flex items-center space-x-4 mb-8">
        <button 
          onClick={() => navigate('/eval/dashboard')}
          className="p-2 hover:bg-gray-100 rounded-full transition-colors"
        >
          <ArrowLeft size={20} className="text-gray-500" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Run Details</h1>
          <p className="text-sm text-gray-500 mt-1">
            {new Date(run.started_at).toLocaleString()} • Triggered by {run.triggered_by}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden mb-8">
        <div className="grid grid-cols-4 divide-x divide-gray-100 border-b border-gray-100 bg-gray-50/50">
          <div className="p-4 text-center">
            <p className="text-xs font-semibold text-gray-500 uppercase">Score</p>
            <p className="text-2xl font-bold text-gray-900">{run.overall_score ? `${(run.overall_score * 100).toFixed(1)}%` : 'N/A'}</p>
          </div>
          <div className="p-4 text-center">
            <p className="text-xs font-semibold text-gray-500 uppercase">Pass Rate</p>
            <p className="text-2xl font-bold text-gray-900">{run.pass_rate ? `${(run.pass_rate * 100).toFixed(1)}%` : 'N/A'}</p>
          </div>
          <div className="p-4 text-center">
            <p className="text-xs font-semibold text-gray-500 uppercase">Avg Latency</p>
            <p className="text-2xl font-bold text-gray-900">{run.avg_latency_ms ? `${run.avg_latency_ms} ms` : 'N/A'}</p>
          </div>
          <div className="p-4 text-center">
            <p className="text-xs font-semibold text-gray-500 uppercase">Tests Run</p>
            <p className="text-2xl font-bold text-gray-900">{run.results ? run.results.length : 0}</p>
          </div>
        </div>
      </div>

      <h2 className="text-lg font-bold text-gray-900 mb-4">Question Results</h2>
      <div className="space-y-4">
        {run.results?.map((res: any, i: number) => (
          <div key={i} className={`bg-white rounded-xl shadow-sm border p-5 ${res.is_pass ? 'border-emerald-100' : 'border-red-200'}`}>
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center space-x-2">
                {res.is_pass ? <CheckCircle size={18} className="text-emerald-500" /> : <XCircle size={18} className="text-red-500" />}
                <span className="font-medium text-gray-900">Dataset ID: {res.dataset_id}</span>
              </div>
              <span className="text-sm font-bold bg-gray-100 px-2 py-1 rounded">Score: {res.reliability_score ? `${(res.reliability_score * 100).toFixed(0)}%` : '0%'}</span>
            </div>
            
            {!res.is_pass && res.failure_reasons?.length > 0 && (
              <div className="mt-3 p-3 bg-red-50 text-red-800 text-sm rounded flex items-start space-x-2">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <ul className="list-disc pl-4 space-y-1">
                  {res.failure_reasons.map((r: string, j: number) => (
                    <li key={j}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
            
            <div className="mt-4 grid grid-cols-2 md:grid-cols-6 gap-2 text-center text-xs">
              <div className="p-2 bg-gray-50 rounded">
                <p className="text-gray-500 mb-1">Intent</p>
                <p className="font-semibold">{res.intent_score?.toFixed(2) || '0.00'}</p>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <p className="text-gray-500 mb-1">Plan</p>
                <p className="font-semibold">{res.plan_score?.toFixed(2) || '0.00'}</p>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <p className="text-gray-500 mb-1">SQL</p>
                <p className="font-semibold">{res.sql_score?.toFixed(2) || '0.00'}</p>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <p className="text-gray-500 mb-1">Result</p>
                <p className="font-semibold">{res.result_score?.toFixed(2) || '0.00'}</p>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <p className="text-gray-500 mb-1">Chart</p>
                <p className="font-semibold">{res.chart_score?.toFixed(2) || '0.00'}</p>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <p className="text-gray-500 mb-1">NL</p>
                <p className="font-semibold">{res.nl_score?.toFixed(2) || '0.00'}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
