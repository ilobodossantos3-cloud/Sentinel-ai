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
├── models/       ORM (Incident, IncidentAnalysis, Asset, Job)
├── schemas/      Pydantic (entrada/saída da API)
└── services/     regra de negócio + cliente IA

migrations/       Alembic (schema versionado)
scripts/
└── migrate_jsonb.py   migração one-shot TEXT -> JSONB (BDs antigas)

tests/            pytest (BD SQLite temporária)
test_ai.py        smoke test manual do OpenRouter (sem servidor)
```

Notas:
- `POST /incidents/` responde logo; a análise IA corre em background
  e fica rastreada como `Job` (pending → running → completed/failed).
- O resultado do LLM é validado com Pydantic (`AnalysisResult`
  em `services/ai_analyzer.py`) antes de ser guardado.
- Em dev, `create_all` cria as tabelas no arranque; em produção usar
  `alembic upgrade head`. Base de dados já existente: `alembic stamp head`.
- Inventário de ativos (`assets`) é alimentado apenas por IPs
  observados em incidentes reais + registo manual.

## Testes

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -v
```
