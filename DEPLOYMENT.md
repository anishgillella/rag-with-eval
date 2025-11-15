# Aurora Deployment Guide

## Project Structure

```
Aurora/
├── backend/              # FastAPI backend
│   ├── app/             # Application modules
│   ├── main.py          # FastAPI entry point
│   ├── requirements.txt  # Python dependencies
│   ├── Dockerfile       # Docker configuration
│   ├── Procfile         # Railway deployment
│   ├── railway.toml     # Railway configuration
│   └── .env.example     # Environment template
│
├── frontend/            # Next.js frontend
│   ├── src/
│   │   ├── app/         # App pages
│   │   └── components/  # React components
│   ├── package.json
│   ├── next.config.js
│   └── tsconfig.json
│
└── README.md           # Main documentation
```

## Backend Deployment (Railway)

### Step 1: Fix the Railway Deployment

Railway needs proper configuration for Python apps.

**Files Added:**
- `backend/Dockerfile` - Docker container setup
- `backend/Procfile` - Process configuration
- `backend/railway.toml` - Railway configuration

### Step 2: Deploy to Railway

```bash
1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub"
4. Select: anishgillella/rag-with-eval
5. Select branch: rag
6. Railway will auto-detect it's a Python app and use Dockerfile
7. Add Environment Variables:
   - PINECONE_API_KEY=your_key
   - PINECONE_INDEX_NAME=aurora
   - PINECONE_ENVIRONMENT=us-west-1
   - OPENROUTER_API_KEY=your_key
   - OPENROUTER_MODEL=openai/gpt-4o-mini
   - HUGGINGFACE_API_KEY=your_key
   - HF_EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
   - EXTERNAL_API_URL=https://november7-730026606190.europe-west1.run.app
   - LOG_LEVEL=INFO
   - ENVIRONMENT=production
8. Click Deploy
9. Wait for deployment (2-3 minutes)
10. Get your API URL (e.g., https://aurora-api.up.railway.app)
```

### Test Backend API

```bash
curl -X POST "https://aurora-api.up.railway.app/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "When is Layla planning her trip to London?"}'
```

## Frontend Deployment (Vercel)

### Step 1: Install Dependencies Locally

```bash
cd frontend
npm install
```

### Step 2: Create .env.local

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=https://aurora-api.up.railway.app
```

### Step 3: Deploy to Vercel

```bash
1. Go to https://vercel.com
2. Click "Add New..." → "Project"
3. Select: anishgillella/rag-with-eval
4. Set "Root Directory" to: frontend
5. Add Environment Variable:
   - NEXT_PUBLIC_API_URL=https://aurora-api.up.railway.app
6. Click Deploy
7. Wait for deployment (1-2 minutes)
8. Get your frontend URL (e.g., https://aurora-qa.vercel.app)
```

### Test Frontend

```bash
Visit: https://aurora-qa.vercel.app
Try the example queries
```

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
python main.py
# Server runs on http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Visit http://localhost:3000
```

## Troubleshooting

### Railway Backend Issues

If you see "ModuleNotFoundError: No module named 'fastapi'":

1. Make sure you're in the `backend` directory when deploying
2. Railway should use the `Dockerfile` to build
3. Check Railway logs for build errors
4. Verify all environment variables are set

### Frontend Can't Connect to Backend

If you see errors about connecting to the API:

1. Check `NEXT_PUBLIC_API_URL` is set correctly in Vercel
2. Make sure backend is deployed and running
3. Check CORS is enabled (it is in main.py)
4. Try the API directly: `curl https://aurora-api.up.railway.app/health`

## Monitoring

### View Logs

**Railway:**
- Go to your project → Logs tab
- Real-time logs of backend

**Vercel:**
- Go to your project → Deployments → View Functions
- Runtime logs

## Scale Up

To handle more traffic:

- **Backend**: Railway auto-scales (upgrade plan for guaranteed resources)
- **Frontend**: Vercel handles all scale automatically

## Cost

- **Backend (Railway)**: ~$5/month free tier, then usage-based
- **Frontend (Vercel)**: Free tier sufficient for most usage
- **APIs**: Based on usage (Pinecone, OpenRouter, HuggingFace)

## Support

For issues:
1. Check Railway/Vercel logs
2. Verify all environment variables
3. Test API locally first
4. Check API limits on Pinecone/OpenRouter/HuggingFace

