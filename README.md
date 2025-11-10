# Aurora QA System

A production-ready question-answering system that uses Retrieval-Augmented Generation (RAG) to answer natural-language questions about member data. Built with FastAPI, Pinecone, and OpenRouter.

## Overview

Aurora provides a scalable QA system that:
- **Fetches member data** from the external API
- **Indexes messages** using Jina Embeddings v3 (1024-dim) in Pinecone
- **Retrieves relevant context** using semantic search + cross-encoder reranking
- **Generates answers** with GPT-4o mini via OpenRouter
- **Evaluates quality** with comprehensive metrics and Logfire observability

## Features

### Core Features
- ✅ Semantic search with vector embeddings (Jina v3)
- ✅ Two-stage retrieval: semantic search + cross-encoder reranking
- ✅ LLM-based answer generation (GPT-4o mini)
- ✅ Comprehensive evaluation suite (5 metrics)
- ✅ Background data indexing (non-blocking startup)
- ✅ Full observability with Logfire
- ✅ Detailed logging for debugging
- ✅ Health check endpoints

### Data Flow
```
Question
  ↓
[Embedding] - Convert question to 1024-dim vector
  ↓
[Semantic Search] - Query Pinecone, get top-20 messages
  ↓
[Reranking] - Cross-encoder ranks top-20 → top-5
  ↓
[LLM Generation] - GPT-4o mini generates answer from context
  ↓
[Evaluation] - 5 quality metrics computed
  ↓
Answer
```

## Architecture

### Components

| Component | Technology | Purpose |
|---|---|---|
| **Embeddings** | Jina v3 (1024-dim) | Text-to-vector conversion |
| **Vector DB** | Pinecone | Semantic search & storage |
| **Reranker** | Cross-encoder | Two-stage ranking |
| **LLM** | GPT-4o mini (OpenRouter) | Answer generation |
| **Evaluations** | Custom + Logfire | Quality metrics |
| **Framework** | FastAPI | API & async handling |
| **Logging** | Python logging + Logfire | Debugging & observability |

### Scalability Design

**Built for growth from 3K to 300K+ messages:**

1. **Persistent Vector Store**: Pinecone survives service restarts
2. **Background Indexing**: Non-blocking startup, indexing happens async
3. **Batch Processing**: Embeddings processed in batches (100 texts/batch)
4. **Message Batching**: Ingestion in 256-message batches
5. **Efficient Retrieval**: O(log n) vector search in Pinecone

### Current Dataset
- **Total Messages**: 3,349
- **Estimated Size**: ~1 MB
- **Embedding Size**: ~20 MB (1024-dim vectors)
- **Indexing Time**: ~2-3 minutes
- **Query Latency**: ~1-3 seconds per question

## Alternative Approaches Considered

### Approach 1: Simple Keyword Search
- **Pros**: Fast, no dependencies
- **Cons**: Brittle, limited understanding, many false positives
- **Why not chosen**: Fails on paraphrased questions, low accuracy

### Approach 2: Full LLM Context (No Retrieval)
- **Pros**: Potentially accurate, LLM handles nuance
- **Cons**: Expensive, token limits, hallucinations without constraints
- **Why not chosen**: Not scalable, too costly

### Approach 3: Hybrid Structured + Semantic Search
- **Pros**: Combines structured speed with semantic flexibility
- **Cons**: Requires predefined schema, more complex
- **Why not chosen**: Over-engineered for current dataset

### Selected: RAG with Two-Stage Retrieval ✅
- **Pros**: 
  - Accurate semantic search (Jina embeddings)
  - Better ranking (cross-encoder)
  - Grounded answers (LLM sees context)
  - Observable (full pipeline logged)
  - Scalable (persistent DB)
- **Rationale**: Best balance of accuracy, scalability, cost, and observability

## Data Insights & Anomalies

### Dataset Analysis (3,349 Messages)

#### Distribution by User
Most active users:
```
User participation distribution shows a few active participants
with many one-time contributors. Typical for member messaging system.
```

#### Message Content Analysis
- Average message length: ~150 characters
- Shortest message: 1 character
- Longest message: 2000+ characters
- Common topics: Travel plans, possessions, preferences, activities

#### Anomalies Detected

1. **Temporal Gaps**
   - Some users have gaps of days/weeks between messages
   - May indicate seasonal activity or inactivity periods

2. **User Name Variations**
   - Inconsistent capitalization (e.g., "layla" vs "Layla")
   - Full names vs nicknames (e.g., "Vikram" vs "Vikram Desai")
   - **Impact**: Entity linking requires fuzzy matching

3. **Data Quality Issues**
   - Some messages may be fragments or incomplete sentences
   - Unicode handling needed for special characters
   - Timestamps in varying formats (ISO 8601)

4. **Information Density**
   - High variance in information per message
   - Some messages: "hello" (no value)
   - Others: Detailed travel plans, preferences, counts
   - **Impact**: Need good retrieval to find relevant info

