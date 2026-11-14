# SentinelAI

Plataforma SOC de deteção e análise de incidentes de cibersegurança assistida por IA.

Os alertas do **Suricata IDS** são ingeridos, guardados em **PostgreSQL** (ou SQLite em dev)
e analisados por um **LLM** (via OpenRouter), que produz classificação de ameaça, risk score,
indicadores de compromisso e ações recomendadas. O painel web mostra tudo com dados 100% reais.

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
| `backend/` | API FastAPI (incidentes, ativos, auditorias), SQLAlchemy + Alembic |
| `frontend/` | Painel React 19 + Vite (dashboard SOC, threats, assets, audits) |
| `detection/` | Ingestor de logs EVE do Suricata (stdlib, sem dependências) |

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
cp .env.example .env                               # preencher credenciais
.venv/Scripts/uvicorn app.main:app --port 8000
```

Utilizadores Windows: `py -3.13 -m venv .venv` + `call .venv\Scripts\activate.bat`.
A venv é específica do OS — não partilhes a pasta entre Windows e WSL.

Esquema da base de dados:
- **dev**: `create_all` automático no arranque.
- **produção**: `alembic upgrade head` (bases existentes: `alembic stamp head` primeiro).

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

Alertas → incidentes analisados por IA. Registos `flow`/`dns`/`http`/`tls`/`ssh`
→ observações de tráfego (alimentam o inventário de ativos, nunca criam incidentes).

Regras de exemplo: `detection/rules/sentinel.rules`.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | health (inclui verificação à BD) |
| GET | `/incidents/` | listar (`?severity=&skip=&limit=`) |
| POST | `/incidents/` | criar incidente (análise IA em background, rastreada em jobs) |
| GET | `/incidents/{id}` | detalhe |
| PATCH | `/incidents/{id}` | actualizar estado (ciclo de vida de investigação) |
| GET | `/incidents/{id}/analysis` | análise IA |
| POST | `/incidents/{id}/analysis` | re-gerar análise IA |
| GET | `/assets/` | inventário de ativos (estado derivado de dados reais) |
| POST | `/assets/` | registar ativo manualmente |
| GET | `/assets/{ip}` | detalhe do ativo + incidentes recentes |
| POST | `/ingest/observations` | observações de tráfego do ingester (não criam incidentes) |
| GET | `/audits/` | listar auditorias |
| POST | `/audits/` | lançar auditoria não destrutiva (exige `authorized: true`) |
| GET | `/audits/{id}` | detalhe + achados com evidência técnica |
| GET | `/audits/{id}/report` | relatório markdown com evidências |
| GET | `/audits/compare?a=&b=` | comparação de duas auditorias do mesmo alvo |
| PATCH | `/audits/{id}/findings/{fid}` | estado do achado (open/fixed/accepted) |
| GET | `/stats/alerts` | contagens por severidade e estado |
| GET | `/topology` | nós/arestas/eventos para o dashboard |
| GET | `/posture` | score de segurança calculado de dados reais |
| GET | `/activity` | feed de atividade da plataforma |
| GET | `/threat-intel` | inteligência de ameaças agregada |

## Testes

```bash
cd backend
.venv/Scripts/python -m pytest tests/ -q
```

## Configuração

Variáveis em `backend/.env` (ver `.env.example`):

- `DATABASE_URL` — ligação PostgreSQL
  (em dev sem Postgres, `sqlite:///./sentinelai.db` também funciona)
- `OPENROUTER_API_KEY` — chave da API (openrouter.ai/keys)
- `OPENROUTER_MODEL` — modelo de análise (default: `z-ai/glm-5.3-flash`)
