# Aurora - AI Question Answering System

A production-ready question-answering system using Retrieval-Augmented Generation (RAG) with a modern full-stack architecture. Built with FastAPI backend and Next.js frontend.

**Live Demo:** [https://aurora-qa.vercel.app](https://aurora-qa.vercel.app)

## Quick Start

### Prerequisites
- Python 3.11+ (for backend)
- Node.js 18+ (for frontend)
- API Keys: Pinecone, OpenRouter, Hugging Face

### Option 1: Local Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py  # Server on http://localhost:8000
```

**Frontend (new terminal):**
```bash
cd frontend
npm install
npm run dev  # Visit http://localhost:3000
```

### Option 2: Deploy to Cloud

See [DEPLOYMENT.md](./DEPLOYMENT.md) for step-by-step Railway + Vercel deployment.

## Project Structure

```
Aurora/
├── backend/              # FastAPI backend (Python)
│   ├── app/             # Core modules
│   ├── main.py          # Entry point
│   ├── requirements.txt  # Dependencies
│   ├── Dockerfile       # Docker config
│   └── BACKEND_README.md # Detailed backend docs
│
├── frontend/            # Next.js frontend (React)
│   ├── src/app/         # Pages & components
│   ├── package.json     # Dependencies
│   └── .env.example     # Config template
│
├── DEPLOYMENT.md        # Deployment guide
└── README.md           # This file
```

## Architecture

### Backend (FastAPI + RAG)

```
Question
  ↓
[Type Detection] → Identify query type
  ↓
[Embedding] → BGE embeddings (1024-dim)
  ↓
[Semantic Search] → Pinecone (top-100)
  ↓
[Reranking] → Cross-encoder (top-30)
  ↓
[LLM] → GPT-4o mini generates answer
  ↓
[Response] → Answer + confidence + sources
```

**Key Features:**
- Two-stage retrieval (semantic + reranking)
- Confidence scoring (0-1)
- Query type detection
- Source attribution
- Comprehensive logging

See [backend/BACKEND_README.md](./backend/BACKEND_README.md) for full details.

### Frontend (Next.js)

**Features:**
- Beautiful, modern UI
- Real-time query interface
- Source visualization
- Query type detection display
- Confidence indicators
- Responsive design

**Tech Stack:**
- Next.js 14
- TypeScript
- Tailwind CSS
- Lucide icons
- Axios

## API Usage

### Ask a Question

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "When is Layla planning her trip to London?",
    "include_sources": true
  }'
```

### Response Format

```json
{
  "answer": "Based on the messages, Layla is planning her trip to London for next month...",
  "confidence": 0.85,
  "query_metadata": {
    "query_type": "user_specific",
    "mentioned_users": ["Layla Kawaguchi"]
  },
  "tips": "Good confidence: 15 relevant sources found.",
  "sources": [
    {
      "user_name": "Layla Kawaguchi",
      "message": "Book me flights to London for next month",
      "similarity_score": 0.92,
      "reranker_score": 0.88
    }
  ]
}
```

## Example Queries

```bash
# User-specific
"What did Sophia say about travel?"
"Summarize Amira's messages"

# Factual
"How many cars does Vikram have?"
"What restaurants are mentioned?"

# Comparative
"Compare Fatima and Vikram's travel styles"
"What do Sophia and Amira have in common?"
```

## Data Analysis

### Dataset Quality: 92%

**Total Messages:** 3,400 (3,300 unique)

**Anomalies Found:**
1. Duplicate Message IDs (100, 3%) - API pagination overlap
2. Temporal Anomalies (100, 5%) - Batch processing timestamps

**Analysis Tool:**
```bash
cd backend
python anomaly_detection.py  # Generates anomalies_report.json
```

See [backend/BACKEND_README.md](./backend/BACKEND_README.md#dataset-quality) for full analysis.

## Deployment

### Railway (Backend)
```bash
1. Connect GitHub repo to Railway
2. Set Python environment variables
3. Deploy (auto-detects Dockerfile)
4. Get API URL
```

### Vercel (Frontend)
```bash
1. Connect GitHub repo to Vercel
2. Set root directory to `frontend`
3. Set NEXT_PUBLIC_API_URL env var
4. Deploy
```

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions.

## Performance

- **Backend startup:** ~3-4 seconds
- **Query latency:** ~2-3 seconds
  - Embedding: ~200ms
  - Retrieval: ~100ms
  - Reranking: ~500ms
  - LLM: ~1000ms
- **Indexing:** ~2-3 minutes for 3,349 messages

## Design Decisions

### Why RAG with Two-Stage Retrieval?

**Alternatives Considered:**
1. **Keyword Search** ❌
   - Fast but brittle
   - Fails on paraphrased questions

2. **Full LLM Context** ❌
   - Would send all 3,349 messages
   - Expensive (~$1 per query)

3. **Simple Semantic Search** ❌
   - Better but imperfect ranking
   - May miss relevant context

4. **RAG with Two-Stage Retrieval** ✅
   - Semantic search + cross-encoder
   - Grounded answers
   - Observable context
   - Scalable to 300K+ messages

### Tech Stack Rationale

- **FastAPI:** Production-ready, async, auto-docs, excellent performance
- **Pinecone:** Managed vector DB, low maintenance, scales automatically
- **GPT-4o mini:** Balanced cost/quality for generation
- **Next.js:** Modern frontend, deployed instantly on Vercel
- **Tailwind CSS:** Beautiful UI without custom CSS

## Troubleshooting

### Backend Issues

**"ModuleNotFoundError"**
```bash
cd backend
pip install -r requirements.txt
```

**"No API Key"**
- Check .env file has all required keys
- Use .env.example as template

### Frontend Issues

**"Can't connect to backend"**
- Check backend is running: `curl http://localhost:8000/health`
- Set NEXT_PUBLIC_API_URL correctly
- Check CORS in backend (enabled by default)

### Deployment Issues

See [DEPLOYMENT.md](./DEPLOYMENT.md#troubleshooting) for common issues.

## Development

### Adding Features

**New Query Type?**
- Edit `app/query_analyzer.py`
- Add detection logic
- Update confidence calculation

**New Reranker?**
- Edit `app/reranker.py`
- Update model configuration

**New Frontend Page?**
- Add file to `frontend/src/app/`
- Use existing components

### Testing

```bash
cd backend
python test_queries.py  # Run test suite
python extract_messages.py  # Export data
python anomaly_detection.py  # Analyze data
```

## Monitoring

**Backend Logs:**
```bash
# Local
tail -f logs/app_*.log

# Railway
Visit project → Logs tab
```

**Frontend Logs:**
- Vercel dashboard → Deployments → View Functions

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ask` | POST | Ask a question |
| `/health` | GET | Health check |
| `/status` | GET | Indexing status |
| `/reindex` | POST | Manual reindex |
| `/docs` | GET | API documentation |

## Future Improvements

- [ ] Multi-turn conversations
- [ ] Result caching with TTL
- [ ] Incremental indexing
- [ ] Query expansion
- [ ] Analytics dashboard
- [ ] A/B testing framework

## License

MIT

## Support

**Issues?**

1. Check logs: `logs/app_*.log`
2. Read backend docs: `backend/BACKEND_README.md`
3. Check deployment: `DEPLOYMENT.md`
4. Review API: `http://localhost:8000/docs`

**Want to contribute?**
- Fork the repo
- Create a feature branch
- Submit a PR

## Questions?

Ask the AI directly! Visit the live demo or run locally and test.

