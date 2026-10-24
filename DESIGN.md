---
name: Laya Connector
description: Painel de observabilidade local do hook do Laya, no padrão da categoria com acabamento Datadog.
colors:
  accent: "#a184ff"
  accent-soft: "rgba(161,132,255,.16)"
  bg: "#14161b"
  panel: "#1c1f26"
  raise: "#242832"
  line: "#2c313b"
  ink: "#e7e9ee"
  ink-2: "#aab0bc"
  ink-3: "#8c93a1"
  ok: "#41bb7d"
  ok-soft: "rgba(65,187,125,.14)"
  warn: "#e9a640"
  warn-ink: "#e9a640"
  warn-soft: "rgba(233,166,64,.15)"
  bad: "#f2625f"
  bad-soft: "rgba(242,98,95,.15)"
  info: "#58a6f5"
  neutral: "#737a88"
  accent-light: "#6a43d9"
  accent-soft-light: "rgba(106,67,217,.1)"
  bg-light: "#f3f4f7"
  panel-light: "#ffffff"
  raise-light: "#f6f7f9"
  line-light: "#e0e3e9"
  ink-light: "#1a1d23"
  ink-2-light: "#4a5260"
  ink-3-light: "#5f6876"
  ok-light: "#1c8a54"
  ok-soft-light: "rgba(28,138,84,.1)"
  warn-light: "#b97600"
  warn-ink-light: "#8a5200"
  warn-soft-light: "rgba(168,100,0,.1)"
  bad-light: "#cf3633"
  bad-soft-light: "rgba(207,54,51,.09)"
  info-light: "#1d6dcf"
  neutral-light: "#7a8291"
typography:
  headline:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
  title:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    fontFeature: "tnum"
  title-widget:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    fontFeature: "tnum"
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    fontFeature: "tnum"
  caption:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "tnum"
  axis:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    fontFeature: "tnum"
  mono:
    fontFamily: "Cascadia Mono, Cascadia Code, Consolas, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
rounded:
  xs: "2px"
  sm: "3px"
  md: "6px"
  pill: "8px"
  tag: "10px"
spacing:
  "4": "4px"
  "6": "6px"
  "8": "8px"
  "10": "10px"
  "12": "12px"
  "14": "14px"
  "16": "16px"
  "24": "24px"
components:
  widget:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "14px 16px 16px"
  widget-title:
    textColor: "{colors.ink}"
    typography: "{typography.title-widget}"
  kpi-tile:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
    padding: "12px 16px 14px"
  kpi-tile-ok:
    backgroundColor: "{colors.ok-soft}"
    textColor: "{colors.ok}"
  kpi-tile-warn:
    backgroundColor: "{colors.warn-soft}"
    textColor: "{colors.warn-ink}"
  kpi-tile-bad:
    backgroundColor: "{colors.bad-soft}"
    textColor: "{colors.bad}"
  tab-link:
    textColor: "{colors.ink-2}"
    padding: "10px 12px"
  tab-link-hover:
    textColor: "{colors.ink}"
  tag:
    backgroundColor: "{colors.raise}"
    textColor: "{colors.ink-2}"
    typography: "{typography.caption}"
    rounded: "{rounded.tag}"
    padding: "1px 8px"
  tag-low-confidence:
    backgroundColor: "{colors.warn-soft}"
    textColor: "{colors.warn-ink}"
  small-sample-pill:
    backgroundColor: "{colors.raise}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "0 6px"
  toplist-bar:
    backgroundColor: "{colors.raise}"
    rounded: "{rounded.sm}"
    height: "6px"
  confidence-meter:
    backgroundColor: "{colors.raise}"
    rounded: "{rounded.sm}"
    height: "6px"
  table-cell:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "8px 10px"
  table-header:
    textColor: "{colors.ink-3}"
    typography: "{typography.label}"
    padding: "0 10px 8px"
  inline-code:
    backgroundColor: "{colors.raise}"
    typography: "{typography.mono}"
    rounded: "{rounded.sm}"
    padding: "1px 5px"
---

# Design System: Laya Connector

## Overview

**Creative North Star: "O Painel de Plantão"**

O dashboard é um painel de observabilidade no padrão da categoria, executado sem ironia e no acabamento do Datadog: barra superior com marca, breadcrumb e período coberto; uma faixa de valores-consulta; e, abaixo, widgets densos, cada um com título, unidade e um único tipo de leitura (série temporal, histograma, toplist ou tabela). Quem abre o painel é o mantenedor em modo de operação, e cada pixel serve para responder rápido se o hook está dentro do orçamento de latência e se já há dados para treinar.

