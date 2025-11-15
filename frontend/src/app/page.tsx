'use client';

import { useState } from 'react';
import axios from 'axios';
import { Send, Loader, AlertCircle, CheckCircle } from 'lucide-react';

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
}

export default function Home() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSources, setShowSources] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError('');
    setResponse(null);

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
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return 'HIGH';
    if (confidence >= 0.6) return 'MODERATE';
    return 'LOW';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">Aurora</h1>
          <p className="text-gray-600">Ask questions about member data powered by RAG</p>
        </div>

        {/* Query Form */}
        <form onSubmit={handleAsk} className="mb-8">
          <div className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question... (e.g., 'When is Layla planning her trip to London?')"
              className="flex-1 px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 flex items-center gap-2 transition"
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
        </form>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-800">Error</h3>
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* Response Display */}
        {response && (
          <div className="space-y-6">
            {/* Answer */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="flex items-start justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-800">Answer</h2>
                <div className={`text-sm font-semibold ${getConfidenceColor(response.confidence)}`}>
                  <span className="text-gray-600">Confidence: </span>
                  {getConfidenceLabel(response.confidence)} ({(response.confidence * 100).toFixed(0)}%)
                </div>
              </div>
              <p className="text-gray-700 leading-relaxed">{response.answer}</p>

              {response.tips && (
                <div className="mt-4 p-3 bg-blue-50 rounded border-l-4 border-blue-500">
                  <p className="text-sm text-blue-800">{response.tips}</p>
                </div>
              )}
            </div>

            {/* Query Metadata */}
            {response.query_metadata && (
              <div className="bg-white rounded-lg shadow p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Query Type</p>
                    <p className="font-semibold text-gray-800 capitalize">
                      {response.query_metadata.query_type.replace(/_/g, ' ')}
                    </p>
                  </div>
                  {response.query_metadata.mentioned_users.length > 0 && (
                    <div>
                      <p className="text-sm text-gray-600">Mentioned Users</p>
                      <p className="font-semibold text-gray-800">
                        {response.query_metadata.mentioned_users.join(', ')}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Sources Toggle */}
            {response.sources && response.sources.length > 0 && (
              <div>
                <button
                  onClick={() => setShowSources(!showSources)}
                  className="w-full flex items-center justify-between p-4 bg-white rounded-lg shadow hover:shadow-md transition"
                >
                  <span className="font-semibold text-gray-800">
                    Sources ({response.sources.length})
                  </span>
                  <span className={`transform transition ${showSources ? 'rotate-180' : ''}`}>▼</span>
                </button>

                {showSources && (
                  <div className="mt-2 space-y-3">
                    {response.sources.map((source, idx) => (
                      <div
                        key={idx}
                        className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold text-gray-800">{source.user_name}</h4>
                          <div className="text-xs text-gray-600">
                            Relevance: {(source.reranker_score ? source.reranker_score * 100 : source.similarity_score * 100).toFixed(0)}%
                          </div>
                        </div>
                        <p className="text-gray-700 text-sm">{source.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Example Questions */}
        {!response && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="font-semibold text-gray-800 mb-4">Try these examples:</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                "When is Layla planning her trip to London?",
                "How many cars does Vikram Desai have?",
                "What are Amira's favorite restaurants?",
                "Summarize Sophia's messages",
              ].map((example, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuestion(example)}
                  className="text-left p-3 bg-blue-50 hover:bg-blue-100 rounded border border-blue-200 text-blue-800 text-sm transition"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

