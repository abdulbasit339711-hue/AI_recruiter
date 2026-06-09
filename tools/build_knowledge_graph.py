#!/usr/bin/env python3
"""
Weighted dependency knowledge graph for the whole AI-Recruiter monorepo.

Builds a single directed graph across all subsystems:
  - Backend (app/)              Python
  - Voice agent (pipecat-...)   Python
  - Shared (packages/shared)    Python
  - Frontend (frontend/src)     TS/TSX

Edge weight = number of distinct import references from source module -> target module.
For each node we compute:
  fan_in    (how many modules depend on it)  -> blast radius / regression risk
  fan_out   (how many modules it depends on) -> coupling / fragility
  weight_in (sum of incoming edge weights)
  impact    (fan_in-driven regression-impact score, see below)

Outputs (written next to repo root under tools/graph_out/):
  knowledge_graph.json   full graph (nodes + weighted edges + metrics)
  knowledge_graph.mmd    Mermaid diagram of the highest-weight edges
  REGRESSION_MAP.md      human-readable "touch X -> retest these" report
"""
from __future__ import annotations
import ast
import json
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "graph_out"
OUT.mkdir(parents=True, exist_ok=True)

# ---- subsystem roots: (label, base_dir, kind) -----------------------------
PY_ROOTS = [
    ("backend", ROOT / "app", "app"),
    ("voice", ROOT / "pipecat-quickstart" / "server", None),
    ("shared", ROOT / "packages" / "shared", None),
]
FRONTEND_SRC = ROOT / "frontend" / "src"

EXCLUDE_DIRS = {".venv", "venv", "node_modules", "__pycache__", "alembic",
                ".next", ".git", "graph_out", "test_conversations"}


def subsystem_of(path: Path) -> str:
    p = str(path)
    if "/frontend/" in p:
        return "frontend"
    if "/pipecat-quickstart/" in p:
        return "voice"
    if "/packages/" in p:
        return "shared"
    if "/app/" in p:
        return "backend"
    return "other"


# =====================================================================
# PYTHON
# =====================================================================
def py_module_name(file: Path, base: Path, kind) -> str:
    """Map a .py file to its importable dotted module name."""
    rel = file.relative_to(base).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if kind == "app":            # imported as app.xxx
        return "app." + ".".join(parts) if parts else "app"
    # voice/shared: flat top-level modules (e.g. `from bot import ...`)
    return ".".join(parts) if parts else base.name


def collect_python():
    """Return (nodes set, name->node map of internal module names, file list)."""
    files = []
    name_to_node = {}     # importable name -> canonical node id
    for label, base, kind in PY_ROOTS:
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            if any(part in EXCLUDE_DIRS for part in f.parts):
                continue
            node = py_module_name(f, base, kind)
            files.append((f, base, kind, node))
            name_to_node[node] = node
            # also register the last segment for flat imports (voice/shared)
            if kind != "app":
                name_to_node.setdefault(node.split(".")[-1], node)
    return files, name_to_node


