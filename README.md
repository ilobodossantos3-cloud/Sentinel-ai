# SentinelAI

Plataforma de deteção e análise de incidentes de cibersegurança assistida por IA.

Os alertas do **Suricata IDS** são ingeridos, guardados num **PostgreSQL** e analisados por um **LLM** (via OpenRouter), que produz classificação de ameaça, risk score, indicadores de compromisso e ações recomendadas. O painel web mostra tudo em tempo consultável.

## Arquitectura

```
┌──────────────┐   EVE JSON   ┌───────────────────┐   REST    ┌─────────────┐
│   Suricata   ├─────────────►│ detection/ingest  ├──────────►│  API FastAPI│
│   (ids)      │              └───────────────────┘           │  backend/   │
└──────────────┘                                              │    │        │
                                                              │    ▼        │
┌──────────────┐                                              │  OpenRouter │
│  Frontend    │◄──────────── REST ───────────────────────────│  (LLM)      │
│  React/Vite  │                                              └─────┬───────┘
└──────────────┘                                                    ▼
                                                               PostgreSQL
```

| Pasta | Descrição |
|---|---|
| `backend/` | API FastAPI (incidentes + análise IA), SQLAlchemy, PostgreSQL |
| `frontend/` | Painel React 19 + Vite |
| `detection/` | Ingestor de logs EVE do Suricata (stdlib, sem dependências) |

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # preencher credenciais
.venv/bin/uvicorn app.main:app --reload
```

Utilizadores Windows: `python -m venv .venv` + `Scripts\activate` (a venv é
específica do OS — não partilhes a pasta entre Windows e WSL).

Migre as colunas de análise para JSONB (apenas se a BD já existia antes desta
versão):

```bash
.venv/bin/python scripts/migrate_jsonb.py
```

API em `http://127.0.0.1:8000` · docs interativas: `/docs` · health: `/health`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Painel em `http://localhost:5173`.

### 3. Deteção (Suricata)

```bash
# seguir o log em tempo real
python3 detection/ingest.py /var/log/suricata/eve.json

# testar com o ficheiro de exemplo (processa e sai)
python3 detection/ingest.py detection/suricata/eve.sample.json --once
```

Regras de exemplo: `detection/rules/sentinel.rules`.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | state da API |
| GET | `/health` | health (inclui verificação à BD) |
| GET | `/incidents/` | listar (`?severity=&skip=&limit=`) |
| POST | `/incidents/` | criar incidente (análise IA em background) |
| POST | `/incidents/simulate` | incidente simulado (SSH brute force) |
| GET | `/incidents/{id}` | detalhe |
| GET | `/incidents/{id}/analysis` | análise IA |
| POST | `/incidents/{id}/analysis` | re-gerar análise IA |

## Configuração

Variáveis em `backend/.env` (ver `.env.example`):

- `DATABASE_URL` — ligação PostgreSQL
  (em dev sem Postgres, `sqlite:///./sentinelai.db` também funciona)
- `OPENROUTER_API_KEY` — chave da API (openrouter.ai/keys)
- `OPENROUTER_MODEL` — modelo de análise (default: `z-ai/glm-5.3-flash`)
