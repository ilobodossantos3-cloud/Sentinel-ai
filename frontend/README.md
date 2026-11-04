SentinelAI — painel de incidentes (React 19 + Vite 8 + axios).

```bash
npm install
npm run dev     # http://localhost:5173
npm run build   # build de produção em dist/
npm run lint    # oxlint
```

Funções:
- Lista de incidentes com estatísticas por severidade
- Modal com a análise IA (threat level, risk score, confidence, IOCs, ações)
- Se a análise ainda não existir (geração em background), o painel indica-o
  e permite tentar de novo
- Endereço da API configurável via `VITE_API_URL`
  (default: `http://127.0.0.1:8000`)

Exemplo:

```bash
VITE_API_URL=https://api.exemplo.pt npm run dev
```
