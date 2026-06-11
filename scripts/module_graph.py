#!/usr/bin/env python3
"""Generate a weighted module-dependency graph for the AI-Recruiter monorepo.

Nodes are individual source files; a directed edge A -> B means "A imports from B",
and the edge weight is the number of names A imports from B (so `from x import a, b`
contributes 2, `import x` contributes 1, a TS `import { a, b }` contributes 2).

Only INTRA-project edges are kept — imports of third-party / stdlib packages are
ignored, since the point is to show how *our* modules relate.

Covers three Python roots and the TS frontend:
  - app/                          (package `app.*`)
  - voice-agent/server/    (top-level: `database`, `processors.x`, ...)
  - packages/shared/              (package `recruiter_shared.*`)
  - frontend/src/                 (relative imports + `@/` alias)

Output: MODULE_GRAPH.md at the repo root — a package-level overview plus a
per-subsystem, per-file Mermaid graph and dependency tables.

Run:  python scripts/module_graph.py   (no third-party deps; stdlib only)
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (label, root-dir-relative-to-repo, import-root). import_root is the directory that
# acts as the module search path; module names are computed relative to it.
PY_ROOTS = [
    ("app", REPO / "app", REPO),                       # imported as app.*
    ("voice", REPO / "voice-agent" / "server", REPO / "voice-agent" / "server"),
    ("shared", REPO / "packages" / "shared", REPO / "packages" / "shared"),
]
TS_ROOT = REPO / "frontend" / "src"

EXCLUDE_DIRS = {".venv", "venv", "__pycache__", "node_modules", ".next", ".git", "dist", "build"}

# Subsystem assignment for grouping (by repo-relative path prefix).
SUBSYSTEMS = [
    ("Backend API (app/)", "app/"),
    ("Voice agent (server/)", "voice-agent/server/"),
    ("Shared package", "packages/shared/"),
    ("Frontend (frontend/src/)", "frontend/src/"),
]


def _excluded(p: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in p.parts)


def rel(p: Path) -> str:
    return str(p.relative_to(REPO)).replace("\\", "/")


# ── Python: build module-name -> file maps, then resolve imports ───────────────

def _module_name(file: Path, import_root: Path) -> str:
    r = file.relative_to(import_root).with_suffix("")
    parts = list(r.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def build_python_index():
    """Return (files_by_root, module_to_file). module_to_file maps a dotted module
    name to its file Path (only for the roots above)."""
    files_by_root: dict[str, list[Path]] = defaultdict(list)
    module_to_file: dict[str, Path] = {}
    for label, root, import_root in PY_ROOTS:
        if not root.exists():
            continue
        for f in root.rglob("*.py"):
            if _excluded(f):
                continue
            files_by_root[label].append(f)
            mod = _module_name(f, import_root)
            if mod:
                module_to_file[mod] = f
    return files_by_root, module_to_file


def _resolve_py(mod: str, module_to_file: dict[str, Path]) -> Path | None:
    """Resolve a dotted module name to a project file, trying to strip a trailing
    symbol (e.g. `pkg.mod.Symbol` -> `pkg.mod`)."""
    if mod in module_to_file:
        return module_to_file[mod]
    if "." in mod:
        head = mod.rsplit(".", 1)[0]
        if head in module_to_file:
            return module_to_file[head]
    return None


def _relative_base(file: Path, import_root: Path, level: int) -> str:
    """Dotted package base for a relative import of given level, from `file`."""
    pkg = file.parent
    # each extra level beyond 1 climbs one more directory
    for _ in range(level - 1):
        pkg = pkg.parent
    try:
        parts = list(pkg.relative_to(import_root).parts)
    except ValueError:
        return ""
    return ".".join(parts)


def python_edges(files_by_root, module_to_file):
    """edges[(src_rel, dst_rel)] = summed weight."""
    edges: dict[tuple[str, str], int] = defaultdict(int)
    import_root_for = {label: ir for label, _root, ir in PY_ROOTS}
    for label, files in files_by_root.items():
        import_root = import_root_for[label]
        for f in files:
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            src = rel(f)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        tgt = _resolve_py(alias.name, module_to_file)
                        if tgt and rel(tgt) != src:
                            edges[(src, rel(tgt))] += 1
                elif isinstance(node, ast.ImportFrom):
                    weight = sum(1 for a in node.names)  # names imported = weight
                    if node.level and node.level > 0:
                        base = _relative_base(f, import_root, node.level)
                        mod = f"{base}.{node.module}" if node.module else base
                    else:
                        mod = node.module or ""
                    if not mod:
                        continue
                    tgt = _resolve_py(mod, module_to_file)
                    if tgt is None and node.module:
                        # maybe `from pkg import submodule` — try each name as a submodule
                        for a in node.names:
                            sub = _resolve_py(f"{mod}.{a.name}", module_to_file)
                            if sub and rel(sub) != src:
                                edges[(src, rel(sub))] += 1
                        continue
                    if tgt and rel(tgt) != src:
                        edges[(src, rel(tgt))] += weight
    return edges


# ── TypeScript / TSX: regex-parse imports, resolve relative + `@/` alias ───────

_TS_IMPORT_RE = re.compile(
    r"""(?:import|export)\s+(?P<clause>[^'"]*?)\s+from\s*['"](?P<path>[^'"]+)['"]"""
    r"""|import\s*['"](?P<bare>[^'"]+)['"]"""
    r"""|import\s*\(\s*['"](?P<dyn>[^'"]+)['"]\s*\)""",
    re.DOTALL,
)
_TS_EXTS = [".ts", ".tsx", ".js", ".jsx", ".d.ts"]