A base é escura (grafite), com tema claro completo via `prefers-color-scheme`. A profundidade vem só de tom e de filete: o fundo, os painéis um tom acima e as superfícies internas mais um tom, todos separados por linhas de 1px. Não há sombra em lugar nenhum. A cor é semântica: violeta para a série principal, seleção e links; verde, âmbar e vermelho apenas onde carregam estado; azul e cinza só para as ações `block` e `skip`.

O sistema recusa o grid de cards genéricos com número gigante e nada atrás: todo número grande vem com contexto (percentual do timeout, `n=`, denominador) e todo estado vazio explica o que vai aparecer ali e por quê.

**Key Characteristics:**
- Densidade de console: corpo em 13px, gutter de 12px, grid de 12 colunas.
- Plano por construção: tom + filete de 1px, zero sombras.
- Cor como dado: o mapa de ações (`inject`, `warn`, `skip`, `block`, `fail_open`) é fixo em todos os gráficos, legendas, barras e tags.
- Numerais tabulares em todo o documento; mono só para dados brutos e trechos de prompt.
- Dois temas com os mesmos nomes de token, escuro por padrão.

## Colors

Grafite frio com um único acento violeta e uma tríade de estado que só aparece quando há algo a dizer.

### Primary
- **Violeta de Sinal** (`accent`; `accent-light` no tema claro): série principal (linha de latência, barras do histograma dentro do orçamento, toplists sem cor de ação), seleção de texto, links, anel de foco e o fundo do logotipo. `accent-soft` existe como véu translúcido do mesmo tom.

### Tertiary (estado e ação)
- **Verde Saudável** (`ok`): KPI dentro do limiar, ação `inject`, confiança média ≥ 0,75.
- **Âmbar de Aviso** (`warn`, texto em `warn-ink`): KPI em alerta, ação `warn`, confiança entre 0,5 e 0,75, tags de baixa confiança. No tema claro `warn-ink` escurece para manter legibilidade do texto sobre `warn-soft`; no escuro os dois coincidem.
- **Vermelho de Falha** (`bad`): KPI estourado, ação `fail_open`, linha tracejada do timeout e seu rótulo, barras do histograma acima do timeout, confiança < 0,5.
- **Azul de Bloqueio** (`info`): reservado à ação `block` (segredo barrado).
- **Cinza de Descarte** (`neutral`): reservado à ação `skip`.
- Os véus `ok-soft`, `warn-soft` e `bad-soft` pintam o fundo de um KPI em estado e das tags de baixa confiança; nunca aparecem sozinhos sem o texto da cor cheia correspondente.

### Neutral
- **Grafite de Fundo** (`bg`): a página e a trilha da barra de rolagem.
- **Grafite de Painel** (`panel`): widgets, faixa de KPIs, barra superior e abas.
- **Grafite Elevado** (`raise`): trilhas de barra e de medidor, tags, pílula de amostra, `code` inline e o hover de linha de tabela.
- **Filete** (`line`): bordas de 1px de painéis, divisórias entre KPIs, linhas de tabela, linhas de grade dos gráficos.
- **Tinta** (`ink`, `ink-2`, `ink-3`): texto principal e números; texto secundário (breadcrumb, legendas, rótulos de toplist); texto terciário (subtítulos de widget, notas, cabeçalhos de tabela, eixos).

### Named Rules
**The Color Is Data Rule.** Cada ação tem uma cor e só uma (`inject` verde, `warn` âmbar, `skip` cinza, `block` azul, `fail_open` vermelho), e essa cor é a mesma no gráfico de pontos, nas barras empilhadas, nas toplists, na legenda e na tag da tabela. Nenhuma cor de estado é usada como decoração.

**The Threshold Paint Rule.** Um KPI só ganha cor quando tem limiar definido: latência em relação ao timeout (aviso ≥ 60%, falha ≥ 90%) e fail_open em relação às tentativas (aviso ≥ 1%, falha ≥ 5%). Contagens sem limiar (chamadas, bloqueios, rótulos) ficam neutras.

**The Twin Theme Rule.** Todo token existe nos dois temas com o mesmo nome; o tema claro troca valores, nunca papéis.

## Typography

**Display Font:** nenhuma; a hierarquia toda usa a fonte de interface.
**Body Font:** Segoe UI Variable Text (com Segoe UI, system-ui, sans-serif)
**Label/Mono Font:** Cascadia Mono (com Cascadia Code, Consolas, ui-monospace, monospace)

**Character:** a fonte do sistema do próprio ambiente do mantenedor (Windows), como nos consoles da categoria; mono entra só para dados que precisam ser lidos caractere a caractere.

