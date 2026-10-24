---
version: 1
slug: "src-laya-connector-dashboard-py"
primary_target: "src/laya_connector/dashboard.py"
related_targets: [".laya-connector/dashboard.html"]
---

# Dashboard de desempenho do hook

Scope: `.laya-connector/dashboard.html`, gerado por `src/laya_connector/dashboard.py` (`uv run --script bin/laya_dashboard.py`). Visitor mode: Operate.

Audience/job: o mantenedor, em duas tarefas — saúde do hook (latência contra o timeout, fail_open, bloqueios, avisos) e prontidão para fine-tuning (volume classificado, perguntas com baixa confiança, exemplos mascarados).

Constraints: arquivo único, sem JS obrigatório, sem rede, sem dependências; pt-BR; prompts só mascarados e truncados; nada de números inventados — volume pequeno aparece como estado vazio ou amostra insuficiente.

Direction: o padrão da categoria executado no nível do Datadog (escolha do usuário: canon). Unresolved: nenhum.

## Direction contract

THESIS: Painel de observabilidade da categoria, sem ironia, no acabamento do Datadog: widgets densos com título e unidade, séries temporais, toplists e tabelas. Recusa o grid de cards genéricos com número gigante e nada atrás.

OWN-WORLD: Escuro como base (claro via prefers-color-scheme), fundo grafite, painéis um tom acima com filete de 1px, sem sombra. Violeta para a série principal e seleção; verde ok, âmbar aviso, vermelho falha, só onde carregam significado. Fonte do sistema (Segoe UI), numerais tabulares, mono só para dados e trechos.

STORY: Em segundos o mantenedor sabe se o hook está dentro do orçamento de 2,5 s, quantas vezes falhou aberto e se já há dados para treinar.

FIRST VIEWPORT: Barra superior com nome, breadcrumb e período coberto. Faixa de valores-consulta (chamadas, p50, p90 contra timeout com cor por limiar, fail_open %, bloqueios, classificadas). Abaixo, latência por chamada com linha tracejada do timeout (2/3) ao lado de ações por dia empilhadas (1/3).

FORM: canon (padrão da categoria), referência de acabamento Datadog. seed: none (unavailable)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
