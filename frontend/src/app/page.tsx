'use client';

import { useState } from 'react';
import axios from 'axios';
import { Send, Loader, AlertCircle, CheckCircle2, Sparkles, Copy, Check } from 'lucide-react';

interface Source {
  user_name: string;
  message: string;
  similarity_score: number;
  reranker_score?: number;
}

interface Response {
  answer: string;
  confidence: number;
  tips?: string;
  sources?: Source[];
  query_metadata?: {
    query_type: string;
    mentioned_users: string[];
  };
  evaluations?: {
    evaluations: Array<{
      name: string;
      score: number;
      reasoning: string;
      passed: boolean;
    }>;
    average_score: number;
    all_passed: boolean;
  };
}

export default function Home() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSources, setShowSources] = useState(false);
  const [showEvaluations, setShowEvaluations] = useState(false);
  const [copied, setCopied] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError('');
    setResponse(null);
    setShowSources(false);
    setShowEvaluations(false);

    try {
      const result = await axios.post(`${apiUrl}/ask`, {
        question,
        include_sources: true,
      });
      setResponse(result.data);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
        'Failed to get answer. Make sure the backend is running.'
      );
    } finally {
      setLoading(false);
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'from-green-500 to-green-600';
    if (confidence >= 0.6) return 'from-yellow-500 to-yellow-600';
    return 'from-red-500 to-red-600';
  };

  const getConfidenceBgColor = (confidence: number) => {
    if (confidence >= 0.8) return 'bg-green-50 border-green-200';
    if (confidence >= 0.6) return 'bg-yellow-50 border-yellow-200';
    return 'bg-red-50 border-red-200';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return { label: 'HIGH', color: 'text-green-700' };
    if (confidence >= 0.6) return { label: 'MODERATE', color: 'text-yellow-700' };
    return { label: 'LOW', color: 'text-red-700' };
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(response?.answer || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const exampleQueries = [
    "When is Layla planning her trip to London?",
    "How many cars does Vikram Desai have?",
    "What are Amira's favorite restaurants?",
    "Summarize Sophia's messages",
    "Compare Fatima and Vikram's travel styles",
    "What do people like about travel?",
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
      {/* Animated background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-0 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob" />
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000" />
        <div className="absolute bottom-0 left-1/2 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="p-3 bg-gradient-to-br from-blue-400 to-purple-500 rounded-xl">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-5xl font-bold bg-gradient-to-r from-blue-300 via-purple-300 to-pink-300 bg-clip-text text-transparent">
              Aurora
            </h1>
          </div>
          <p className="text-gray-300 text-lg mb-2">AI-Powered Question Answering</p>
          <p className="text-gray-400 text-sm">Ask questions about member data with RAG technology</p>
        </div>

        {/* Query Form */}
        <form onSubmit={handleAsk} className="mb-8">
          <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 rounded-2xl blur opacity-75 group-hover:opacity-100 transition duration-1000 group-hover:duration-200" />
            <div className="relative bg-slate-800 rounded-2xl p-2 flex gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question... (e.g., 'When is Layla planning her trip to London?')"
                className="flex-1 px-6 py-3 bg-slate-700 text-white placeholder-gray-400 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-400 focus:bg-slate-600 transition"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white px-8 py-3 rounded-xl font-semibold hover:shadow-lg hover:shadow-purple-500/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-all duration-200"
              >
                {loading ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" />
                    Thinking...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Ask
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/50 rounded-xl flex gap-3 backdrop-blur">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-300">Error</h3>
              <p className="text-red-200 text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* Response Display */}
        {response && (
          <div className="space-y-6">
            {/* Answer Card */}
            <div className="relative group">
              <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-400 to-purple-400 rounded-2xl blur opacity-50 group-hover:opacity-75 transition" />
              <div className="relative bg-slate-800 rounded-2xl p-8">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-6 h-6 text-green-400 flex-shrink-0" />
                    <h2 className="text-2xl font-bold text-white">Answer</h2>
                  </div>
                  <div className={`flex items-center gap-2 px-4 py-2 rounded-lg border ${getConfidenceBgColor(response.confidence)}`}>
                    <div className={`w-2 h-2 rounded-full bg-gradient-to-r ${getConfidenceColor(response.confidence)}`} />
                    <span className={`text-sm font-bold ${getConfidenceLabel(response.confidence).color}`}>
                      {getConfidenceLabel(response.confidence).label}
                    </span>
                    <span className="text-sm font-semibold text-gray-600">
                      {(response.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <p className="text-gray-100 leading-relaxed text-lg mb-6">{response.answer}</p>

                <div className="flex gap-2">
                  <button
                    onClick={copyToClipboard}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-gray-300 rounded-lg transition"
                  >
                    {copied ? (
                      <>
                        <Check className="w-4 h-4" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4" />
                        Copy
                      </>
                    )}
                  </button>
                </div>

                {response.tips && (
                  <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/50 rounded-lg">
                    <p className="text-sm text-blue-200">{response.tips}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Query Metadata */}
            {response.query_metadata && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-xl p-4">
                  <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">Query Type</p>
                  <p className="text-lg font-semibold text-blue-300 capitalize">
                    {response.query_metadata.query_type.replace(/_/g, ' ')}
                  </p>
                </div>
                {response.query_metadata.mentioned_users.length > 0 && (
                  <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-xl p-4">
                    <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">Mentioned Users</p>
                    <p className="text-lg font-semibold text-purple-300">
                      {response.query_metadata.mentioned_users.join(', ')}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Evaluations */}
            {response.evaluations && (
              <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-xl p-6">
                <button
                  onClick={() => setShowEvaluations(!showEvaluations)}
                  className="w-full flex items-center justify-between text-white hover:text-gray-300 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">Quality Metrics</span>
                    <span className="text-sm text-gray-400">
                      {(response.evaluations.average_score * 100).toFixed(0)}% Average
                    </span>
                  </div>
                  <span className={`transform transition ${showEvaluations ? 'rotate-180' : ''}`}>▼</span>
                </button>

                {showEvaluations && (
                  <div className="mt-4 space-y-3">
                    {response.evaluations.evaluations.map((eval_item, idx) => (
                      <div key={idx} className="bg-slate-700/50 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium text-white capitalize">{eval_item.name.replace(/_/g, ' ')}</h4>
                          <div className="flex items-center gap-2">
                            {eval_item.passed && <CheckCircle2 className="w-4 h-4 text-green-400" />}
                            <span className="text-sm font-semibold text-blue-300">
                              {(eval_item.score * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                        <p className="text-sm text-gray-400">{eval_item.reasoning}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Sources */}
            {response.sources && response.sources.length > 0 && (
              <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-xl p-6">
                <button
                  onClick={() => setShowSources(!showSources)}
                  className="w-full flex items-center justify-between text-white hover:text-gray-300 transition"
                >
                  <span className="font-semibold">Sources ({response.sources.length})</span>
                  <span className={`transform transition ${showSources ? 'rotate-180' : ''}`}>▼</span>
                </button>

                {showSources && (
                  <div className="mt-4 space-y-3">
                    {response.sources.map((source, idx) => (
                      <div
                        key={idx}
                        className="bg-gradient-to-r from-slate-700/50 to-slate-600/50 border border-slate-600 rounded-lg p-4 hover:border-blue-500/50 transition"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold text-blue-300">{source.user_name}</h4>
                          <div className="flex gap-4 text-xs">
                            <div className="text-right">
                              <p className="text-gray-400">Relevance</p>
                              <p className="text-green-300 font-semibold">
                                {(source.reranker_score ? source.reranker_score * 100 : source.similarity_score * 100).toFixed(0)}%
                              </p>
                            </div>
                          </div>
                        </div>
                        <p className="text-gray-200 text-sm leading-relaxed">{source.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Example Questions */}
        {!response && !loading && (
          <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-2xl p-8">
            <h3 className="font-semibold text-gray-300 mb-6 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-400" />
              Try These Questions
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {exampleQueries.map((example, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuestion(example)}
                  className="text-left p-4 bg-gradient-to-br from-slate-700/50 to-slate-600/50 hover:from-slate-600/80 hover:to-slate-500/80 rounded-lg border border-slate-600 hover:border-blue-400/50 text-gray-200 hover:text-white text-sm transition-all duration-200 hover:shadow-lg hover:shadow-blue-500/20"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-12 text-center text-gray-400 text-sm">
          <p>Powered by RAG with semantic search and cross-encoder reranking</p>
        </div>
      </div>

      <style jsx>{`
        @keyframes blob {
          0%, 100% {
            transform: translate(0, 0) scale(1);
          }
          33% {
            transform: translate(30px, -50px) scale(1.1);
          }
          66% {
            transform: translate(-20px, 20px) scale(0.9);
          }
        }
        .animate-blob {
          animation: blob 7s infinite;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
    </div>
  );
}
