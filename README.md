# Laya ↔ Claude Code Connector

Gateway entre o [Laya](https://github.com/NandhaKishorM/laya), um motor de decisão local que não gera texto, e o Claude Code. Os resultados chegam ao Claude no menor número de tokens possível:

- **Hook `UserPromptSubmit`**: a cada prompt, faz uma chamada ao Laya e injeta uma linha como `[laya] task=refactor .82 | risk=cross-module | repo_ctx`. Bloqueia prompts com segredos colados e mostra avisos ou sugestões de modelo só para você.
- **Servidor MCP `laya`**: `laya_classify`, `laya_filter_sources` e `laya_check_claim` classificam itens em lote. Você passa *caminhos* em vez de colar conteúdo, e a resposta vem em texto compacto.
- **Daemon local**: o servidor oficial do Laya com autenticação por origem. A própria máquina acessa sem chave; qualquer outra origem precisa de `Authorization: Bearer <remote_key>`.

## Requisitos
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- ~2 GB de RAM livres e ~1,5 GB de disco para o checkpoint `laya-multilingual`. GPU é opcional.

## Instalação
```bash
git clone <este repositório> && cd <pasta>
uv run --script bin/laya_setup.py        # venv do daemon, torch (GPU→CPU), laya, chave, checkpoint
uv run --script bin/laya_daemon.py start
uv run --script bin/laya_doctor.py       # confere daemon, auth e latência
```
Depois abra a pasta no Claude Code. Ele lê `.claude/settings.json` (o hook) e `.mcp.json` (o servidor MCP) e pede sua aprovação na primeira vez.

**Claude Code no Windows com o projeto no WSL:** rode setup e daemon *dentro* do WSL. O Claude Code no Windows acessa o daemon por `localhost`.

> **Atenção (WSL):** por padrão o daemon confia no gateway do WSL (faixa `172.16.0.0/12`) para que o Windows o acesse sem chave. Com `netsh portproxy` no Windows ou rede WSL no modo *mirrored*, o tráfego externo chega com a origem do gateway e **ignora a `remote_key`**. Nesse caso defina `[daemon] trust_wsl_gateway = false` em `laya-connector.local.toml`.

## Configuração
- `laya-connector.toml`: padrões portáveis (versionado).
- `laya-connector.local.toml`: ajustes desta máquina, por exemplo `[daemon] device = "cpu"` ou `url` de um daemon remoto (ignorado pelo git).
- `.laya-connector/secrets.toml`: `remote_key` gerada pelo setup (ignorado pelo git). Clientes remotos usam a mesma chave em `[secrets] remote_key`.
- `schemas/*.json`: as perguntas enviadas ao Laya. Edite `schemas/hook.json` para reduzir a latência do hook.

## Comandos do daemon
`uv run --script bin/laya_daemon.py start | stop | status | logs`

## Testes
`uv run pytest`: rodam sem modelo e sem rede.

## Limitações
- Sem fine-tuning, os rótulos de tarefa e risco são aproximados. A linha `[laya]` é só uma dica, e o log em `.laya-connector/logs/` serve para treinar um checkpoint depois.
- O guard do Laya é fraco contra injeção embutida em documentos. Segredos são detectados por regex, sem depender do modelo.
- Em CPU, se o hook passar do timeout ele simplesmente não injeta nada. Use o `doctor` para medir.
