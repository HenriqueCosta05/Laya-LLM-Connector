# Laya ↔ Claude Code Connector — Design (MVP)

- **Data:** 2026-10-23
- **Status:** aprovado em brainstorming, aguardando revisão da spec
- **Base:** [Laya](https://github.com/NandhaKishorM/laya) 0.4.13

## 1. Objetivo

Um gateway entre o Laya (motor de decisão local, não-autoregressivo) e o Claude Code, que:

1. **traduz** entre os dois lados: nomes curtos e referências do lado do Claude, perguntas tipadas e distribuições do lado do Laya;
2. **repassa os resultados ao Claude com o mínimo de tokens**: linhas compactas, silêncio quando não há sinal útil, dados lidos localmente em vez de copiados pelo Claude.

O MVP é ativado por projeto: vale para sessões do Claude Code abertas no diretório deste repositório, via `.claude/settings.json` e `.mcp.json` versionados. Qualquer pessoa que clone o repo e rode o setup obtém o mesmo comportamento, sem alterar a configuração global do Claude Code.

### Fora de escopo (MVP)
Serviço de sistema/auto-start do daemon; estado de sugestão por sessão (`suggest = on_change`); raízes de paths além do projeto; resultado parcial em timeout; ONNX; fine-tuning de checkpoints próprios; instalação global para outros projetos; decisões ad hoc definidas pelo Claude.

## 2. Plataformas suportadas

- **Pré-requisito único:** [`uv`](https://docs.astral.sh/uv/). Ele provê o Python (≥ 3.10, exigência do Laya) e isola as dependências.
- **Daemon:** Linux, macOS, Windows nativo ou WSL2. Dispositivo automático, na ordem do Laya (CUDA → MPS → XPU → CPU), sobrescrevível com `device` no config.
- **Claude Code:** qualquer SO suportado, incluindo o caso de o Claude Code rodar no Windows com o projeto aberto pelo WSL (`\\wsl.localhost\...`) e o daemon dentro do WSL.
- **Checkpoint padrão:** `convaiinnovations/laya-multilingual` (322M, 100+ idiomas, o mais leve), com `max_loaded = 1` para caber em máquinas modestas. Configurável.
- **Requisitos indicativos:** ~2 GB de RAM livres para o daemon, ~1,5 GB de disco para o checkpoint. Em CPU, a latência por chamada varia de centenas de ms a alguns segundos conforme o processador; o `doctor` mede.

## 3. Arquitetura

```
 Máquina onde o Claude Code roda                          Host do daemon (mesma máquina, WSL ou remoto)
┌────────────────────────────────────────────────┐        ┌───────────────────────────────┐
│ Claude Code                                    │        │ laya-connector daemon         │
│  ├─ hook UserPromptSubmit → bin/laya_hook.py ──┼──HTTP─►│  OriginAuth middleware        │
│  └─ MCP stdio ───────────→ bin/laya_mcp.py ────┤        │  └─ laya.serve.create_app()   │
│                     src/laya_connector (núcleo)│        │     POST /v1/systemone[/batch]│
└────────────────────────────────────────────────┘        │     checkpoint · device auto  │
                                                          └───────────────────────────────┘
```

Abordagem escolhida: reusar o servidor oficial do Laya (`laya.serve.create_app()`), sem fork. Toda a tradução, formatação, política e log ficam no pacote `laya_connector`.

### 3.1 Módulos de `src/laya_connector`

| Módulo | Responsabilidade | Dependências |
|---|---|---|
| `config` | carrega `laya-connector.toml` + `.laya-connector/secrets.toml` + variáveis de ambiente `LAYA_CONNECTOR_*`; valores padrão | stdlib (`tomllib`) |
| `schemas` | carrega `schemas/*.json` (nome, versão, perguntas no formato do Laya, descrição de uma linha) | stdlib |
| `client` | HTTP para o daemon via `urllib`; timeout; envia `Bearer` só se a URL não for loopback; erros viram `DaemonError` tipado | stdlib |
| `translate` | (schema, estados) → payload `/v1/systemone[/batch]`; resposta → `Decision(qid, label, value, confidence, low_confidence, runner_up)` | `schemas` |
| `format` | `Decision`s → texto compacto (hook e cada ferramenta) | — |
| `policy` | funções puras: tier/effort sugerido; ação do guard (`block`/`warn`/`pass`) | `config` |
| `secrets_scan` | regex de segredos (prefixos `sk-ant-`, `sk-`, `ghp_`/`github_pat_`, `AKIA`, PEM `PRIVATE KEY`, JWT); mascaramento para log | stdlib |
| `paths` | resolve `paths`/`lines` dentro da raiz do projeto; recusa `..` e symlinks que escapam; ignora binários; trunca itens | stdlib |
| `log` | append JSONL em `.laya-connector/logs/AAAA-MM.jsonl` | stdlib |
| `daemon` | middleware ASGI `OriginAuth` + lançador uvicorn em torno de `laya.serve.create_app()` | `laya[serve]` (só no host do daemon) |

Os pontos de entrada em `bin/` são scripts com metadados PEP 723, executados com `uv run --script` (ambiente isolado e em cache por SO). Cada um adiciona `src/` ao `sys.path`.

| Script | Função | Dependências |
|---|---|---|
| `laya_hook.py` | hook | só stdlib |
| `laya_mcp.py` | servidor MCP | `mcp` |
| `laya_setup.py` | setup do host do daemon | só stdlib |
| `laya_daemon.py` | `start` / `stop` / `status` / `logs` | só stdlib; executa o daemon no `.venv-daemon` |
| `laya_doctor.py` | diagnóstico | só stdlib |

## 4. Daemon e autenticação por origem

- `uv run --script bin/laya_daemon.py start` sobe o daemon em segundo plano usando `.venv-daemon` (criado pelo setup, com `laya[serve]` e torch). Grava o PID em `.laya-connector/daemon.pid` e o log em `.laya-connector/logs/daemon.log`.
- Variáveis passadas ao Laya: `LAYA_MODELS=<checkpoint>`, `LAYA_MAX_LOADED=1`, `LAYA_DEVICE=<config ou vazio = auto>`, `LAYA_PRELOAD=1`. `LAYA_API_KEY` **nunca** é definida, porque a autenticação é do conector.
- Bind padrão `0.0.0.0:8000`, configurável.
- Middleware `OriginAuth`, decidido pelo IP do socket (`scope["client"]`) e nunca por cabeçalhos:
  - **local** = `127.0.0.0/8` e `::1`. Quando o daemon detecta que está no WSL2 (`/proc/version` contém `microsoft`), inclui também o IP do host Windows (gateway padrão), porque requisições do Claude Code no Windows podem chegar por ele. Entradas extras vão em `trusted_local` no config. Requisição local passa sem chave.
  - **remoto** = qualquer outro IP. Exige `Authorization: Bearer <remote_key>`, comparado com `hmac.compare_digest`; sem chave ou com chave errada → 401.
  - `GET /health` é liberado para qualquer origem e devolve só o status. O detalhe (dispositivo, checkpoints) fica restrito a origem local ou autenticada.
- `remote_key` é gerada pelo setup (`secrets.token_urlsafe(32)`) em `.laya-connector/secrets.toml`, com permissão restrita ao usuário (`chmod 600` em POSIX; no Windows, o arquivo fica no perfil do projeto, sem ACL extra no MVP).
- Se o bind não for loopback e não houver `remote_key`, o daemon **se recusa a iniciar**.

## 5. Hook `UserPromptSubmit` (`bin/laya_hook.py`)

Entrada: o JSON do evento no stdin (`prompt`, `session_id`, `cwd`, ...). Fluxo:

1. **Filtro local:** se o prompt começa com `/` ou tem menos de 15 caracteres → sai com código 0 e sem saída.
2. **Segredos:** se `secrets_scan` encontrar algo → imprime `{"decision": "block", "reason": "segredo detectado (<tipo>); remova e reenvie"}`, sem ecoar o valor. Registra no log a ação `block`.
3. **Uma chamada ao daemon:** estado `{"request": <prompt>}`. Prompt longo é cortado em início + fim, dentro do limite de caracteres do config. As perguntas vêm do schema `hook` (configurável):
   - `task_kind`: choice entre `bugfix, feature, refactor, explain, test, review, ops, other`;
   - `change_risk`: score em `trivial < local < cross-module < breaking`;
   - `needs_repo_context`, `needs_execution`: noul;
   - `difficulty`, `is_sensitive`: do `router_questions()` do Laya;
   - `jailbreak`, `sensitive_data`: do `guard_questions()` do Laya.

   Timeout padrão de 2,5 s. Erro ou timeout → **fail-open**: sai sem saída e registra no log a ação `fail_open`.
4. **Policy:**
   - `jailbreak ≥ 0.7` ou `sensitive_data ≥ 0.9` → `systemMessage` de aviso **para o usuário**, sem injetar no Claude.
   - O tier sugerido (`small` / `mid` / `frontier` + effort) só é mostrado ao usuário, via `systemMessage`, quando for `frontier` ou `small`. Regras:
     - `frontier`: sensível, `difficulty ≥ 2` ou baixa confiança;
     - `mid`: precisa de ferramentas, `difficulty ≥ 1`, ou domínio `code`/`data_analysis`;
     - `small`: o restante.
   - Campos com `low_confidence` (limiar por pergunta no config) são omitidos.
5. **Saída para o Claude** (`hookSpecificOutput.additionalContext`), uma linha, por exemplo:
   `[laya] task=refactor .82 | risk=cross-module | repo_ctx | run_tests | tier=frontier/high`
   Booleanos só aparecem quando verdadeiros. Se tudo for omitido, não há saída.
6. **Log:** `ts`, `session_id`, prompt mascarado (ou só hash, se `log.store_prompt = false`), versão do schema, rótulo e probabilidades por pergunta, latência e ação (`skip | block | warn | inject | fail_open`).

O hook nunca termina com código ≠ 0 por erro interno. Exceções são capturadas, registradas e convertidas em fail-open.

## 6. Servidor MCP (`bin/laya_mcp.py`)

Princípio: o Claude passa **referências** (`paths`, `lines`) em vez de copiar conteúdo nos argumentos, que são tokens de saída. O servidor lê os arquivos localmente.

`instructions` do servidor (~120 tokens, carregadas uma vez por sessão):
- legenda da linha `[laya]` (dica consultiva de um classificador local);
- schemas disponíveis, uma linha cada;
- "prefer `paths`/`lines` over pasting content";
- "if a tool says unavailable, decide without it".

### 6.1 `laya_classify`
- Entrada: `schema` (enum dos schemas classificáveis: `task_kind`, `commit_type`, `change_risk`, `issue_triage` + os do config) e exatamente um entre `items: [str]`, `paths: [glob]` ou `lines: {file, from?, to?}`.
- Saída:
  ```
  commit_type n=6 low=1
  a1b2 fix .93
  e5f6 ? refactor .41 / chore .33
  ```
  O id é o caminho relativo, o número da linha ou o índice (base 1).

### 6.2 `laya_filter_sources`
- Entrada: `query`, `sources: [{id, text}]` ou `paths`; opcionais `top_k` e `min` (padrão 0.5).
- Saída: `keep 3/12: s4 .91, s1 .84, s9 .62`, ordenado por P(relevante).

### 6.3 `laya_check_claim`
- Entrada: `claim`, `passages: [{id, text}]` ou `paths`.
- Saída:
  ```
  supported: 2 entail, 0 contradict, 3 neutral
  p2 entails .88
  ```
  O veredito é `supported` (≥ 1 entail e 0 contradict), `contradicted` (≥ 1 contradict e 0 entail), `mixed` (ambos) ou `unclear` (só neutros). Abaixo, uma linha para cada trecho não neutro.

### 6.4 Regras comuns
- Saída em texto puro, números com 2 casas sem o zero inicial, sem vetores de probabilidade (exceto o segundo colocado nos itens incertos).
- Até 128 itens por chamada (config). Os itens vão ao daemon em lotes de até 64; cada item é truncado a ~2.000 caracteres (início + fim).
- `paths`/`lines` só resolvem dentro da raiz do projeto. Binários são ignorados, e a contagem de ignorados/recusados aparece na linha de resumo.
- Timeout por chamada proporcional ao lote (config). No MVP, estourar o timeout devolve um erro claro.
- Daemon indisponível → `laya: unavailable (<motivo>) — decide without it`.

## 7. Configuração e instalação

| Arquivo | Conteúdo | Versionado |
|---|---|---|
| `laya-connector.toml` | `daemon_url`, `host`, `port`, `device`, `checkpoint`, `trusted_local`, timeouts, limiares, perguntas do hook, `log.*`, limites do MCP — só valores padrão portáveis | sim |
| `laya-connector.local.toml` | sobrescritas da máquina (ex.: `device`, `daemon_url` remoto) | não |
| `.laya-connector/secrets.toml` | `remote_key` | não |
| `.laya-connector/logs/` | JSONL e log do daemon | não |
| `.claude/settings.json` | hook `UserPromptSubmit` → `uv run --script bin/laya_hook.py` (timeout 5 s) | sim |
| `.mcp.json` | `laya` → `uv run --script bin/laya_mcp.py` | sim |
| `schemas/*.json` | schemas nomeados e versionados | sim |

Nenhum arquivo versionado contém caminhos absolutos, nomes de usuário, hardware ou segredos. Tudo o que é específico da máquina vai em `laya-connector.local.toml` ou `.laya-connector/`, ambos ignorados pelo git.

`uv run --script bin/laya_setup.py` (idempotente, roda no host do daemon):
1. cria `.venv-daemon` com `uv venv`;
2. sonda a GPU: instala o torch indicado por `uv pip install --torch-backend=auto` e valida com um tensor no dispositivo; se falhar, reinstala o torch CPU e grava `device = "cpu"` em `laya-connector.local.toml`;
3. instala `laya[serve]` na versão fixada;
4. gera `remote_key`;
5. baixa o checkpoint configurado;
6. executa o `doctor`.

O README traz o caminho mínimo: instalar o `uv`, clonar, rodar `laya_setup.py`, depois `laya_daemon.py start`, e abrir o projeto no Claude Code. Inclui ainda uma nota para quem usa Claude Code no Windows com daemon no WSL: rodar setup e daemon dentro do WSL.

**Risco a validar primeiro na implementação:** diretório de trabalho e shell usados pelo Claude Code ao executar hooks e servidores MCP de projeto, incluindo o caso Windows + pasta `\\wsl.localhost`. Se o caminho relativo falhar, o fallback é `$CLAUDE_PROJECT_DIR`.

## 8. Erros

| Situação | Comportamento |
|---|---|
| daemon fora do ar, timeout, 5xx | hook: fail-open + log; MCP: linha `unavailable` |
| 401 | mensagem explícita "remote_key inválida/ausente"; o `doctor` aponta a causa |
| segredo no prompt | hook bloqueia, informando o tipo sem ecoar o valor |
| schema desconhecido / entrada inválida | MCP: erro curto com os schemas válidos |
| path fora do projeto / symlink que escapa / binário | recusado ou ignorado, com contagem |
| bind externo sem `remote_key` | daemon não inicia |
| GPU indisponível ou incompatível | fallback para CPU registrado; o `doctor` mostra o dispositivo real |

## 9. Testes

- **Unitários (pytest via `uv`, sem modelo, sem rede, rodam em Linux, macOS e Windows):** `translate`/`format` com fixtures gravadas de respostas do Laya; `policy`; `secrets_scan` com casos positivos e negativos; `paths` em árvore temporária (glob, `..`, symlink, binário); `OriginAuth` com `create_app(router=<falso>)`, cobrindo loopback, gateway WSL (detecção simulada), IP externo, chave certa/errada/ausente e recusa de inicialização; hook ponta a ponta com stdin simulado e daemon HTTP falso; MCP com cliente em memória e daemon falso.
- **Integração (`-m slow`, opcional):** contra o daemon real, medindo a latência do hook e das ferramentas (o mesmo código do `doctor`).
- **CI:** GitHub Actions executando os testes unitários em `ubuntu-latest`, `macos-latest` e `windows-latest`.
- **Aceite do MVP**, numa sessão do Claude Code aberta no repositório:
  1. um prompt normal recebe a linha `[laya]`;
  2. um prompt com uma chave falsa `sk-ant-…` é bloqueado;
  3. o Claude chama `laya_classify` com `paths` e recebe a saída compacta;
  4. com o daemon parado, o prompt segue normalmente e as ferramentas respondem `unavailable`.

## 10. Riscos conhecidos

- **Latência em CPU:** 8 perguntas por prompt podem passar de 1 s em processadores modestos. Mitigação: reduzir as perguntas do hook no config (o guard por regex já cobre segredos).
- **GPUs antigas:** podem não ser suportadas pelas builds atuais do PyTorch. O setup detecta e cai para CPU.
- **Qualidade zero-shot:** os rótulos de tarefa e risco são fracos sem fine-tuning. A linha `[laya]` é consultiva, e o log local permite treinar um checkpoint depois.
- **Guard do Laya:** fraco para injeção embutida em documentos. Não é usado em conteúdo de ferramentas, só no prompt do usuário, e mesmo assim apenas como aviso.
- **API do Laya em evolução (0.4.x):** fixar a versão no `.venv-daemon`; as fixtures de resposta detectam mudanças de formato.