### Hierarchy
- **Headline** (600, 28px, 1.15, -0.01em): o valor de cada KPI. A unidade vem num `small` de 14px/500 em `ink-2` colado ao número.
- **Title** (600, 16px): o nome do dashboard no breadcrumb. A marca usa 15px/600.
- **Title-widget** (600, 14px): título de cada widget, com subtítulo opcional em caption `ink-3` na mesma linha de base.
- **Body** (400, 13px, 1.45): texto corrido, células de tabela, rótulos de toplist. Estados vazios limitados a 60ch, trechos a 70ch.
- **Label** (500, 12px): título de KPI (`ink-2`) e cabeçalho de tabela (`ink-3`).
- **Caption** (400, 12px): notas sob widgets, subtítulos, legenda, tags e metadados.
- **Axis** (400, 11px): textos de eixo e valores dentro dos gráficos SVG, e a pílula "amostra pequena".
- **Mono** (400, 12px): identificadores de pergunta, horários na tabela de chamadas, trechos de prompt mascarados, motivos de bloqueio/falha e `code` inline.
- Os números de destaque da seção de fine-tuning usam 18px/600; é o único degrau intermediário.

### Named Rules
**The Tabular Everywhere Rule.** `font-variant-numeric: tabular-nums` vale para o documento inteiro, para que colunas de números e valores que se atualizam não dancem.

**The Mono Is Raw Data Rule.** Mono só para o que o mantenedor copiaria ou compararia literalmente (ids, prompts, motivos, caminhos). Rótulos, números e títulos ficam na fonte de interface.

**The Brazilian Number Rule.** Números usam vírgula decimal e ponto de milhar (`2,37 s`, `1.024`), segundos com duas casas abaixo do timeout, e "…" como o valor de ausência; nada é inventado para preencher um campo.

## Layout

Página única, sem JS. Barra superior (`panel`, filete inferior, padding 12px 24px) com marca, breadcrumb e período alinhado à direita; abaixo, uma barra de âncoras ("Ir para") com links para as seções. O `main` é um grid de 12 colunas com gutter de 12px, padding 16px 24px 32px e largura máxima de 1680px centrada.

Composição: a faixa de KPIs ocupa as 12 colunas em 6 células iguais; a segunda fila põe a série temporal em 8 colunas ao lado das ações por dia em 4; a terceira divide em três terços (histograma, toplist de ações, pilha de dois widgets); depois confiança (7) ao lado de fine-tuning (5); por fim a tabela de últimas chamadas em 12. Widgets empilhados dentro de uma coluna usam o mesmo gap de 12px.

Ritmo: degraus de 4, 6, 8, 10, 12, 14, 16 e 24px. 12px é o respiro estrutural (gutter, margem abaixo do título de widget), 16px o recuo lateral de widget e KPI, 24px a margem da página.

Responsivo:
- ≤ 1100px: terços e o widget de 5 colunas viram metades; 7 e 8 colunas viram largura total; KPIs em 3 colunas.
- ≤ 640px: tudo em largura total, KPIs em 2 colunas, margens laterais de 16px e gutter de 10px; a série temporal troca para um desenho próprio de viewBox estreito (360) para os textos de eixo manterem o tamanho; tabelas viram linhas em grid sem cabeçalho; dicas auxiliares de toplist somem.
- Tabelas largas ficam num contêiner com rolagem horizontal (largura mínima 620px) acima de 640px.

## Elevation & Depth

Sistema plano. A profundidade é tonal em três degraus (`bg` → `panel` → `raise`) mais um filete de 1px em `line`; não existe nenhum `box-shadow` no código, nem em hover. O único estado de hover com superfície é a linha de tabela, que sobe para `raise`.

### Named Rules
**The No Shadow Rule.** Nenhuma sombra, em nenhum tema. Separação é tom e filete de 1px; se um elemento precisa de destaque, ele ganha cor semântica, não elevação.

## Shapes

Cantos discretos e funcionais: 6px nos contêineres (widgets e faixa de KPIs, que recorta suas células com `overflow: hidden`), 3px em trilhas de barra e medidor, `code` inline e anel de foco, 2px nos quadrados de legenda e nas barras do histograma, 8–10px nas pílulas e tags. Bordas sempre de 1px; a única exceção é o sublinhado de 2px das abas. Marcadores de série são círculos de raio 4 nos pontos de latência e quadrados de 9px nas legendas.

## Components

