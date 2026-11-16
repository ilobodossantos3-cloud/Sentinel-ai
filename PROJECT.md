# SentinelAI — Documentação do Projeto

> Plataforma SOC de cibersegurança com IA: deteção via Suricata, análise de
> incidentes assistida por LLM, auditoria de segurança de sistemas e
> inventário de vulnerabilidades — **100% com dados reais, nunca fabricados**.

---

## 1. O que é

SentinelAI é um SOC (Security Operations Center) self-hosted que:

1. **Ingestão** — lê o log EVE JSON do Suricata IDS em tempo real
   (alertas criam incidentes; tráfego `flow`/`dns`/`http`/`tls` alimenta o
   inventário de ativos sem criar incidentes).
2. **Análise IA** — cada incidente é analisado por um LLM (OpenRouter,
   modelo configurável) que produz classificação de ameaça, risk score,
   confiança, indicadores de compromisso e ações recomendadas.
3. **Auditoria de segurança** — verificações não destrutivas (apenas HTTP
   GET + inspeção TLS) sobre alvos autorizados: headers de segurança,
   certificados, redirects, cookies, exposição pública.
4. **Vulnerabilidades** — inventário derivado dos achados das auditorias,
   com IDs internos determinísticos (`VULN-XXXXXXXX`), estado de correção
   e histórico por auditoria.
5. **Threat Intelligence** — 4 feeds públicas reais (FireHOL level 1,
   abuse.ch Feodo C2, Tor exit nodes, IPsum), com matching por IP exacto
   e por contenção CIDR, que enriquecem os incidentes.
6. **Dashboard SOC** — painel React com dados 100% reais: postura de
   segurança, topologia, alertas, ativos, auditorias, vulnerabilidades
   e intel — com varredura automática agendada de todos os sistemas.

## 2. Como começou

O projeto começou como um scaffold típico: backend FastAPI com um único
modelo de incidente, análise IA básica e um ingester Suricata em stdlib
Python, mais um frontend React de template.

A partir dessa base foi construído um produto real, fase a fase, com três
regras inegociáveis desde o início:

- **Nunca apresentar dados simulados como reais** (alerta ≠ evento ≠
  incidente confirmado).
- **A IA deve exprimir incerteza** (confiança, não certeza).
- **Validar cada fase antes de avançar** (suíte de testes crescente).

## 3. Arquitectura

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
                          threat feeds (FireHOL,     ┌─────────────────────┐
                          abuse.ch, Tor, IPsum) ────►│  PostgreSQL/SQLite  │
                          (downloads reais)          └─────────────────────┘
