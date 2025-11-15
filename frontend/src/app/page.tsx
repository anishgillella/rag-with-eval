'use client';

import { useState } from 'react';
import axios from 'axios';
import { Send, Loader, AlertCircle, CheckCircle2, ChevronDown, Copy, Check, Sparkles } from 'lucide-react';

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

const SAMPLE_QUESTIONS = [
  {
    category: 'User-Specific',
    questions: [
      "When is Layla planning her trip to London?",
      "What are Amira's favorite restaurants?",
      "Summarize Sophia's messages about travel",
      "What does Vikram Desai own?"
    ]
  },
  {
    category: 'Factual',
    questions: [
      "How many cars does Vikram have?",
      "Which restaurants are mentioned in the messages?",
      "What travel destinations appear most frequently?",
      "Who mentions visiting Paris?"
    ]
  },
  {
    category: 'Comparative',
    questions: [
      "Compare Fatima and Vikram's travel preferences",
      "What do Sophia and Amira have in common?",
      "Which user is most active in the conversations?",
      "Compare different users' interests"
    ]
  },
  {
    category: 'Analytical',
    questions: [
      "What are the most common topics discussed?",
      "How do users describe their preferences?",
      "What patterns exist in user requests?",
      "Summarize the dataset's main themes"
    ]
  }
];

export default function Home() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSources, setShowSources] = useState(false);
  const [showEvaluations, setShowEvaluations] = useState(false);
  const [copied, setCopied] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const handleAsk = async (e: React.FormEvent, q?: string) => {
    e?.preventDefault?.();
    const queryText = q || question;
    if (!queryText.trim()) return;

    setQuestion(queryText);
    setLoading(true);
    setError('');
    setResponse(null);
    setShowSources(false);
    setShowEvaluations(false);

    try {
      const result = await axios.post(`${apiUrl}/ask`, {
        question: queryText,
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
    if (confidence >= 0.6) return 'text-amber-600';
    return 'text-red-600';
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(response?.answer || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Simple header */}
      <div className="border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 py-8">
          <h1 className="text-3xl font-light text-gray-900 tracking-tight">Aurora</h1>
          <p className="text-sm text-gray-500 mt-2">Ask questions about member data</p>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-3xl mx-auto px-4 py-12">
        {/* Query Form */}
        <form onSubmit={(e) => handleAsk(e)} className="mb-12">
          <div className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question..."
              className="flex-1 px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-gray-400 focus:border-gray-400 bg-white text-gray-900 placeholder-gray-400 transition-colors"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="px-6 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {loading ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </form>

        {/* Error Display */}
        {error && (
          <div className="mb-8 p-4 border border-red-200 bg-red-50 rounded-lg flex gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        )}

        {/* Response Display */}
        {response && (
          <div className="space-y-6">
            {/* Answer Card */}
            <div className="border border-gray-200 rounded-lg p-8 bg-gray-50">
              <div className="flex items-start justify-between mb-6">
                <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wider">Answer</h2>
                <div className={`text-sm font-medium ${getConfidenceColor(response.confidence)}`}>
                  {(response.confidence * 100).toFixed(0)}%
                </div>
              </div>
              <p className="text-lg text-gray-900 leading-relaxed mb-6">{response.answer}</p>

              <button
                onClick={copyToClipboard}
                className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-2 transition-colors"
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

              {response.tips && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <p className="text-sm text-gray-600">{response.tips}</p>
                </div>
              )}
            </div>

            {/* Query Metadata */}
            {response.query_metadata && (
              <div className="grid grid-cols-2 gap-4">
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Query Type</p>
                  <p className="text-sm text-gray-900 font-medium capitalize">
                    {response.query_metadata.query_type.replace(/_/g, ' ')}
                  </p>
                </div>
                {response.query_metadata.mentioned_users.length > 0 && (
                  <div className="border border-gray-200 rounded-lg p-4">
                    <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Users</p>
                    <p className="text-sm text-gray-900 font-medium">
                      {response.query_metadata.mentioned_users.join(', ')}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Evaluations */}
            {response.evaluations && (
              <div className="border border-gray-200 rounded-lg">
                <button
                  onClick={() => setShowEvaluations(!showEvaluations)}
                  className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-gray-900">Quality</span>
                    <span className="text-xs text-gray-500">
                      {(response.evaluations.average_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <ChevronDown
                    className={`w-4 h-4 text-gray-400 transition-transform ${
                      showEvaluations ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {showEvaluations && (
                  <div className="border-t border-gray-200 divide-y divide-gray-200">
                    {response.evaluations.evaluations.map((eval_item, idx) => (
                      <div key={idx} className="px-6 py-4">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="text-sm font-medium text-gray-900 capitalize">
                            {eval_item.name.replace(/_/g, ' ')}
                          </h4>
                          <span className="text-sm text-gray-600">
                            {(eval_item.score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed">{eval_item.reasoning}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Sources */}
            {response.sources && response.sources.length > 0 && (
              <div className="border border-gray-200 rounded-lg">
                <button
                  onClick={() => setShowSources(!showSources)}
                  className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                  <span className="text-sm font-semibold text-gray-900">
                    Sources ({response.sources.length})
                  </span>
                  <ChevronDown
                    className={`w-4 h-4 text-gray-400 transition-transform ${
                      showSources ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {showSources && (
                  <div className="border-t border-gray-200 divide-y divide-gray-200">
                    {response.sources.map((source, idx) => (
                      <div key={idx} className="px-6 py-4 hover:bg-gray-50 transition-colors">
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="text-sm font-medium text-gray-900">{source.user_name}</h4>
                          <div className="text-xs text-gray-600">
                            {(source.reranker_score ? source.reranker_score * 100 : source.similarity_score * 100).toFixed(0)}%
                          </div>
                        </div>
                        <p className="text-sm text-gray-700 leading-relaxed">{source.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Sample Questions */}
        {!response && !loading && (
          <div className="space-y-8">
            <div className="flex items-center gap-2 mb-6">
              <Sparkles className="w-5 h-5 text-gray-600" />
              <p className="text-sm font-medium text-gray-600">Sample Questions to Try</p>
            </div>

            {SAMPLE_QUESTIONS.map((category, catIdx) => (
              <div key={catIdx}>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  {category.category}
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {category.questions.map((q, qIdx) => (
                    <button
                      key={qIdx}
                      onClick={(e) => handleAsk(e, q)}
                      className="text-left p-4 border border-gray-200 rounded-lg hover:border-gray-400 hover:bg-gray-50 transition-all text-sm text-gray-700 hover:text-gray-900"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ))}

            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mt-8">
              <p className="text-xs text-gray-600">
                <span className="font-semibold">Tip:</span> Click any sample question above to test, or type your own question in the input field.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-gray-200 mt-12">
        <div className="max-w-3xl mx-auto px-4 py-8 text-center">
          <p className="text-xs text-gray-500">Powered by RAG with semantic search</p>
        </div>
      </div>
    </div>
  );
}