### Widget
Contêiner padrão de tudo que não é KPI.
- **Corner Style:** suave (6px).
- **Background:** `panel` com filete de 1px em `line`.
- **Shadow Strategy:** nenhuma (ver Elevation & Depth).
- **Internal Padding:** 14px 16px 16px.
- **Título:** title-widget em linha flexível com subtítulo caption `ink-3` alinhado pela linha de base, 12px acima do conteúdo. Todo widget tem título e, quando o número tem unidade, ela vai no subtítulo.

### Faixa de KPIs
Uma única caixa de 6 células divididas por filetes verticais, não seis cards soltos.
- Cada célula: título em label `ink-2`, valor em headline, linha de contexto em caption `ink-3` (percentual do timeout, `n=`, denominador).
- Estado: célula inteira recebe o véu (`ok-soft`, `warn-soft`, `bad-soft`) e o valor a cor cheia correspondente; sem limiar, fica neutra.
- Pílula "amostra pequena" (`raise`, `ink-2`, 11px, raio 8px) marca estatísticas com menos observações que o mínimo de confiança.

### Navegação (abas de âncora)
- Faixa em `panel` com filete inferior; rótulo "Ir para" em `ink-3` seguido dos links em `ink-2`, peso 500, padding 10px 12px.
- **Hover:** texto vai a `ink` e aparece um sublinhado de 2px em `line`.
- **Foco:** anel de 2px em `accent` com 2px de offset e raio 3px (vale para todo link).
- **Mobile:** rolagem horizontal, sem quebra.

### Chips (tags)
- **Style:** `raise` com texto `ink-2`, caption, raio 10px, padding 1px 8px; pode levar um ponto de 9px na cor da ação.
- **State:** variante de baixa confiança em `warn-soft` com texto `warn-ink`. Não há estado selecionado; tags são somente leitura.

### Toplist
Lista com rótulo à esquerda, contagem em 600 e percentual em `ink-2` à direita, e uma barra de 6px em `raise` abaixo, preenchida proporcionalmente ao maior item. O preenchimento é `accent` por padrão ou a cor da ação quando a chave é uma ação.

### Tabela
- Cabeçalho em label `ink-3`, células em body com padding 8px 10px, filetes de 1px entre linhas, números alinhados à direita.
- Hover de linha em `raise`. Medidor de confiança: trilha de 6px em `raise`, preenchimento verde/âmbar/vermelho pelos limiares 0,75 e 0,5, valor ao lado.

### Gráficos (SVG inline)
- Grade e eixos em `line` e `ink-3` 11px; a linha de série em `accent` com 1,5px e opacidade 0,55, pontos coloridos pela ação.
- Limite (timeout) como linha tracejada `bad` 1,5px (5 4) com rótulo em `bad` 600 alinhado à direita.
- Barras empilhadas na ordem fixa das ações; histograma em `accent` com as faixas acima do timeout em `bad` e uma nota explicando o vermelho.
- Cada ponto e barra carrega um `title` com data, ação e valor.

### Estado vazio
Parágrafo em `ink-2` até 60ch: uma frase em negrito `ink` dizendo o que falta, seguida da explicação do que vai aparecer e, quando cabe, o comando em `code` inline.

## Do's and Don'ts

### Do:
- **Do** dar a todo widget um título e, quando houver, a unidade no subtítulo.
- **Do** acompanhar todo número grande do seu contexto: denominador, `n=` ou percentual do timeout.
- **Do** usar o mapa fixo de cores de ação em qualquer gráfico, legenda, barra ou tag nova.
- **Do** separar superfícies com o degrau tonal seguinte e um filete de 1px em `line`.
- **Do** definir todo token novo nos dois temas com o mesmo nome.
- **Do** escrever estados vazios que digam o que falta e o que vai aparecer ali.

### Don't:
- **Don't** usar sombra para separar ou destacar nada.
- **Don't** pintar um KPI sem limiar definido.
- **Don't** usar verde, âmbar, vermelho, azul ou cinza de ação como decoração.
- **Don't** usar mono para rótulos, títulos ou números de KPI.
- **Don't** montar a faixa de valores como cards soltos com número gigante e nada atrás.
- **Don't** preencher campos sem dado com números inventados; use "…" ou um estado vazio.

## Known gaps

Itens aceitos no envio que não são regras do sistema e não devem ser copiados:
1. Na segunda fila de terços, o widget "Ações" estica até a altura do histograma e deixa cerca de 40% vazio.
2. A pílula "amostra pequena" quebra de forma inconsistente entre os KPIs p50, p90 e fail_open.
3. Em ≤ 640px, o título h2 do widget e o subtítulo se espremem lado a lado porque a linha flexível não quebra.
