"""Shadow log -> performance summary -> one self-contained HTML file."""
from __future__ import annotations

import argparse
import json
import re
import webbrowser
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote

from . import config as config_mod
from .paths import truncate
from .secrets_scan import mask_secrets

ACTIONS = ("inject", "warn", "skip", "block", "fail_open")
TIERS = ("small", "mid", "frontier")
LATENCY_BUCKETS = (250, 500, 1000, 1500, 2000, 2500, 3000)
EXCERPT_CHARS = 140
RECENT = 12
LOW_EXAMPLES = 8


def load_records(log_dir: Path) -> tuple[list[dict], int]:
    """Every record of every monthly file, oldest first, plus how many lines were unreadable."""
    records: list[dict] = []
    bad = 0
    for path in sorted(log_dir.glob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(rec, dict) and isinstance(rec.get("ts"), str):
                records.append(rec)
            else:
                bad += 1
    records.sort(key=lambda r: r["ts"])
    return records, bad


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * p // 100))
    return ordered[int(rank) - 1]


def excerpt(rec: dict) -> str | None:
    prompt = rec.get("prompt")
    if not isinstance(prompt, str):
        return None
    text = re.sub(r"\s+", " ", mask_secrets(prompt)).strip()  # masked again: older lines may predate a pattern
    return truncate(text, EXCERPT_CHARS)


def _latency(rec: dict) -> float | None:
    value = rec.get("latency_ms")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _histogram(values: list[float]) -> list[tuple[int | None, int]]:
    counts = [0] * (len(LATENCY_BUCKETS) + 1)
    for value in values:
        index = next((i for i, upper in enumerate(LATENCY_BUCKETS) if value <= upper), len(LATENCY_BUCKETS))
        counts[index] += 1
    return list(zip((*LATENCY_BUCKETS, None), counts))


def _questions(records: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rec in records:
        decisions = rec.get("decisions")
        if not isinstance(decisions, dict):
            continue
        for qid, d in decisions.items():
            if not isinstance(d, dict):
                continue
            q = out.setdefault(qid, {"n": 0, "low": 0, "confidence": [], "labels": Counter()})
            q["n"] += 1
            q["low"] += bool(d.get("low"))
            if isinstance(d.get("confidence"), (int, float)):
                q["confidence"].append(float(d["confidence"]))
            q["labels"][str(d.get("label"))] += 1
    for q in out.values():
        conf = q.pop("confidence")
        q["mean_confidence"] = sum(conf) / len(conf) if conf else None
        q["labels"] = q["labels"].most_common()
    return out


def _low_questions(rec: dict) -> list[tuple[str, str, float]]:
    decisions = rec.get("decisions")
    if not isinstance(decisions, dict):
        return []
    return [(qid, str(d.get("label")), float(d.get("confidence") or 0))
            for qid, d in decisions.items() if isinstance(d, dict) and d.get("low")]


def _daily(records: list[dict]) -> list[dict]:
    days: dict[str, list[dict]] = {}
    for rec in records:
        days.setdefault(rec["ts"][:10], []).append(rec)
    rows = []
    for day, recs in sorted(days.items()):
        latencies = [v for v in map(_latency, recs) if v is not None]
        rows.append({"day": day, "total": len(recs),
                     "classified": sum(isinstance(r.get("decisions"), dict) for r in recs),
                     "fail_open": sum(r.get("action") == "fail_open" for r in recs),
                     "p50": percentile(latencies, 50)})
    return rows


def summarize(records: list[dict], timeout_ms: float, bad_lines: int = 0) -> dict:
    latencies = [v for v in map(_latency, records) if v is not None]
    classified = [r for r in records if isinstance(r.get("decisions"), dict)]
    low_records = [r for r in classified if _low_questions(r)]
    actions = Counter(str(r.get("action")) for r in records)
    return {
        "total": len(records),
        "bad_lines": bad_lines,
        "first": records[0]["ts"] if records else None,
        "last": records[-1]["ts"] if records else None,
        "sessions": len({r["session_id"] for r in records if r.get("session_id")}),
        "actions": [(a, actions.get(a, 0)) for a in ACTIONS]
                   + sorted((a, n) for a, n in actions.items() if a not in ACTIONS),
        "latency": {
            "n": len(latencies), "timeout_ms": timeout_ms,
            "p50": percentile(latencies, 50), "p90": percentile(latencies, 90),
            "p99": percentile(latencies, 99), "max": max(latencies, default=None),
            "over_timeout": sum(v > timeout_ms for v in latencies),
            "histogram": _histogram(latencies),
        },
        "daily": _daily(records),
        "tiers": [(t, sum(r.get("tier") == t for r in records)) for t in TIERS],
        "questions": _questions(classified),
        "training": {
            "classified": len(classified),
            "unique_prompts": len({r.get("prompt_sha256") for r in classified if r.get("prompt_sha256")}),
            "with_low": len(low_records),
        },
        "secrets": Counter(k for r in records for k in (r.get("secrets") or []) if isinstance(k, str)).most_common(),
        "errors": Counter(truncate(str(r.get("error")), 120) for r in records
                          if r.get("action") == "fail_open").most_common(),
        "low_examples": [{"ts": r["ts"], "excerpt": excerpt(r), "low": _low_questions(r)}
                         for r in reversed(low_records[-LOW_EXAMPLES:])],
        "series": [{"ts": r["ts"], "action": str(r.get("action")), "latency_ms": _latency(r)} for r in records],
        "recent": [{"ts": r["ts"], "action": str(r.get("action")), "latency_ms": _latency(r),
                    "tier": r.get("tier"), "excerpt": excerpt(r)} for r in reversed(records[-RECENT:])],
    }


def build(root: Path, out: Path | None = None, now: datetime | None = None) -> Path:
    cfg = config_mod.load(root)
    records, bad = load_records(cfg.log_dir)
    summary = summarize(records, cfg.hook_timeout * 1000, bad)
    summary["generated"] = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    target = out or cfg.state_dir / "dashboard.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(summary), encoding="utf-8")
    return target


# --- rendering --------------------------------------------------------------------------------

SMALL_SAMPLE = 20
ACTION_LABEL = {"inject": "inject", "warn": "warn", "skip": "skip", "block": "block", "fail_open": "fail_open"}
ACTION_HELP = {"inject": "dica injetada", "warn": "dica + aviso ao usuário", "skip": "ignorado (comando ou curto)",
               "block": "bloqueado por segredo", "fail_open": "Laya não respondeu a tempo"}

CSS = """
:root{color-scheme:dark;--bg:#14161b;--panel:#1c1f26;--raise:#242832;--line:#2c313b;--ink:#e7e9ee;--ink-2:#aab0bc;
--ink-3:#8c93a1;--accent:#a184ff;--accent-soft:rgba(161,132,255,.16);--ok:#41bb7d;--warn:#e9a640;--bad:#f2625f;
--warn-ink:#e9a640;--info:#58a6f5;--neutral:#737a88;--ok-soft:rgba(65,187,125,.14);--warn-soft:rgba(233,166,64,.15);--bad-soft:rgba(242,98,95,.15);
--mono:"Cascadia Mono","Cascadia Code",Consolas,ui-monospace,monospace}
@media (prefers-color-scheme:light){:root{color-scheme:light;--bg:#f3f4f7;--panel:#fff;--raise:#f6f7f9;--line:#e0e3e9;
--ink:#1a1d23;--ink-2:#4a5260;--ink-3:#5f6876;--accent:#6a43d9;--accent-soft:rgba(106,67,217,.1);--ok:#1c8a54;--warn:#b97600;--warn-ink:#8a5200;
--bad:#cf3633;--info:#1d6dcf;--neutral:#7a8291;--ok-soft:rgba(28,138,84,.1);--warn-soft:rgba(168,100,0,.1);--bad-soft:rgba(207,54,51,.09)}}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--bg);scrollbar-color:var(--line) var(--bg);scroll-behavior:smooth}
body{font:400 13px/1.45 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;color:var(--ink);background:var(--bg);
font-variant-numeric:tabular-nums;min-width:320px}
::selection{background:var(--accent);color:#fff}
a{color:var(--accent);text-underline-offset:3px}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
.top{display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px;padding:12px 24px;background:var(--panel);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;font-weight:600;font-size:15px}
.brand svg{width:22px;height:22px}
.crumb{color:var(--ink-2)}
.crumb h1{display:inline;font-size:16px;color:var(--ink);font-weight:600}
.period{margin-left:auto;display:flex;gap:16px;color:var(--ink-2);flex-wrap:wrap}
.period b{color:var(--ink);font-weight:600}
.tabs{display:flex;gap:4px;padding:0 24px;background:var(--panel);border-bottom:1px solid var(--line);overflow-x:auto}
.tabs a{padding:10px 12px;color:var(--ink-2);text-decoration:none;border-bottom:2px solid transparent;white-space:nowrap;font-weight:500}
.tabs a:hover{color:var(--ink);border-bottom-color:var(--line)}
.tabs span{padding:10px 12px 10px 0;color:var(--ink-3);white-space:nowrap}
main{padding:16px 24px 32px;display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px;max-width:1680px;margin:0 auto}
.w{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px 16px 16px;min-width:0;scroll-margin-top:12px}
.stack{display:grid;gap:12px;align-content:start;min-width:0}
.s3{grid-column:span 3}.s4{grid-column:span 4}.s5{grid-column:span 5}.s7{grid-column:span 7}.s8{grid-column:span 8}.s12{grid-column:span 12}
.w h2{font-size:14px;font-weight:600;display:flex;align-items:baseline;gap:8px;margin-bottom:12px}
.w h2 small{font-weight:400;color:var(--ink-3);font-size:12px}
.kpis{grid-column:span 12;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--line);border-radius:6px;
background:var(--panel);overflow:hidden}
.kpi{padding:12px 16px 14px;border-left:1px solid var(--line);position:relative}
.kpi:first-child{border-left:0}
.kpi h2{font-size:12px;font-weight:500;color:var(--ink-2)}
.kpi .v{font-size:28px;font-weight:600;line-height:1.15;margin-top:4px;letter-spacing:-.01em}
.kpi .v small{font-size:14px;font-weight:500;color:var(--ink-2);margin-left:2px}
.kpi p{color:var(--ink-3);font-size:12px;margin-top:2px}
.kpi.ok .v{color:var(--ok)}.kpi.warn .v{color:var(--warn-ink)}.kpi.bad .v{color:var(--bad)}
.small-n{display:inline-block;margin-left:6px;padding:0 6px;border-radius:8px;background:var(--raise);color:var(--ink-2);font-size:11px}
.kpi.ok{background:var(--ok-soft)}.kpi.warn{background:var(--warn-soft)}.kpi.bad{background:var(--bad-soft)}
svg.chart{display:block;width:100%;height:auto;overflow:visible}
svg.narrow{display:none}
.chart text{fill:var(--ink-3);font-size:11px}
.chart .grid{stroke:var(--line);stroke-width:1}
.chart .limit{stroke:var(--bad);stroke-width:1.5;stroke-dasharray:5 4}
.chart .limit-t{fill:var(--bad);font-weight:600}
.chart .path{fill:none;stroke:var(--accent);stroke-width:1.5;opacity:.55}
.c-inject{fill:var(--ok)}.c-warn{fill:var(--warn)}.c-skip{fill:var(--neutral)}.c-block{fill:var(--info)}.c-fail_open{fill:var(--bad)}
.b-inject{background:var(--ok)}.b-warn{background:var(--warn)}.b-skip{background:var(--neutral)}.b-block{background:var(--info)}.b-fail_open{background:var(--bad)}
.c-bar{fill:var(--accent)}.c-bar-over{fill:var(--bad)}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:10px;color:var(--ink-2);font-size:12px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i,.dot{display:inline-block;width:9px;height:9px;border-radius:2px;flex:none}
.top-list{list-style:none;display:grid;gap:9px}
.top-list li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;align-items:baseline}
.top-list .bar{grid-column:1/-1;height:6px;background:var(--raise);border-radius:3px;overflow:hidden}
.top-list .bar i{display:block;height:100%;background:var(--accent);border-radius:3px}
.top-list .bar i[class]{background:none}.top-list .bar i.b-inject{background:var(--ok)}.top-list .bar i.b-warn{background:var(--warn)}
.top-list .bar i.b-skip{background:var(--neutral)}.top-list .bar i.b-block{background:var(--info)}.top-list .bar i.b-fail_open{background:var(--bad)}
.top-list .n{font-weight:600}
.top-list .k{color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mono{font-family:var(--mono);font-size:12px}
table{width:100%;border-collapse:collapse}
th{font-size:12px;font-weight:500;color:var(--ink-3);text-align:left;padding:0 10px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--raise)}
th.r,td.r{text-align:right}
.conf{display:flex;align-items:center;gap:8px;min-width:120px}
.conf .track{flex:1;height:6px;background:var(--raise);border-radius:3px;overflow:hidden}
.conf .track i{display:block;height:100%;border-radius:3px}
.tag{display:inline-flex;align-items:center;gap:6px;padding:1px 8px;border-radius:10px;background:var(--raise);font-size:12px;
white-space:nowrap;color:var(--ink-2)}
.tag.lowc{background:var(--warn-soft);color:var(--warn-ink)}
.labels{color:var(--ink-2)}
.labels b{color:var(--ink);font-weight:600}
.facts{display:flex;flex-wrap:wrap;margin-bottom:14px;color:var(--ink-2)}
.facts span{padding:0 14px;border-left:1px solid var(--line)}
.facts span:first-child{padding-left:0;border-left:0}
.facts b{font-size:18px;font-weight:600;color:var(--ink);margin-right:5px}
.samples{list-style:none;display:grid;gap:10px}
.samples li{padding-top:10px;border-top:1px solid var(--line)}
.samples q{display:block;font-family:var(--mono);font-size:12px;color:var(--ink);quotes:none;overflow-wrap:anywhere}
.samples .meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;color:var(--ink-3);font-size:12px}
.excerpt{font-family:var(--mono);font-size:12px;color:var(--ink-2);overflow-wrap:anywhere;max-width:70ch}
.empty{color:var(--ink-2);padding:18px 0 6px;max-width:60ch}
.empty b{color:var(--ink);display:block;margin-bottom:4px;font-weight:600}
.empty code,.foot code{font-family:var(--mono);font-size:12px;background:var(--raise);padding:1px 5px;border-radius:3px}
.note{color:var(--ink-3);font-size:12px;margin-top:10px}
.scroll{overflow-x:auto;scrollbar-width:thin}
.scroll table{min-width:620px}
.foot{grid-column:span 12;color:var(--ink-3);font-size:12px;display:flex;flex-wrap:wrap;gap:6px 18px;padding-top:4px}
@media (max-width:1100px){.s3,.s4,.s5{grid-column:span 6}.s7,.s8{grid-column:span 12}.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}
.kpi:nth-child(4){border-left:0}.kpi:nth-child(n+4){border-top:1px solid var(--line)}}
@media (max-width:640px){.top,.tabs{padding-left:16px;padding-right:16px}main{padding:12px 16px 24px;gap:10px}
.s3,.s4,.s5,.s7,.s8{grid-column:span 12}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi:nth-child(n){border-left:1px solid var(--line);border-top:1px solid var(--line)}.kpi:nth-child(odd){border-left:0}
.kpi:nth-child(-n+2){border-top:0}.period{margin-left:0}.hide-sm{display:none}
svg.wide{display:none}svg.narrow{display:block}
.scroll table.reflow{min-width:0}.reflow thead{display:none}.reflow,.reflow tbody{display:block}
.reflow tr{display:grid;gap:6px 12px;padding:10px 0;border-bottom:1px solid var(--line)}.reflow tr:last-child{border-bottom:0}
.reflow td{display:block;padding:0;border:0;text-align:left}tbody tr:hover td{background:none}
.q tr{grid-template-columns:minmax(0,1fr) auto}.q .qid,.q .lab{grid-column:1/-1}.q .n{display:none}
.ev tr{grid-template-columns:auto auto 1fr auto;align-items:center}.ev .ex{grid-column:1/-1}.ev .lat{text-align:right}}
"""

LOGO = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="5" fill="var(--accent)"/>'
        '<path d="M7 6v12h10" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="15.5" cy="9.5" r="2.2" fill="#fff"/></svg>')


def _e(value) -> str:
    return escape("" if value is None else str(value), quote=True)


def _int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _ms(value: float | None) -> str:
    if value is None:
        return "…"
    if value >= 1000:
        return f"{value / 1000:.2f} s".replace(".", ",")
    return f"{value:.0f} ms"


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "…"


def _conf(x: float | None) -> str:
    return "…" if x is None else f"{x:.2f}".replace(".", ",")


def _when(ts: str | None, with_day: bool = True) -> str:
    if not ts:
        return "…"
    try:
        moment = datetime.fromisoformat(ts).astimezone(timezone.utc)
    except ValueError:
        return ts
    return moment.strftime("%d/%m %H:%M" if with_day else "%H:%M")


def _small(n: int) -> str:
    """Marks statistics computed from too few observations to trust (display heuristic, not a product threshold)."""
    return f'<span class="small-n" title="menos de {SMALL_SAMPLE} observações">amostra pequena</span>' if n < SMALL_SAMPLE else ""


def _seconds(value: float) -> str:
    return f"{value / 1000:.2f} s".replace(".", ",")


def _level(value: float | None, warn: float, bad: float) -> str:
    if value is None:
        return ""
    return "bad" if value >= bad else ("warn" if value >= warn else "ok")


def _kpis(s: dict) -> str:
    lat, timeout = s["latency"], s["latency"]["timeout_ms"]
    actions = dict(s["actions"])
    attempted = lat["n"]
    fail = actions.get("fail_open", 0)
    fail_share = fail / attempted if attempted else None

    def cell(title, value, note, level=""):
        return f'<div class="kpi {level}"><h2>{title}</h2><div class="v">{value}</div><p>{note}</p></div>'

    def share(v):
        if v is None or not timeout:
            return "sem medições"
        return f"{100 * v / timeout:.0f}% do timeout · n={attempted}{_small(attempted)}"

    def seconds(v):
        return "…" if v is None else _seconds(v).replace(" s", "<small>s</small>")

    return "".join((
        '<section class="kpis" aria-label="Resumo">',
        cell("Chamadas do hook", _int(s["total"]), f'{s["sessions"]} sessões · {attempted} classificações tentadas'),
        cell("Latência p50", seconds(lat["p50"]), share(lat["p50"]), _level(lat["p50"] and lat["p50"] / timeout, .6, .9)),
        cell("Latência p90", seconds(lat["p90"]), share(lat["p90"]), _level(lat["p90"] and lat["p90"] / timeout, .6, .9)),
        cell("Fail open", _pct(fail, attempted) if attempted else "…",
             f"{fail} de {attempted} tentativas{_small(attempted)}" if attempted else "nenhuma tentativa",
             _level(fail_share, .01, .05)),
        cell("Bloqueios", _int(actions.get("block", 0)), "prompts com segredo barrados"),
        cell("Rótulos para treino", _int(s["training"]["classified"]),
             f'{s["training"]["unique_prompts"]} prompts únicos'),
        "</section>",
    ))


def _nice_max(value: float) -> float:
    for step in (250, 500, 1000, 2000, 5000, 10000):
        if value <= step * 6:
            return -(-value // step) * step
    return value


def _latency_chart(s: dict, records_series: list[dict]) -> str:
    points = [r for r in records_series if r["latency_ms"] is not None]
    if not points:
        return ('<p class="empty"><b>Nenhuma latência registrada ainda.</b>Cada prompt classificado pelo hook entra aqui; '
                'comandos com <code>/</code> e prompts curtos são ignorados e não medem latência.</p>')
    # Two drawings of the same series: phones get a narrow viewBox so axis text keeps its size.
    chart = _latency_svg(s, points, 760, "wide") + _latency_svg(s, points, 360, "narrow")
    present = [a for a in ACTIONS if any(p["action"] == a for p in points)]
    return chart + '<div class="legend">' + "".join(
        f'<span><i class="b-{a}"></i>{ACTION_LABEL[a]}</span>' for a in present) + "</div>"


def _latency_svg(s: dict, points: list[dict], w: int, variant: str) -> str:
    timeout = s["latency"]["timeout_ms"]
    top = _nice_max(max(max(p["latency_ms"] for p in points), timeout) * 1.12)
    h, left, bottom, pad = 230, 48, 26, 10
    inner_w, inner_h = w - left - pad, h - bottom - pad
    step = inner_w / max(len(points) - 1, 1)

    def x(i):
        return left + (i * step if len(points) > 1 else inner_w / 2)

    def y(v):
        return pad + inner_h * (1 - v / top)

    ticks = [top * k / 4 for k in range(5)]
    hidden = ' aria-hidden="true"' if variant == "narrow" else ' role="img" aria-label="Latência por chamada, em ordem cronológica"'
    out = [f'<svg class="chart {variant}" viewBox="0 0 {w} {h}"{hidden}>']
    for t in ticks:
        out.append(f'<line class="grid" x1="{left}" x2="{w - pad}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                   f'<text x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{_e(_seconds(t))}</text>')
    day = None
    for i, p in enumerate(points):
        if p["ts"][:10] != day:
            day = p["ts"][:10]
            out.append(f'<line class="grid" x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{pad}" y2="{h - bottom}" opacity=".6"/>'
                       f'<text x="{x(i) + 4:.1f}" y="{h - 8}">{_e(day[8:10] + "/" + day[5:7])}</text>')
    out.append(f'<line class="limit" x1="{left}" x2="{w - pad}" y1="{y(timeout):.1f}" y2="{y(timeout):.1f}"/>'
               f'<text class="limit-t" x="{w - pad}" y="{y(timeout) - 6:.1f}" text-anchor="end">timeout {_e(_seconds(timeout))}</text>')
    if len(points) > 1:
        path = " ".join(f"{x(i):.1f},{y(p['latency_ms']):.1f}" for i, p in enumerate(points))
        out.append(f'<polyline class="path" points="{path}"/>')
    for i, p in enumerate(points):
        out.append(f'<circle class="c-{_e(p["action"])}" cx="{x(i):.1f}" cy="{y(p["latency_ms"]):.1f}" r="4">'
                   f'<title>{_e(_when(p["ts"]))} · {_e(p["action"])} · {_e(_seconds(p["latency_ms"]))}</title></circle>')
    out.append("</svg>")
    return "".join(out)


def _daily_chart(s: dict, by_day: dict[str, Counter]) -> str:
    if not by_day:
        return '<p class="empty"><b>Sem dias registrados.</b>O log mensal ainda está vazio.</p>'
    days = sorted(by_day)[-14:]
    tick = -(-max(sum(by_day[d].values()) for d in days) // 4)
    top = tick * 4
    w, h, left, bottom, pad = 360, 230, 28, 26, 10
    inner_h = h - bottom - pad
    slot = (w - left - 4) / len(days)
    bar = min(28, slot * 0.6)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Ações do hook por dia">']
    for k in range(5):
        yy = pad + inner_h * (1 - k / 4)
        out.append(f'<line class="grid" x1="{left}" x2="{w}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                   f'<text x="{left - 6}" y="{yy + 4:.1f}" text-anchor="end">{tick * k}</text>')
    for i, d in enumerate(days):
        cx = left + 4 + slot * i + (slot - bar) / 2
        base = pad + inner_h
        for a in ACTIONS:
            n = by_day[d].get(a, 0)
            if not n:
                continue
            seg = inner_h * n / top
            base -= seg
            out.append(f'<rect class="c-{a}" x="{cx:.1f}" y="{base:.1f}" width="{bar:.1f}" height="{seg:.1f}">'
                       f'<title>{_e(d)} · {a}: {n}</title></rect>')
        out.append(f'<text x="{cx + bar / 2:.1f}" y="{h - 8}" text-anchor="middle">{_e(d[8:10] + "/" + d[5:7])}</text>')
    out.append("</svg>")
    out.append('<div class="legend">' + "".join(
        f'<span><i class="b-{a}"></i>{ACTION_LABEL[a]}</span>' for a in ACTIONS) + "</div>")
    return "".join(out)


def _histogram_chart(s: dict) -> str:
    hist, timeout = s["latency"]["histogram"], s["latency"]["timeout_ms"]
    if not s["latency"]["n"]:
        return '<p class="empty"><b>Sem medições.</b>A distribuição aparece depois da primeira classificação.</p>'
    top = max(n for _, n in hist) or 1
    w, h, bottom, pad = 360, 170, 24, 14
    inner_h = h - bottom - pad
    slot = w / len(hist)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Distribuição de latência">']
    lower = 0
    for i, (upper, n) in enumerate(hist):
        over = upper is None or upper > timeout
        bh = inner_h * n / top
        bx = slot * i + 3
        label = f"≤{upper / 1000:g}s".replace(".", ",") if upper else f">{lower / 1000:g}s".replace(".", ",")
        out.append(f'<rect class="{"c-bar-over" if over else "c-bar"}" x="{bx:.1f}" y="{pad + inner_h - bh:.1f}" '
                   f'width="{slot - 6:.1f}" height="{max(bh, 1 if n else 0):.1f}" rx="2"><title>{_e(label)}: {n}</title></rect>')
        if n:
            out.append(f'<text x="{bx + (slot - 6) / 2:.1f}" y="{pad + inner_h - bh - 4:.1f}" text-anchor="middle">{n}</text>')
        out.append(f'<text x="{bx + (slot - 6) / 2:.1f}" y="{h - 6}" text-anchor="middle">{_e(label)}</text>')
        lower = upper or lower
    out.append("</svg>")
    out.append(f'<p class="note">Barras vermelhas ficam acima do timeout de {_e(_ms(timeout))}: '
               f'nessas o hook já desistiu e seguiu sem a dica.</p>')
    return "".join(out)


def _toplist(rows: list[tuple[str, int]], empty: str, help_text: dict | None = None, mono: bool = False,
             color=None) -> str:
    rows = [(k, n) for k, n in rows if n]
    if not rows:
        return f'<p class="empty">{empty}</p>'
    top = max(n for _, n in rows)
    total = sum(n for _, n in rows)
    items = []
    for key, n in rows:
        hint = f' <span class="hide-sm">· {_e(help_text[key])}</span>' if help_text and key in help_text else ""
        cls = "k mono" if mono else "k"
        fill = f' class="b-{color(key)}"' if color else ""
        items.append(f'<li><span class="{cls}" title="{_e(key)}">{_e(key)}{hint}</span>'
                     f'<span><span class="n">{n}</span> <span class="labels">{_pct(n, total)}</span></span>'
                     f'<span class="bar"><i{fill} style="width:{100 * n / top:.1f}%"></i></span></li>')
    return '<ul class="top-list">' + "".join(items) + "</ul>"


def _questions_table(s: dict) -> str:
    questions = s["questions"]
    if not questions:
        return ('<p class="empty"><b>Nenhuma pergunta respondida ainda.</b>Quando o hook classificar um prompt, cada '
                'pergunta de <code>schemas/hook.json</code> aparece aqui com sua confiança média.</p>')
    ordered = sorted(questions.items(), key=lambda kv: (kv[1]["mean_confidence"] is None, kv[1]["mean_confidence"] or 0))
    rows = []
    for qid, q in ordered:
        mean = q["mean_confidence"]
        color = "var(--bad)" if mean is not None and mean < .5 else ("var(--warn)" if mean is not None and mean < .75 else "var(--ok)")
        low_rate = q["low"] / q["n"] if q["n"] else 0
        low = f'<span class="tag lowc">{q["low"]} · {_pct(q["low"], q["n"])}</span>' if q["low"] else '<span class="tag">0</span>'
        labels = ", ".join(f"<b>{_e(label)}</b> {n}" for label, n in q["labels"][:3])
        rows.append(f'<tr><td class="mono qid">{_e(qid)}</td><td class="r n">{q["n"]}</td>'
                    f'<td><div class="conf"><span class="track"><i style="width:{100 * (mean or 0):.0f}%;background:{color}"></i>'
                    f'</span><span>{_conf(mean)}</span></div></td><td class="r" data-low="{low_rate:.2f}">{low}</td>'
                    f'<td class="labels lab">{labels}</td></tr>')
    fewest = min(q["n"] for q in questions.values())
    caveat = (f' Com no máximo {fewest} respostas por pergunta, as médias ainda oscilam muito.'
              if fewest < SMALL_SAMPLE else "")
    return ('<div class="scroll"><table class="reflow q"><thead><tr><th>Pergunta</th><th class="r">Respostas</th>'
            '<th>Confiança média</th><th class="r">Baixa confiança</th><th>Rótulos mais frequentes</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table></div><p class="note">Ordenadas da menor para a maior confiança: '
            f'as primeiras linhas são as candidatas a fine-tuning.{caveat}</p>')


def _training(s: dict) -> str:
    t = s["training"]
    facts = (f'<p class="facts"><span><b>{_int(t["with_low"])}</b>com alguma resposta incerta</span>'
             f'<span><b>{_pct(t["with_low"], t["classified"])}</b>dos rotulados</span>'
             '<span title="PRODUCT.md ainda não define quantos exemplos bastam para treinar">'
             '<b>?</b>volume mínimo: limiar a definir</span></p>')
    if not s["low_examples"]:
        body = ('<p class="empty"><b>Nenhum exemplo de baixa confiança.</b>Prompts em que alguma pergunta ficou abaixo '
                'do limiar do schema aparecem aqui, mascarados, para revisar antes de treinar.</p>')
    else:
        items = []
        for ex in s["low_examples"]:
            text = _e(ex["excerpt"]) if ex["excerpt"] else '<span class="labels">prompt não armazenado (store_prompt = false)</span>'
            tags = "".join(f'<span class="tag lowc">{_e(q)} → {_e(label)} {_conf(c)}</span>' for q, label, c in ex["low"])
            items.append(f'<li><q>{text}</q><div class="meta"><span>{_e(_when(ex["ts"]))}</span>{tags}</div></li>')
        body = '<ul class="samples">' + "".join(items) + "</ul>"
    return facts + body


def _recent(s: dict) -> str:
    if not s["recent"]:
        return ('<p class="empty"><b>O log está vazio.</b>Use o Claude Code com o hook ativo e gere o painel de novo com '
                '<code>uv run --script bin/laya_dashboard.py</code>.</p>')
    rows = []
    for r in s["recent"]:
        action = r["action"]
        excerpt_html = _e(r["excerpt"]) if r["excerpt"] else '<span class="labels">…</span>'
        rows.append(f'<tr><td class="mono" style="white-space:nowrap">{_e(_when(r["ts"]))}</td>'
                    f'<td><span class="tag"><i class="dot b-{_e(action)}"></i>{_e(action)}</span></td>'
                    f'<td class="r lat">{_e(_seconds(r["latency_ms"]) if r["latency_ms"] is not None else "-")}</td>'
                    f'<td>{_e(r["tier"] or "-")}</td><td class="ex"><div class="excerpt">{excerpt_html}</div></td></tr>')
    return ('<div class="scroll"><table class="reflow ev"><thead><tr><th>Quando (UTC)</th><th>Ação</th><th class="r">Latência</th>'
            '<th>Tier</th><th>Prompt (mascarado)</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def render(summary: dict, series: list[dict] | None = None) -> str:
    s = summary
    series = series if series is not None else s.get("series", [])
    by_day: dict[str, Counter] = {}
    for r in series:
        by_day.setdefault(r["ts"][:10], Counter())[r["action"]] += 1
    blocks_and_errors = _toplist(
        [(f"segredo: {k}", n) for k, n in s["secrets"]] + [(f"fail_open: {k}", n) for k, n in s["errors"]],
        "<b>Nada bloqueado e nenhuma falha.</b>Segredos colados e respostas fora do prazo aparecem aqui.", mono=True,
        color=lambda key: "block" if key.startswith("segredo") else "fail_open")
    period = (f'<span>De <b>{_e(_when(s["first"]))}</b> a <b>{_e(_when(s["last"]))}</b> UTC</span>'
              if s["first"] else "<span>Sem registros</span>")
    widgets = [
        _kpis(s),
        f'<section class="w s8" id="latencia"><h2>Latência por chamada <small>segundos, em ordem cronológica</small></h2>'
        f'{_latency_chart(s, series)}</section>',
        f'<section class="w s4"><h2>Ações por dia <small>chamadas, últimos 14 dias</small></h2>{_daily_chart(s, by_day)}</section>',
        f'<section class="w s4"><h2>Distribuição de latência</h2>{_histogram_chart(s)}</section>',
        f'<section class="w s4"><h2>Ações <small>total do período</small></h2>'
        f'{_toplist(s["actions"], "<b>Sem chamadas.</b>", ACTION_HELP, color=lambda key: key)}</section>',
        f'<div class="stack s4"><section class="w"><h2>Bloqueios e falhas</h2>{blocks_and_errors}</section>'
        f'<section class="w"><h2>Modelo sugerido <small>tier por prompt classificado</small></h2>'
        f'{_toplist(s["tiers"], "<b>Nenhuma sugestão ainda.</b>")}</section></div>',
        f'<section class="w s7" id="confianca"><h2>Confiança por pergunta <small>schema do hook</small></h2>'
        f'{_questions_table(s)}</section>',
        f'<section class="w s5" id="treino"><h2>Prontidão para fine-tuning</h2>{_training(s)}</section>',
        f'<section class="w s12" id="eventos"><h2>Últimas chamadas <small>{len(s["recent"])} mais recentes</small></h2>'
        f'{_recent(s)}</section>',
    ]
    bad = f'<span>{s["bad_lines"]} linhas ilegíveis ignoradas</span>' if s["bad_lines"] else ""
    return (
        '<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Laya · Desempenho do hook</title>'
        f'<link rel="icon" href="data:image/svg+xml,{quote(LOGO.replace("var(--accent)", "#7c5cff"))}">'
        f"<style>{CSS}</style></head><body>"
        f'<header class="top"><div class="brand">{LOGO}Laya Connector</div>'
        '<div class="crumb">Dashboards / <h1>Desempenho do hook</h1></div>'
        f'<div class="period">{period}<span>Gerado em <b>{_e(_when(s.get("generated")))}</b></span></div></header>'
        '<nav class="tabs" aria-label="Ir para a seção"><span>Ir para</span><a href="#latencia">Latência</a>'
        '<a href="#confianca">Confiança</a><a href="#treino">Fine-tuning</a><a href="#eventos">Últimas chamadas</a></nav>'
        "<main>" + "".join(widgets)
        + f'<footer class="foot"><span>Fonte: <code>.laya-connector/logs/*.jsonl</code></span>{bad}'
        '<span>Prompts mascarados e truncados; segredos nunca aparecem em claro.</span></footer>'
        "</main></body></html>\n"
    )


def main(root: Path, argv: list[str], say=print) -> int:
    parser = argparse.ArgumentParser(prog="laya_dashboard", description="Write the performance dashboard HTML.")
    parser.add_argument("--out", type=Path, help="output file (default: .laya-connector/dashboard.html)")
    parser.add_argument("--open", action="store_true", help="open the file in the default browser")
    args = parser.parse_args(argv)
    try:
        path = build(root, args.out)
    except (OSError, ValueError) as exc:
        say(f"[!!] dashboard: {exc}")
        return 1
    say(f"[ok] dashboard: {path}")
    if args.open:
        webbrowser.open(path.resolve().as_uri())
    return 0
