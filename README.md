# ModelMerge

Smart merge tool for SysML v2 and ReqIF engineering models. Upload two models, resolve conflicts visually, validate with AI, and download the merged result.

## Features

- **SysML v2 Parser** — Custom recursive descent parser for `.sysml` files
- **ReqIF Support** — Parse and merge `.reqif` requirements files
- **Visual Merge** — Side-by-side conflict resolution with color-coded blocks
- **AI Validation** — Claude-powered syntax and semantic checking
- **Diagram View** — D3.js hierarchical block diagrams of merged models
- **Download** — Export merged models as `.sysml` text

## Architecture

- **Frontend**: React + TypeScript + Vite
- **Backend**: Python + FastAPI
- **AI**: Anthropic Claude API (via direct HTTP)

## Live Demo

- Frontend: _deployed on Vercel_
- Backend API: _deployed on Railway_

## Local Development

```bash
# Backend
cd backend
pip3 install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Sample Files

Sample SysML v2 files are in `samples/sysmlv2/` for testing.
