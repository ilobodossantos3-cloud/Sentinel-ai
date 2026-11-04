Backend da SentinelAI — FastAPI + SQLAlchemy + PostgreSQL + OpenRouter.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # preencher credenciais
.venv/bin/uvicorn app.main:app --reload
```

Se a base de dados já existia antes da introdução de colunas JSONB:

```bash
.venv/bin/python scripts/migrate_jsonb.py
```

## Estrutura

```
app/
├── api/          routers (incidents, incident_analysis)
├── core/         config (pydantic-settings) e database
├── models/       ORM (Incident, IncidentAnalysis)
├── schemas/      Pydantic (entrada/saída da API)
└── services/     regra de negócio + cliente IA

scripts/
└── migrate_jsonb.py   migração one-shot TEXT -> JSONB

test_ai.py        smoke test manual do OpenRouter (sem servidor)
```

Notas:
- `POST /incidents/` responde logo; a análise IA corre em background
  (FastAPI `BackgroundTasks`).
- O resultado do LLM é validado com Pydantic (`AnalysisResult`
  em `services/ai_analyzer.py`) antes de ser guardado.
- A BD é criada automaticamente no arranque (`create_all`).