```

| Componente | Stack | Papel |
|---|---|---|
| `backend/` | FastAPI, SQLAlchemy 2.0, Alembic, OpenAI SDK (OpenRouter) | API, regra de negócio, jobs em background, scheduler |
| `frontend/` | React 19 + Vite + axios | Dashboard SOC (8 rotas reais) |
| `detection/` | Python stdlib | Ingester EVE → API (batch de observações) |

**Ciclo de vida de jobs:** tudo que corre em background (análise IA,
auditoria, refresh de feeds, varreduras) é rastreado numa tabela `jobs`
com estado `pending → running → completed | partial | failed` — nunca
"desaparece".

## 4. Regras de honestidade (o coração do projeto)

| Regra | Implementação |
|---|---|
| Nunca dados falsos | Endpoint `/incidents/simulate` foi **apagado**; score vazio → `null` + `insufficient_data`, nunca 100 |
| Achados com evidência | Todo `AuditFinding` exige `evidence` técnica (headers observados, datas do certificado) |
| Sem CVEs inventados | Vulnerabilidades usam IDs internos; CVE só com feed real (futuro) |
| IA exprime incerteza | `confidence` explícita nas análises |
| "Não detectado" ≠ "resolvido" | Vulnerabilidade não re-detectada → badge "NÃO VISTA NA ÚLTIMA", estado só muda por operador |
| Lista vazia ≠ "limpo" | Intel de incidente sem matches → `[]`, nunca "clean" |
| Falhas reportadas | Feed de rede em baixo → job `failed` com o erro, nada fabricado |
| Só alvos autorizados | Auditoria exige `authorized: true` (403 caso contrário) |
| Não sondear atacantes | IPs apenas observados no tráfego nunca são auditados pelo scheduler |

**Fórmula da postura de segurança** (documentada e consistente):
`100 − Σ penalidade por incidente/achado aberto`
(CRITICAL 25 · HIGH 10 · MEDIUM 5 · LOW 2 · INFORMATIONAL 1), piso 0.

## 5. Jornada por fases (o que já foi construído)

### Fase 1 — Fundação (B1–B4) ✅
- **B1**: Alembic baseline, modelos `Asset` + `Job`, ciclo de vida de
  incidentes (`new/investigating/confirmed/false_positive/closed`),
  severidade INFORMATIONAL, suíte pytest.
- **B2**: API de agregação — `/assets`, `/topology`, `/posture`,
  `/stats/alerts`, `/activity`; normalização naive/aware de datas.
- **B3**: Dashboard SOC completo — topbar + sidebar (10 rotas, 8 reais),
  painel de topologia SVG (fluxo animado só com eventos reais <10min),
  postura, alertas, intel, ativos; página Threats com modal de
  investigação; página Assets com registo manual.
- **B4**: Ingester 2.0 — observações de tráfego (`flow`/`dns`/`http`/
  `tls`/`ssh`) alimentam `first_seen/last_seen` de ativos sem criar
  incidentes; batching; resumo de sessão; correção de duplo-INSERT
  (autoflush=False).

### Fase 2 — Auditoria de segurança (A1–A3) ✅
- **A1**: Modelos `AuditTarget`/`Audit`/`AuditFinding` + migrações; motor
  de verificações não destrutivas (headers, HSTS, TLS/certificado,
  redirect HTTP→HTTPS, cookies, robots/sitemap); autorização explícita.
- **A2**: Página Audits no dashboard (autorização em checkbox, polling,
  modal com evidências) + checks X-Powered-By/SameSite.
- **A3**: Relatórios markdown com evidências (descarregáveis) e
  **comparação de execuções** (apareceu/desapareceu/persistiu + delta
  de score); estados de achado open/fixed/accepted.

### Fase 2/3 — Inventário de vulnerabilidades ✅
- Read-model derivado dos achados (sem duplicação de dados);
  agregação por alvo+categoria+título; filtros e stats;
  PATCH de estado escreve no achado mais recente (fonte de verdade).

### Fase 3 — Threat Intelligence e operação (C1–C2) ✅
- **C1**: Feeds reais e gratuitas — FireHOL level 1 (4646 CIDRs/IPs),
  abuse.ch Feodo C2, Tor exit nodes (1258), IPsum ≥3 reports (18171);
  refresh rastreado como Job; matching IP exacto + **contenção CIDR**;
  enriquecimento de incidentes derivado on-read; painel e alerta no
  modal de incidente.
- **C2**: Gestão de operação — DELETE de ativos/incidentes/auditorias;
  **análise de segurança automática no registo de ativo** (sonda 443/80,
  https preferido); análise manual on-demand (`POST /assets/{ip}/audit`);
  **varredura automática a cada 2 min** de todos os sistemas conhecidos
  (thread em background, `AUDIT_SCHEDULE_SECONDS` configurável, mínimo
  30s); botão "Analisar tudo agora"; estado do scheduler visível.

## 6. Como correr

### Backend (Windows)
```bat
cd backend
call .venv\Scripts\activate.bat
set DATABASE_URL=sqlite:///./sentinelai.db
uvicorn app.main:app --port 8000
```

### Frontend
```bat
cd frontend
npm install   # primeira vez
npm run dev   # http://localhost:5173
```

### Ingestão (dados reais)
```bat
python detection\ingest.py detection\suricata\eve.sample.json --once
```

### Testes
```bat
cd backend
.venv\Scripts\python -m pytest tests\ -q   # 63 testes
```

### Configuração (`backend/.env`)
- `DATABASE_URL` — PostgreSQL (produção) ou SQLite (dev)
- `OPENROUTER_API_KEY` / `OPENROUTER_MODEL`
- `AUDIT_SCHEDULE_ENABLED` (default `true`) e `AUDIT_SCHEDULE_SECONDS` (default `120`)

## 7. Estado e qualidade

- **63 testes** a passar (auditorias usam servidor HTTP local real —
  zero rede externa nos testes; feeds stubadas).
- Lint sem erros; build de produção verde.
- Migrações Alembic testadas (upgrade/downgrade/upgrade); dev usa
  `create_all`, produção `alembic upgrade head`.
- Limitações conhecidas: PostgreSQL ainda não disponível no Windows de
  dev (portas bloqueadas) — SQLite cobre o dev; produção a definir
  (Docker no PC está bloqueado por política).

## 8. Próximos passos

| Prioridade | Trabalho |
|---|---|
| C3 (Fase 3) | Alertas/notificações quando incidente novo bate numa feed; relatório consolidado da varredura |
| Fase 3 | Correlação entre incidentes (mesmo IP, padrões temporais), atribuição assistida por IA |
| Fase 3/4 | Feed real de CVE/CVSS ligada ao inventário de vulnerabilidades |
| Fase 4 | Sistema modular de skills com permissões e histórico |
| Fase 5 | Network monitoring e consulta/correlação de logs |
| Fase 6 | Gestão de utilizadores, organizações e RBAC |
| Produção | Docker Compose (Postgres + backend + frontend), HTTPS, backups |

## 9. Lições de ambiente (aprendidas àcusta)

- **OneDrive** bloqueia/faz lock de ficheiros (a venv deve viver FORA da
  pasta sincronizada — ex.: `C:\venvs\sentinelai`).
- **Windows Application Control** bloqueia DLLs nativas não assinadas →
  SQLAlchemy pinado `>=2.0,<2.1`.
- WSL e Windows precisam de **venvs separadas** (binários incompatíveis).
- O JSON das colunas usa `sa.JSON().with_variant(JSONB, "postgresql")`
  para funcionar nos dois SGBDs.