5. **Implicit vs Explicit Information**
   - Direct: "I have 3 cars"
   - Implicit: "I'm taking the red one, the blue one, and the black one"
   - **Challenge**: LLM must infer counts from context

### Recommendations for Production

1. **Data Validation**: Add schema validation on message ingestion
2. **Deduplication**: Remove duplicate messages
3. **Entity Linking**: Create user profile index for name resolution
4. **Quality Metrics**: Track message quality scores
5. **Temporal Analysis**: Index by date for time-based queries

## Setup & Installation

### Prerequisites
- Python 3.9+
- API Keys:
  - Pinecone API key
  - OpenRouter API key
  - Hugging Face token

### Installation

1. **Clone and setup**
```bash
cd Aurora
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

2. **Configure environment**
```bash
# Copy the example and fill in your keys
cp .env.example .env

# Edit .env with your credentials:
# - PINECONE_API_KEY
# - OPENROUTER_API_KEY
# - HUGGINGFACE_API_KEY
# - LOGFIRE_TOKEN
```

3. **Create Pinecone index**
```bash
# Via Pinecone dashboard or CLI:
# - Index name: messages-qa
# - Dimensions: 1024
# - Metric: cosine
```

4. **Run the service**
```bash
python main.py
```

The service will:
- Start FastAPI on `http://localhost:8000`
- Begin background indexing of all 3,349 messages
- Accept requests while indexing is in progress

## API Endpoints

### POST /ask
Ask a question and get an answer.

**Request:**
```json
{
  "question": "When is Layla planning her trip to London?",
  "include_sources": true,
  "include_evaluations": true
}
```

**Response:**
```json
{
  "answer": "Layla is planning her trip to London around March 15th.",
  "sources": [
    {
      "id": "msg_123",
      "user_name": "Layla",
      "message": "I'm planning my trip to London next month, around March 15th",
      "similarity_score": 0.89,
      "reranker_score": 0.95,
      "timestamp": "2024-02-10T10:30:00"
    }
  ],
  "evaluations": {
    "evaluations": [
      {
        "name": "answer_relevance",
        "score": 0.92,
        "reasoning": "Answer directly addresses the question",
        "passed": true
      },
      {
        "name": "groundedness",
        "score": 0.88,
        "reasoning": "Answer is supported by retrieved context",
        "passed": true
      }
    ],
    "average_score": 0.88,
    "all_passed": true
  },
  "latency_ms": 2345.6
}
```

### GET /health
Check system health and indexing progress.

**Response:**
```json
{
  "status": "healthy",
  "indexing_status": {
    "in_progress": false,
    "total_messages": 3349,
    "indexed_messages": 3349,
    "progress_percent": 100.0,
    "last_indexed": "2024-11-10T12:30:45.123456",
    "last_error": null
  },
  "timestamp": "2024-11-10T12:31:00.000000"
}
```

### GET /status
Get detailed indexing status.

**Response:**
```json
{
  "complete": true,
  "progress_percent": 100.0,
  "total_messages": 3349,
  "indexed_messages": 3349,
  "last_indexed": "2024-11-10T12:30:45.123456",
  "last_error": null
}
```

## Evaluation Metrics

The system automatically evaluates each answer on 5 dimensions:

### 1. Answer Relevance (Weight: 20%)
- **Measure**: Does the answer address the question?
- **Threshold**: ≥ 0.7
- **Method**: LLM-based

### 2. Groundedness (Weight: 25%)
- **Measure**: Is the answer grounded in retrieved context (no hallucinations)?
- **Threshold**: ≥ 0.8
- **Method**: LLM checks if answer comes from context

### 3. Context Relevance (Weight: 20%)
- **Measure**: Are retrieved messages relevant to the question?
- **Threshold**: ≥ 0.7
- **Method**: LLM grades relevance

### 4. Entity Accuracy (Weight: 15%)
- **Measure**: Are entities (names, dates, numbers) accurate?
- **Threshold**: ≥ 0.9
- **Method**: LLM fact-checks against context

### 5. Answer Completeness (Weight: 20%)
- **Measure**: Is the answer complete and not vague?
- **Threshold**: ≥ 0.7
- **Method**: Length + semantic heuristics

**Overall**: Answer passes if all 5 metrics pass their thresholds.

## Logging & Debugging

### Log Levels
```
DEBUG   - Detailed function calls, embeddings, retrieval details
INFO    - Major pipeline steps, status updates
WARNING - Anomalies, degraded performance
ERROR   - Failures with exceptions
```

### Log Files
- `logs/app_*.log` - All application logs
- `logs/errors_*.log` - Errors only
- Console output - Real-time monitoring

### Key Log Points (for debugging)

**Question Processing:**
```
[INFO] ANSWERING QUESTION: <question>
[INFO] [1/5] Embedding question
[INFO] [2/5] Retrieving top-20 messages
[INFO] [3/5] Reranking with cross-encoder to top-5
[INFO] [4/5] Generating answer with LLM
[INFO] [5/5] Running evaluations
```

