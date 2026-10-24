# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
O próprio mantenedor do conector, operando o Laya na sua máquina (Windows + WSL) enquanto usa o Claude Code no dia a dia. Dois trabalhos:
1. Saúde operacional: ver se o hook está rápido o bastante, quantas vezes cai em `fail_open` por timeout, o que foi bloqueado e o que só gerou aviso.
2. Avaliar fine-tuning: medir quanto dado rotulado o log já acumulou e onde o classificador fica com baixa confiança, para decidir quando treinar um checkpoint próprio.

Não há outros públicos confirmados.

## Product Purpose
Gateway entre o Laya (motor de decisão local que não gera texto) e o Claude Code, entregando classificações no menor número de tokens possível: um hook `UserPromptSubmit` que injeta uma linha `[laya] ...`, um servidor MCP com `laya_classify`, `laya_filter_sources` e `laya_check_claim`, e um daemon local com autenticação por origem. Sucesso é o Claude calibrar esforço com dicas baratas sem que o hook atrase o prompt.

## Positioning
Roda inteiramente local, fail-open (se o Laya não responde a tempo, o prompt segue sem a dica) e com detecção de segredos por regex antes de qualquer chamada ao modelo. O log JSONL é ao mesmo tempo telemetria e matéria-prima de fine-tuning.

## Operating Context
- Daemon em WSL (Ubuntu), iniciado no logon pela tarefa agendada "Laya Connector"; o Claude Code no Windows acessa por `localhost:8000`.
- Ferramentas via `uv run --script bin/*.py`; sem dependências Python no núcleo (`dependencies = []`).
- Log mensal em `.laya-connector/logs/YYYY-MM.jsonl`, um registro por prompt do hook: `ts`, `session_id`, `prompt` (mascarado), `prompt_sha256`, `schema`, `action` (`inject`, `warn`, `skip`, `block`, `fail_open`), `latency_ms`, `tier` (`small`/`mid`/`frontier`), `decisions` (rótulo, valor, confiança, flag `low` por pergunta), `probabilities`, `secrets`, `error`.
- Chamadas MCP não são registradas no log.

## Capabilities and Constraints
- Dashboard de desempenho: HTML estático autocontido gerado por um script em `bin/`, lendo os JSONL. Sem servidor, sem dependências novas.
- O dashboard pode exibir trechos de prompt, sempre já mascarados por `mask_secrets` e truncados.
- Interface e mensagens em pt-BR; identificadores e rótulos técnicos em inglês, como no código.
- Testes rodam sem modelo e sem rede (`uv run pytest`).

## Evidence on Hand
- Log real: `.laya-connector/logs/2026-10.jsonl` (poucas linhas até agora). Não inventar volumes, taxas ou benchmarks.
- `bin/laya_doctor.py` mede latência pontual do hook.

## Product Principles
1. O hook nunca pode atrasar o usuário: latência e `fail_open` são as métricas que mais importam.
2. Privacidade por padrão: segredos nunca saem mascarados de forma incompleta, e texto de prompt só aparece truncado.
3. Dicas, não ordens: confiança baixa é mostrada como tal, nunca escondida.
4. Tudo local e sem dependências novas.
