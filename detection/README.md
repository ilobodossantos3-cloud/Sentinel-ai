# SentinelAI — Deteção (Suricata)

Esta pasta liga o Suricata IDS à API da SentinelAI.

## Ingestor

`ingest.py` (apenas stdlib — sem instalar nada):

```bash
# seguir o log em tempo real (tail -f)
python3 ingest.py /var/log/suricata/eve.json

# processar só os registos existentes e sair (ideal para testes)
python3 ingest.py suricata/eve.sample.json --once

# API noutro endereço
python3 ingest.py eve.json --url http://10.10.10.10:8000

# personalizar base URL
python3 ingest.py eve.json --url http://10.10.10.10:8000
```

## Conversão de campos

| EVE JSON | Incidente SentinelAI |
|---|---|
| `src_ip`, `dest_ip` | `source_ip`, `destination_ip` |
| `src_port`, `dest_port` | `source_port`, `destination_port` |
| `proto` | `protocol` |
| `alert.signature_id` | `event_type` (`SID_<id>`) |
| `alert.signature` | `description` |
| `alert.severity` (1–4) | `severity` (1→CRITICAL … 4→LOW) |

Registos sem `event_type: alert` (ex.: `flow`) são ignorados.

## Observações de tráfego (B4)

Registos `flow`/`dns`/`http`/`tls`/`ssh` **não criam incidentes**: são
enviados em batch (até 25 registos) para `POST /ingest/observations`
e servem apenas para alimentar o inventário de ativos (`first_seen_at`,
`last_seen_at`). Ativos criados assim ficam com `is_registered=False`
(ativos observados, não registados manualmente).

Ao sair (Ctrl+C), o ingester imprime o resumo da sessão: alertas
submetidos, observações de tráfego, registos ignorados e erros.

## Regras

`rules/sentinel.rules` — exemplos mínimos de regras Suricata coerentes com
`suricata/eve.sample.json`. Em produção usar o ruleset Emerging Threats
(open) ou um mais completo, e configurar o output `eve-log` em `suricata.yaml`:

```yaml
outputs:
  - eve-log:
      enabled: yes
      filetype: regular
      filename: eve.json
      types:
        - alert
        - flow
        - dns
        - http
        - tls
```