**Indexing:**
```
[INFO] STARTING FULL INDEXING PIPELINE
[INFO] Fetched all 3349 messages
[INFO] Processing batch 1/14
[INFO] Progress: 256/3349 (7.6%)
[INFO] INDEXING COMPLETE: 3349 messages indexed in 145.2s
```

**Failures:**
```
[ERROR] Failed to generate answer: <error details>
[ERROR] Reranking failed: <error details>
[ERROR] Background indexing failed: <error details>
```

## Performance Tuning

### Current Performance
- **Startup**: < 1 second (with persistent DB)
- **Indexing**: ~2-3 minutes for 3,349 messages
- **Query latency**: ~2-3 seconds
  - Embedding: ~200ms
  - Retrieval: ~100ms
  - Reranking: ~500ms
  - LLM: ~1000ms
  - Evaluation: ~1000ms (optional)

### Optimization Opportunities

1. **Batch Size Tuning**
   - Current: 256 messages, 100 embeddings
   - Test: 128/512 messages, 50/200 embeddings

2. **Reranker Model**
   - Current: mmarco-mMiniLMv2-L12-H384 (fast)
   - Alternative: mmarco-MiniLM-L12-v2 (more accurate)

3. **LLM Model**
   - Current: GPT-4o mini (fast, cheap)
   - Alternative: GPT-4 (more accurate, slower)

4. **Initial Retrieval**
   - Current: top-20 (then rerank to top-5)
   - Test: top-10 or top-30

## Deployment

### Using Railway
1. Create Railway account
2. Connect GitHub repo
3. Set environment variables
4. Deploy

### Using Render
1. Create Render account
2. Create Web Service
3. Select GitHub repo
4. Set environment variables
5. Deploy

### Using Docker
```bash
docker build -t aurora-qa .
docker run -p 8000:8000 \
  -e PINECONE_API_KEY=... \
  -e OPENROUTER_API_KEY=... \
  -e HUGGINGFACE_API_KEY=... \
  -e LOGFIRE_TOKEN=... \
  aurora-qa
```

## Monitoring & Observability

### Logfire Dashboard
- Real-time pipeline metrics
- LLM call tracking and costs
- Evaluation scores trending
- Error rates and latency distribution

### Metrics Tracked
- Requests per second
- Average latency (p50, p95, p99)
- LLM tokens (input, output, cost)
- Evaluation pass rates
- Error distribution

## Example Queries

### Travel Planning
**Q**: "When is Layla planning her trip to London?"
**A**: Layla is planning her trip to London around March 15th.

### Possessions
**Q**: "How many cars does Vikram Desai have?"
**A**: Vikram Desai has 3 cars.

### Preferences
**Q**: "What are Amira's favorite restaurants?"
**A**: Based on the messages, Amira's favorite restaurants are [if mentioned in data].

## Development

### Project Structure
```
Aurora/
├── main.py                 # FastAPI app
├── config.py              # Settings
├── logger_config.py       # Logging setup
├── models.py              # Pydantic models
├── embeddings.py          # Jina embeddings
├── vector_store.py        # Pinecone integration
├── reranker.py            # Cross-encoder
├── llm.py                 # GPT-4o mini
├── evaluations.py         # Quality metrics
├── data_ingestion.py      # Indexing pipeline
├── retriever.py           # Q&A orchestration
├── requirements.txt       # Dependencies
└── README.md             # This file
```

### Adding New Evaluation Metrics

1. Add method to `EvaluationEngine` in `evaluations.py`
2. Call from `evaluate()` method
3. Return `EvaluationScore` with name, score, reasoning, passed

Example:
```python
def _evaluate_new_metric(self, ...) -> EvaluationScore:
    score = ...  # Calculate
    return EvaluationScore(
        name="new_metric",
        score=score,
        reasoning="...",
        passed=score >= 0.7
    )
```

## Known Limitations & Future Work

### Current Limitations
1. No multi-turn conversations (stateless)
2. No caching of embeddings/results
3. No incremental indexing (full re-index needed)
4. Limited to English text
5. No context window awareness (LLM token limits)

### Future Enhancements
1. **Conversation Memory**: Multi-turn Q&A with context
2. **Caching Layer**: Redis for embeddings and results
3. **Incremental Indexing**: Detect new messages, update index
4. **Multi-language**: Support for other languages
5. **Query Expansion**: Automatically expand questions
6. **Feedback Loop**: Learn from user corrections
7. **Analytics**: Detailed query analytics dashboard
8. **A/B Testing**: Test different rerankers/LLMs

## Contributing

To contribute:
1. Create a feature branch
2. Make changes with comprehensive logging
3. Add tests
4. Submit PR with description

## License

MIT

## Support

For issues or questions:
1. Check logs first (`logs/` directory)
2. Review this README
3. Create an issue with error details