def py_imports(file: Path, base: Path, kind, name_to_node, edges):
    src_node = py_module_name(file, base, kind)
    try:
        tree = ast.parse(file.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return
    pkg_parts = py_module_name(file, base, kind).split(".")
    for n in ast.walk(tree):
        targets = []
        if isinstance(n, ast.Import):
            targets = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if n.level and n.level > 0:        # relative import
                anchor = pkg_parts[: len(pkg_parts) - n.level] if kind == "app" else []
                mod = ".".join([*anchor, mod]) if mod else ".".join(anchor)
            targets = [mod]
        for t in targets:
            if not t:
                continue
            # resolve to an internal node by longest-prefix match
            tgt = resolve_py(t, name_to_node)
            if tgt and tgt != src_node:
                edges[(src_node, tgt)] += 1


def resolve_py(name: str, name_to_node) -> str | None:
    if name in name_to_node:
        return name_to_node[name]
    # longest dotted-prefix match (app.scoring.engine -> app.scoring.engine)
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in name_to_node:
            return name_to_node[cand]
    # flat top segment (e.g. `bot`, `runner`)
    if parts[0] in name_to_node:
        return name_to_node[parts[0]]
    return None


# =====================================================================
# FRONTEND (TS/TSX)  — regex import scanner, alias-aware
# =====================================================================
IMPORT_RE = re.compile(
    r"""(?:import[^'"]*?from\s*|import\s*|require\(\s*|export[^'"]*?from\s*)['"]([^'"]+)['"]""",
)


def fe_node_id(file: Path) -> str:
    rel = file.relative_to(FRONTEND_SRC)
    return "fe:" + str(rel).replace("\\", "/")


def fe_resolve(spec: str, file: Path, fe_files: set[Path]) -> Path | None:
    if spec.startswith("@/"):
        base = FRONTEND_SRC / spec[2:]
    elif spec.startswith("."):
        base = (file.parent / spec).resolve()
    else:
        return None  # external package
    cands = [base]
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        cands.append(base.with_suffix(ext))
        cands.append(base.parent / (base.name + ext))
    for idx in ("index.ts", "index.tsx", "index.js", "index.jsx"):
        cands.append(base / idx)
    for c in cands:
        try:
            c = c.resolve()
        except OSError:
            continue
        if c in fe_files:
            return c
    return None


def collect_frontend(edges, nodes_meta):
    if not FRONTEND_SRC.exists():
        return
    fe_files = set()
    for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
        for f in FRONTEND_SRC.rglob(ext):
            if any(p in EXCLUDE_DIRS for p in f.parts):
                continue
            if f.name.endswith(".d.ts"):
                continue
            fe_files.add(f.resolve())
    for f in fe_files:
        src = fe_node_id(f)
        nodes_meta[src] = "frontend"
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in IMPORT_RE.finditer(text):
            tgt_path = fe_resolve(m.group(1), f, fe_files)
            if tgt_path:
                tgt = fe_node_id(tgt_path)
                if tgt != src:
                    edges[(src, tgt)] += 1


# =====================================================================
# BUILD
# =====================================================================
def main():
    edges = defaultdict(int)
    nodes_meta = {}  # node -> subsystem

    py_files, name_to_node = collect_python()
    for node in name_to_node.values():
        pass
    for f, base, kind, node in py_files:
        nodes_meta[node] = subsystem_of(f)
        py_imports(f, base, kind, name_to_node, edges)

    collect_frontend(edges, nodes_meta)

    # metrics
    fan_in = defaultdict(int)
    fan_out = defaultdict(int)
    weight_in = defaultdict(int)
    weight_out = defaultdict(int)
    for (s, t), w in edges.items():
        fan_out[s] += 1
        fan_in[t] += 1
        weight_out[s] += w
        weight_in[t] += w
        nodes_meta.setdefault(s, subsystem_of(Path(s)))
        nodes_meta.setdefault(t, "external")

    all_nodes = sorted(nodes_meta)
    nodes = []
    for n in all_nodes:
        impact = fan_in[n] * 2 + weight_in[n]  # blast radius, weighted
        nodes.append({
            "id": n,
            "subsystem": nodes_meta[n],
            "fan_in": fan_in[n],
            "fan_out": fan_out[n],
            "weight_in": weight_in[n],
            "weight_out": weight_out[n],
            "impact": impact,
        })

    edge_list = [{"source": s, "target": t, "weight": w}
                 for (s, t), w in sorted(edges.items(), key=lambda kv: -kv[1])]

    graph = {
        "meta": {
            "nodes": len(nodes),
            "edges": len(edge_list),
            "subsystems": dict(_count_by(nodes_meta)),
        },
        "nodes": nodes,
        "edges": edge_list,
    }
    (OUT / "knowledge_graph.json").write_text(json.dumps(graph, indent=2))

    write_mermaid(edge_list, nodes_meta)
    write_regression_map(nodes, edges)

    print(f"nodes={len(nodes)} edges={len(edge_list)}")
    print("subsystems:", dict(_count_by(nodes_meta)))
    print("\nTOP REGRESSION-RISK NODES (high blast radius):")
    for nd in sorted(nodes, key=lambda x: -x["impact"])[:15]:
        print(f"  {nd['impact']:>4}  {nd['subsystem']:<9} {nd['id']}"
              f"  (used by {nd['fan_in']}, refs {nd['weight_in']})")
    print(f"\nArtifacts written to {OUT}/")


def _count_by(meta):
    c = defaultdict(int)
    for v in meta.values():
        c[v] += 1
    return c


def write_mermaid(edge_list, meta, top=40):
    color = {"backend": "#cde", "voice": "#fcd", "frontend": "#dfc",
             "shared": "#ffd", "external": "#eee", "other": "#eee"}
    lines = ["graph LR"]
    seen = set()

    def nid(x):
        return "N" + str(abs(hash(x)) % (10 ** 9))

    for e in edge_list[:top]:
        s, t, w = e["source"], e["target"], e["weight"]
        for x in (s, t):
            if x not in seen:
                seen.add(x)
                lines.append(f'  {nid(x)}["{x}"]')
        lines.append(f"  {nid(s)} -->|{w}| {nid(t)}")
    for x in seen:
        lines.append(f"  style {nid(x)} fill:{color.get(meta.get(x,'other'),'#eee')}")
    (OUT / "knowledge_graph.mmd").write_text("\n".join(lines))


def write_regression_map(nodes, edges, top=20):
    rev = defaultdict(list)
    for (s, t), w in edges.items():
        rev[t].append((s, w))
    lines = ["# Regression Impact Map",
             "",
             "_Weighted dependency graph of the whole monorepo. \"Impact\" = "
             "blast radius if this module changes (fan-in × 2 + incoming refs)._",
             "",
             "## Highest blast-radius modules — change these, retest dependents",
             ""]
    for nd in sorted(nodes, key=lambda x: -x["impact"])[:top]:
        if nd["fan_in"] == 0:
            continue
        deps = sorted(rev[nd["id"]], key=lambda x: -x[1])
        dep_str = ", ".join(f"`{s}`×{w}" for s, w in deps[:12])
        more = "" if len(deps) <= 12 else f" …(+{len(deps)-12} more)"
        lines.append(f"### `{nd['id']}`  ({nd['subsystem']}, impact {nd['impact']})")
        lines.append(f"- Depended on by **{nd['fan_in']}** modules ({nd['weight_in']} refs):")
        lines.append(f"  {dep_str}{more}")
        lines.append("")
    (OUT / "REGRESSION_MAP.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