def _ts_files():
    if not TS_ROOT.exists():
        return []
    out = []
    for f in TS_ROOT.rglob("*"):
        if f.suffix in {".ts", ".tsx", ".js", ".jsx"} and not _excluded(f):
            out.append(f)
    return out


def _resolve_ts(spec: str, from_file: Path) -> Path | None:
    if spec.startswith("@/"):
        base = TS_ROOT / spec[2:]
    elif spec.startswith("."):
        base = (from_file.parent / spec).resolve()
    else:
        return None  # bare package import (node_modules) — external
    candidates = [base.with_suffix(base.suffix + ext) if base.suffix else base.with_suffix(ext) for ext in _TS_EXTS]
    candidates = [Path(str(base) + ext) for ext in _TS_EXTS] + [base / ("index" + ext) for ext in _TS_EXTS] + [base]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _ts_weight(clause: str) -> int:
    """Count imported bindings: default + namespace + each named binding."""
    if not clause:
        return 1
    clause = clause.strip().rstrip(",")
    weight = 0
    m = re.search(r"\{(?P<named>.*)\}", clause, re.DOTALL)
    if m:
        names = [n for n in re.split(r",", m.group("named")) if n.strip()]
        weight += len(names)
        before = clause[: m.start()].strip().rstrip(",").strip()
    else:
        before = clause
    # default and/or `* as ns` outside the braces
    for tok in before.split(","):
        tok = tok.strip()
        if tok and tok != "type":
            weight += 1
    return max(weight, 1)


def ts_edges():
    edges: dict[tuple[str, str], int] = defaultdict(int)
    for f in _ts_files():
        src = rel(f)
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in _TS_IMPORT_RE.finditer(text):
            spec = m.group("path") or m.group("bare") or m.group("dyn")
            if not spec:
                continue
            tgt = _resolve_ts(spec, f)
            if tgt and rel(tgt) != src:
                w = _ts_weight(m.group("clause") or "")
                edges[(src, rel(tgt))] += w
    return edges


# ── Rendering ──────────────────────────────────────────────────────────────────

def subsystem_of(path: str) -> str:
    for name, prefix in SUBSYSTEMS:
        if path.startswith(prefix):
            return name
    return "Other"


def short_label(path: str) -> str:
    """Trim the subsystem prefix for readability inside its own box."""
    for _name, prefix in SUBSYSTEMS:
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def _id(counter: dict, path: str) -> str:
    if path not in counter:
        counter[path] = f"n{len(counter)}"
    return counter[path]


def _san(label: str) -> str:
    """Escape characters Mermaid can't handle inside a node label, notably the
    square brackets in Next.js dynamic routes like `[jobId]`."""
    return (
        label.replace("[", "#91;")
        .replace("]", "#93;")
        .replace('"', "#quot;")
    )


def mermaid_for_paths(edges, paths_filter, node_ids, label_fn):
    """Render a Mermaid graph for edges whose SOURCE is in paths_filter."""
    lines = ["```mermaid", "graph LR"]
    # group nodes by subsystem into subgraphs
    nodes_used = set()
    sub_edges = []
    for (s, d), w in sorted(edges.items(), key=lambda kv: (-kv[1], kv[0])):
        if s in paths_filter:
            sub_edges.append((s, d, w))
            nodes_used.add(s)
            nodes_used.add(d)
    by_sub: dict[str, list[str]] = defaultdict(list)
    for p in nodes_used:
        by_sub[subsystem_of(p)].append(p)
    for sub, members in by_sub.items():
        safe = re.sub(r"[^A-Za-z0-9]", "_", sub)
        lines.append(f'  subgraph {safe}["{sub}"]')
        for p in sorted(members):
            lines.append(f'    {_id(node_ids, p)}["{_san(label_fn(p))}"]')
        lines.append("  end")
    for s, d, w in sub_edges:
        lines.append(f"  {_id(node_ids, s)} -->|{w}| {_id(node_ids, d)}")
    lines.append("```")
    return "\n".join(lines)


def package_overview(edges):
    """Aggregate file edges up to directory (package) level."""
    def pkg(path: str) -> str:
        d = str(Path(path).parent)
        return d if d != "." else path
    agg: dict[tuple[str, str], int] = defaultdict(int)
    for (s, d), w in edges.items():
        ps, pd = pkg(s), pkg(d)
        if ps != pd:
            agg[(ps, pd)] += w
    ids: dict[str, str] = {}
    lines = ["```mermaid", "graph LR"]
    nodes = set()
    for (s, d) in agg:
        nodes.add(s)
        nodes.add(d)
    by_sub: dict[str, list[str]] = defaultdict(list)
    for p in nodes:
        by_sub[subsystem_of(p + "/")].append(p)
    for sub, members in by_sub.items():
        safe = re.sub(r"[^A-Za-z0-9]", "_", sub)
        lines.append(f'  subgraph {safe}["{sub}"]')
        for p in sorted(members):
            lines.append(f'    {_id(ids, p)}["{_san(p)}"]')
        lines.append("  end")
    for (s, d), w in sorted(agg.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {_id(ids, s)} -->|{w}| {_id(ids, d)}")
    lines.append("```")
    return "\n".join(lines)


def tables(edges):
    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    for (s, d), w in edges.items():
        fan_out[s] += w
        fan_in[d] += w
    def tbl(title, data):
        rows = [f"### {title}", "", "| File | Weight |", "|---|---:|"]
        for path, w in sorted(data.items(), key=lambda kv: -kv[1])[:12]:
            rows.append(f"| `{path}` | {w} |")
        return "\n".join(rows)
    return tbl("Most depended-on (fan-in)", fan_in), tbl("Most dependencies (fan-out)", fan_out)


def main():
    files_by_root, module_to_file = build_python_index()
    edges: dict[tuple[str, str], int] = defaultdict(int)
    for k, v in python_edges(files_by_root, module_to_file).items():
        edges[k] += v
    for k, v in ts_edges().items():
        edges[k] += v

    node_ids: dict[str, str] = {}
    n_nodes = len({p for e in edges for p in e})
    fan_in_t, fan_out_t = tables(edges)

    out = [
        "# Module dependency graph",
        "",
        "_Auto-generated by `scripts/module_graph.py` — do not edit by hand; re-run to refresh._",
        "",
        "Nodes are source files. An edge **A → B** means *A imports from B*; the number on "
        "the edge is the **weight** = how many names A imports from B "
        "(`from x import a, b` = 2, `import x` = 1, TS `import { a, b }` = 2). "
        "Only intra-project imports are shown (third-party/stdlib omitted).",
        "",
        f"**{n_nodes} files** participate in **{len(edges)} weighted edges**.",
        "",
        "## 1. Package-level overview",
        "",
        "Edges aggregated to directory level (cross-package only).",
        "",
        package_overview(edges),
        "",
        "## 2. Per-subsystem detail (per file)",
        "",
        "Each graph shows edges originating in that subsystem (targets in other "
        "subsystems appear in their own box).",
        "",
    ]
    for name, prefix in SUBSYSTEMS:
        srcs = {p for e in edges for p in (e[0],) if p.startswith(prefix)}
        if not srcs:
            continue
        out.append(f"### {name}")
        out.append("")
        out.append(mermaid_for_paths(edges, srcs, node_ids, short_label))
        out.append("")
    out += ["## 3. Hotspots", "", fan_in_t, "", fan_out_t, ""]

    dest = REPO / "MODULE_GRAPH.md"
    dest.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {rel(dest)}: {n_nodes} nodes, {len(edges)} edges")


if __name__ == "__main__":
    main()
