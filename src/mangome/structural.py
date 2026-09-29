from __future__ import annotations

import ast
import hashlib
import math
import os
import re
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:  # Optional at source-tree test time; installed for the packaged v0.3.11 runtime.
    from tree_sitter import Parser as TreeSitterParser
    from tree_sitter_language_pack import get_language as get_tree_sitter_language
except Exception:  # pragma: no cover - graceful degradation is the contract.
    TreeSitterParser = None  # type: ignore[assignment]
    get_tree_sitter_language = None  # type: ignore[assignment]

STRUCTURAL_PROTOCOL = "SIM/1"
DEFAULT_MAX_FILES = 512
DEFAULT_MAX_FILE_BYTES = 512 * 1024
DEFAULT_MAX_RESULTS = 24
DEFAULT_MAX_PROJECTION_CHARS = 12000
DEFAULT_MAX_IMPACT_DEPTH = 4
DEFAULT_MAX_IMPACT_NODES = 64

_EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "__pycache__", "node_modules", "vendor", ".venv", "venv", "dist", "build",
}
_TEXT_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts",
    ".go", ".rs", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".cs", ".php",
    ".rb", ".sh", ".sql", ".toml", ".yaml", ".yml", ".json", ".md", ".txt",
}
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_./:-]*")
_GENERIC_SYMBOL = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|interface|type|struct|enum|fn)\s+([A-Za-z_][A-Za-z0-9_]*)"
)
_TREE_SITTER_LANGUAGES = {
    ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "tsx",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".go": "go", ".rs": "rust",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".cs": "c_sharp", ".php": "php", ".rb": "ruby", ".sh": "bash", ".sql": "sql",
}
_TREE_SITTER_DEFINITION_TYPES = {
    "function_definition", "function_declaration", "method_definition", "method_declaration",
    "class_definition", "class_declaration", "interface_declaration", "type_alias_declaration",
    "struct_item", "enum_item", "function_item", "impl_item", "method_declaration",
}
_TREE_SITTER_IMPORT_TYPES = {
    "import_statement", "import_declaration", "use_declaration", "use_item", "require_expression",
}
_GENERIC_IMPORT = re.compile(
    r"^\s*(?:from\s+([A-Za-z0-9_./-]+)\s+import|import\s+(?:type\s+)?(?:.*?\s+from\s+)?[\"']?([A-Za-z0-9_./-]+))"
)


@dataclass(frozen=True)
class StructuralNode:
    node_id: str
    kind: str
    name: str
    path: str
    line: int | None = None
    qualified_name: str | None = None
    language: str | None = None
    confidence: float = 1.0
    status: str = "EXACT"
    provenance: str = "LOCAL_WORKSPACE"


@dataclass(frozen=True)
class StructuralRelation:
    source_id: str
    relation: str
    target_id: str
    confidence: float = 1.0
    status: str = "EXACT"
    provenance: str = "LOCAL_WORKSPACE"


@dataclass(frozen=True)
class StructuralRevision:
    workspace_root: str
    revision_id: str
    files_seen: int
    files_indexed: int
    files_skipped: int
    partial: bool


@dataclass
class StructuralObservation:
    revision: StructuralRevision
    nodes: list[StructuralNode] = field(default_factory=list)
    relations: list[StructuralRelation] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class StructuralProjection:
    protocol: str
    status: str
    workspace_root: str
    revision_id: str | None
    query: str | None
    items: list[dict[str, Any]]
    omitted: int
    bounded: bool
    rule: str = "MAP_IS_DERIVED_OBSERVATION_NOT_TRUTH_AUTHORITY_EVIDENCE_OR_ASSURANCE"


@dataclass
class _FileRecord:
    signature: tuple[int, int]
    nodes: list[StructuralNode]
    imports: set[str]
    tokens: Counter[str]
    partial: bool = False


@dataclass
class _WorkspaceCache:
    root: Path
    files: dict[str, _FileRecord] = field(default_factory=dict)
    observation: StructuralObservation | None = None
    generation: int = 0


class StructuralIntelligence:
    """Bounded, lazy structural observation over a workspace.

    Design lineage follows the useful RepoMap ideas from Aider: definitions/references,
    a file dependency graph, task-conditioned ranking, centrality and bounded rendering.
    MangoMe does not absorb Aider as an application and this module performs no LLM calls.

    The index is process-local, incremental and derived. Construction/status never scans.
    Explicit search/context/impact operations may refresh the index lazily.
    """

    _caches: dict[str, _WorkspaceCache] = {}

    def __init__(
        self,
        workspace_root: str | os.PathLike[str] | None = None,
        *,
        max_files: int = DEFAULT_MAX_FILES,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> None:
        root = Path(workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
        self.root = root.expanduser().resolve()
        self.max_files = max(1, int(max_files))
        self.max_file_bytes = max(1024, int(max_file_bytes))

    @classmethod
    def reset_cache_for_tests(cls) -> None:
        cls._caches.clear()

    def structural_status(self) -> dict[str, Any]:
        cache = self._caches.get(str(self.root))
        if cache is None or cache.observation is None:
            return {
                "protocol": STRUCTURAL_PROTOCOL,
                "status": "UNINDEXED",
                "workspace_root": str(self.root),
                "revision_id": None,
                "files_indexed": 0,
                "scan_performed": False,
                "canonical_mutations": 0,
                "rule": "BOOTSTRAP_PERFORMS_NO_FULL_STRUCTURAL_SCAN",
            }
        obs = cache.observation
        return {
            "protocol": STRUCTURAL_PROTOCOL,
            "status": "PARTIAL" if obs.revision.partial else "EXACT",
            "workspace_root": str(self.root),
            "revision_id": obs.revision.revision_id,
            "files_seen": obs.revision.files_seen,
            "files_indexed": obs.revision.files_indexed,
            "files_skipped": obs.revision.files_skipped,
            "generation": cache.generation,
            "scan_performed": False,
            "canonical_mutations": 0,
            "rule": "MAP_IS_DERIVED_OBSERVATION_NOT_TRUTH_AUTHORITY_EVIDENCE_OR_ASSURANCE",
        }

    def _iter_candidates(self) -> Iterable[Path]:
        seen = 0
        for current, dirs, files in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d not in _EXCLUDED_DIRS and not d.startswith(".tox"))
            for name in sorted(files):
                path = Path(current) / name
                if path.suffix.lower() not in _TEXT_SUFFIXES:
                    continue
                seen += 1
                if seen > self.max_files:
                    return
                yield path

    def _signature(self, path: Path) -> tuple[int, int]:
        stat = path.stat()
        return int(stat.st_mtime_ns), int(stat.st_size)

    @staticmethod
    def _language(path: Path) -> str:
        suffix = path.suffix.lower().lstrip(".")
        return suffix or "text"

    @staticmethod
    def _tokenize(value: str) -> Counter[str]:
        return Counter(t.lower() for t in _WORD.findall(value))

    def _parse_python(self, rel: str, text: str) -> tuple[list[StructuralNode], set[str], Counter[str]]:
        nodes: list[StructuralNode] = []
        imports: set[str] = set()
        tokens = self._tokenize(text)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return self._parse_generic(rel, text, language="py", status="PARTIAL")

        file_id = f"file:{rel}"
        nodes.append(StructuralNode(file_id, "FILE", rel, rel, language="py"))

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.stack: list[str] = []

            def _add(self, kind: str, node: ast.AST, name: str) -> None:
                qual = ".".join([*self.stack, name]) if self.stack else name
                nodes.append(
                    StructuralNode(
                        node_id=f"symbol:{rel}:{qual}:{getattr(node, 'lineno', 0)}",
                        kind=kind,
                        name=name,
                        path=rel,
                        line=getattr(node, "lineno", None),
                        qualified_name=qual,
                        language="py",
                    )
                )

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._add("CLASS", node, node.name)
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._add("FUNCTION", node, node.name)
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Import(self, node: ast.Import) -> None:
                for alias in node.names:
                    imports.add(alias.name)
                self.generic_visit(node)

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if node.module:
                    imports.add(node.module)
                self.generic_visit(node)

        Visitor().visit(tree)
        return nodes, imports, tokens


    def _parse_tree_sitter(
        self, rel: str, text: str
    ) -> tuple[list[StructuralNode], set[str], Counter[str], bool] | None:
        suffix = Path(rel).suffix.lower()
        language_name = _TREE_SITTER_LANGUAGES.get(suffix)
        if not language_name or TreeSitterParser is None or get_tree_sitter_language is None:
            return None
        try:
            language = get_tree_sitter_language(language_name)
            parser = TreeSitterParser(language)
            tree = parser.parse(text.encode("utf-8"))
        except Exception:
            return None

        root = tree.root_node
        partial = bool(getattr(root, "has_error", False))
        status = "PARTIAL" if partial else "EXACT"
        lang = language_name
        nodes: list[StructuralNode] = [
            StructuralNode(
                f"file:{rel}", "FILE", rel, rel, language=lang,
                status=status, provenance="TREE_SITTER", confidence=0.98 if not partial else 0.86,
            )
        ]
        imports: set[str] = set()
        source = text.encode("utf-8")
        stack = [root]
        visited = 0
        max_nodes = 20000
        while stack and visited < max_nodes:
            node = stack.pop()
            visited += 1
            ntype = str(getattr(node, "type", ""))
            if ntype in _TREE_SITTER_DEFINITION_TYPES:
                name_node = None
                try:
                    name_node = node.child_by_field_name("name")
                except Exception:
                    name_node = None
                if name_node is not None:
                    try:
                        raw_name = source[name_node.start_byte:name_node.end_byte].decode("utf-8", "replace").strip()
                    except Exception:
                        raw_name = ""
                    if raw_name and len(raw_name) <= 160:
                        line = int(getattr(node, "start_point", (0, 0))[0]) + 1
                        kind = "CLASS" if "class" in ntype or "interface" in ntype else "SYMBOL"
                        nodes.append(
                            StructuralNode(
                                f"symbol:{rel}:{raw_name}:{line}", kind, raw_name, rel,
                                line=line, qualified_name=raw_name, language=lang,
                                confidence=0.96 if not partial else 0.84, status=status, provenance="TREE_SITTER",
                            )
                        )
            if ntype in _TREE_SITTER_IMPORT_TYPES:
                try:
                    raw = source[node.start_byte:node.end_byte].decode("utf-8", "replace")
                except Exception:
                    raw = ""
                match = _GENERIC_IMPORT.match(raw)
                if match:
                    target = match.group(1) or match.group(2)
                    if target:
                        imports.add(target)
            try:
                children = list(node.children)
            except Exception:
                children = []
            stack.extend(reversed(children))

        # Retain the lightweight import regex as a language-neutral dependency hint.
        for line in text.splitlines():
            match = _GENERIC_IMPORT.match(line)
            if match:
                target = match.group(1) or match.group(2)
                if target:
                    imports.add(target)
        return nodes, imports, self._tokenize(text), partial or visited >= max_nodes

    def _parse_generic(
        self, rel: str, text: str, *, language: str | None = None, status: str = "PARTIAL"
    ) -> tuple[list[StructuralNode], set[str], Counter[str]]:
        lang = language or Path(rel).suffix.lower().lstrip(".") or "text"
        nodes = [StructuralNode(f"file:{rel}", "FILE", rel, rel, language=lang, status=status)]
        imports: set[str] = set()
        for line_no, line in enumerate(text.splitlines(), start=1):
            sm = _GENERIC_SYMBOL.match(line)
            if sm:
                name = sm.group(1)
                nodes.append(
                    StructuralNode(
                        f"symbol:{rel}:{name}:{line_no}", "SYMBOL", name, rel,
                        line=line_no, qualified_name=name, language=lang,
                        confidence=0.72, status=status, provenance="BOUNDED_TEXT_FALLBACK",
                    )
                )
            im = _GENERIC_IMPORT.match(line)
            if im:
                target = im.group(1) or im.group(2)
                if target:
                    imports.add(target)
        return nodes, imports, self._tokenize(text)

    @staticmethod
    def _module_candidates(rel: str) -> set[str]:
        p = Path(rel)
        no_suffix = str(p.with_suffix("")).replace(os.sep, "/")
        dotted = no_suffix.replace("/", ".")
        candidates = {no_suffix, dotted, p.stem}
        if dotted.endswith(".__init__"):
            candidates.add(dotted[: -len(".__init__")])
        if dotted.startswith("src."):
            candidates.add(dotted[4:])
        return {c for c in candidates if c}

    def _refresh(self) -> StructuralObservation:
        key = str(self.root)
        cache = self._caches.setdefault(key, _WorkspaceCache(root=self.root))
        discovered: dict[str, Path] = {}
        files_seen = 0
        files_skipped = 0
        errors: list[dict[str, Any]] = []

        if not self.root.exists() or not self.root.is_dir():
            raise FileNotFoundError(f"workspace root does not exist: {self.root}")

        for path in self._iter_candidates():
            files_seen += 1
            rel = path.relative_to(self.root).as_posix()
            discovered[rel] = path
            try:
                sig = self._signature(path)
            except OSError as exc:
                files_skipped += 1
                errors.append({"path": rel, "code": type(exc).__name__})
                continue
            old = cache.files.get(rel)
            if old is not None and old.signature == sig:
                continue
            if sig[1] > self.max_file_bytes:
                files_skipped += 1
                cache.files.pop(rel, None)
                errors.append({"path": rel, "code": "FILE_TOO_LARGE"})
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                parser_partial = False
                if path.suffix.lower() in {".py", ".pyi"}:
                    nodes, imports, tokens = self._parse_python(rel, text)
                else:
                    parsed = self._parse_tree_sitter(rel, text)
                    if parsed is None:
                        nodes, imports, tokens = self._parse_generic(rel, text)
                        parser_partial = True
                    else:
                        nodes, imports, tokens, parser_partial = parsed
                cache.files[rel] = _FileRecord(sig, nodes, imports, tokens, partial=parser_partial)
            except OSError as exc:
                files_skipped += 1
                cache.files.pop(rel, None)
                errors.append({"path": rel, "code": type(exc).__name__})

        for rel in list(cache.files):
            if rel not in discovered:
                del cache.files[rel]

        module_to_file: dict[str, str] = {}
        for rel in cache.files:
            for candidate in self._module_candidates(rel):
                module_to_file.setdefault(candidate, rel)

        nodes: list[StructuralNode] = []
        relations: list[StructuralRelation] = []
        for rel, record in cache.files.items():
            nodes.extend(record.nodes)
            source = f"file:{rel}"
            for imported in sorted(record.imports):
                target_rel = module_to_file.get(imported)
                if target_rel is None:
                    parts = imported.split(".")
                    while len(parts) > 1 and target_rel is None:
                        parts.pop()
                        target_rel = module_to_file.get(".".join(parts))
                if target_rel and target_rel != rel:
                    relations.append(
                        StructuralRelation(source, "IMPORTS", f"file:{target_rel}", confidence=0.95)
                    )

        revision_seed = "\n".join(
            f"{rel}:{rec.signature[0]}:{rec.signature[1]}" for rel, rec in sorted(cache.files.items())
        )
        revision_id = hashlib.sha256(revision_seed.encode("utf-8")).hexdigest()[:20]
        partial = (
            bool(errors)
            or files_seen >= self.max_files
            or any(record.partial for record in cache.files.values())
            or any(node.status == "PARTIAL" for record in cache.files.values() for node in record.nodes)
        )
        revision = StructuralRevision(
            workspace_root=key,
            revision_id=revision_id,
            files_seen=files_seen,
            files_indexed=len(cache.files),
            files_skipped=files_skipped,
            partial=partial,
        )
        obs = StructuralObservation(revision, nodes, relations, errors)
        cache.observation = obs
        cache.generation += 1
        return obs

    def _observation(self, *, refresh: bool = True) -> StructuralObservation:
        cache = self._caches.get(str(self.root))
        if refresh or cache is None or cache.observation is None:
            return self._refresh()
        return cache.observation

    @staticmethod
    def _file_graph(obs: StructuralObservation) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        outgoing: dict[str, set[str]] = defaultdict(set)
        incoming: dict[str, set[str]] = defaultdict(set)
        for rel in obs.relations:
            if rel.source_id.startswith("file:") and rel.target_id.startswith("file:"):
                outgoing[rel.source_id].add(rel.target_id)
                incoming[rel.target_id].add(rel.source_id)
        return outgoing, incoming

    @staticmethod
    def _centrality(obs: StructuralObservation) -> dict[str, float]:
        files = [n.node_id for n in obs.nodes if n.kind == "FILE"]
        if not files:
            return {}
        outgoing, _ = StructuralIntelligence._file_graph(obs)
        scores = {f: 1.0 / len(files) for f in files}
        damping = 0.85
        for _ in range(12):
            next_scores = {f: (1.0 - damping) / len(files) for f in files}
            dangling = sum(scores[f] for f in files if not outgoing.get(f))
            dangling_share = damping * dangling / len(files)
            for f in files:
                next_scores[f] += dangling_share
            for source, targets in outgoing.items():
                if not targets:
                    continue
                share = damping * scores.get(source, 0.0) / len(targets)
                for target in targets:
                    if target in next_scores:
                        next_scores[target] += share
            scores = next_scores
        peak = max(scores.values(), default=1.0) or 1.0
        return {k: v / peak for k, v in scores.items()}

    def structural_search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_MAX_RESULTS,
        refresh: bool = True,
    ) -> dict[str, Any]:
        obs = self._observation(refresh=refresh)
        query_tokens = self._tokenize(query)
        centrality = self._centrality(obs)
        cache = self._caches[str(self.root)]
        scored: list[tuple[float, StructuralNode]] = []

        for node in obs.nodes:
            record = cache.files.get(node.path)
            lexical = 0.0
            hay = f"{node.name} {node.qualified_name or ''} {node.path}".lower()
            for token, count in query_tokens.items():
                if token in hay:
                    lexical += 2.0 * count
                elif record and token in record.tokens:
                    lexical += min(1.0, 0.12 * record.tokens[token]) * count
            if not query_tokens:
                lexical = 0.1
            file_score = centrality.get(f"file:{node.path}", 0.0)
            kind_boost = 0.30 if node.kind != "FILE" else 0.0
            score = lexical + 0.55 * file_score + kind_boost + 0.25 * node.confidence
            if score > 0.25:
                scored.append((score, node))

        scored.sort(key=lambda item: (-item[0], item[1].path, item[1].line or 0, item[1].name))
        items = []
        for score, node in scored[: max(1, int(limit))]:
            item = asdict(node)
            item["score"] = round(score, 5)
            item["revision_id"] = obs.revision.revision_id
            items.append(item)
        return {
            "protocol": STRUCTURAL_PROTOCOL,
            "status": "PARTIAL" if obs.revision.partial else "EXACT",
            "workspace_root": str(self.root),
            "revision_id": obs.revision.revision_id,
            "query": query,
            "results": items,
            "bounded": len(scored) > len(items),
            "canonical_mutations": 0,
        }

    def symbol_lookup(self, symbol: str, *, limit: int = 16) -> dict[str, Any]:
        obs = self._observation(refresh=True)
        needle = symbol.lower().strip()
        matches = [
            n for n in obs.nodes
            if n.kind != "FILE" and (n.name.lower() == needle or needle in (n.qualified_name or "").lower())
        ]
        matches.sort(key=lambda n: (n.name.lower() != needle, n.path, n.line or 0))
        return {
            "protocol": STRUCTURAL_PROTOCOL,
            "status": "PARTIAL" if obs.revision.partial else ("EXACT" if matches else "UNKNOWN"),
            "revision_id": obs.revision.revision_id,
            "symbol": symbol,
            "matches": [asdict(x) for x in matches[: max(1, limit)]],
            "canonical_mutations": 0,
        }

    def symbol_relations(self, symbol: str, *, depth: int = 1, max_nodes: int = 32) -> dict[str, Any]:
        lookup = self.symbol_lookup(symbol, limit=8)
        paths = {m["path"] for m in lookup.get("matches") or []}
        obs = self._observation(refresh=False)
        start = {f"file:{p}" for p in paths}
        outgoing, incoming = self._file_graph(obs)
        visited = set(start)
        q = deque((node, 0) for node in start)
        rels: list[dict[str, Any]] = []
        while q and len(visited) < max(1, max_nodes):
            node, level = q.popleft()
            if level >= max(0, depth):
                continue
            for relation, neighbors in (("DEPENDS_ON", outgoing.get(node, set())), ("DEPENDENT", incoming.get(node, set()))):
                for neighbor in sorted(neighbors):
                    rels.append({"source": node, "relation": relation, "target": neighbor, "depth": level + 1})
                    if neighbor not in visited and len(visited) < max_nodes:
                        visited.add(neighbor)
                        q.append((neighbor, level + 1))
        return {
            "protocol": STRUCTURAL_PROTOCOL,
            "status": lookup.get("status", "UNKNOWN"),
            "revision_id": obs.revision.revision_id,
            "symbol": symbol,
            "relations": rels,
            "bounded": bool(q),
            "canonical_mutations": 0,
        }

    def structural_context(
        self,
        query: str,
        *,
        max_chars: int = DEFAULT_MAX_PROJECTION_CHARS,
        max_items: int = DEFAULT_MAX_RESULTS,
    ) -> dict[str, Any]:
        search = self.structural_search(query, limit=max_items, refresh=True)
        items: list[dict[str, Any]] = []
        used = 0
        omitted = 0
        for item in search["results"]:
            compact = {
                key: item.get(key)
                for key in ("kind", "name", "qualified_name", "path", "line", "confidence", "status", "provenance", "score")
                if item.get(key) is not None
            }
            size = len(str(compact))
            if used + size > max(256, int(max_chars)):
                omitted += 1
                continue
            items.append(compact)
            used += size
        projection = StructuralProjection(
            protocol=STRUCTURAL_PROTOCOL,
            status=search["status"],
            workspace_root=str(self.root),
            revision_id=search["revision_id"],
            query=query,
            items=items,
            omitted=omitted,
            bounded=bool(search.get("bounded") or omitted),
        )
        return asdict(projection)

    def impact_frontier(
        self,
        target: str,
        *,
        max_depth: int = DEFAULT_MAX_IMPACT_DEPTH,
        max_nodes: int = DEFAULT_MAX_IMPACT_NODES,
        max_files: int = 32,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        obs = self._observation(refresh=True)
        outgoing, incoming = self._file_graph(obs)
        target_path = target.replace("\\", "/")
        starts: set[str] = set()
        if target_path in self._caches[str(self.root)].files:
            starts.add(f"file:{target_path}")
        for n in obs.nodes:
            if n.kind != "FILE" and (n.name == target or n.qualified_name == target):
                starts.add(f"file:{n.path}")
        if not starts:
            search = self.structural_search(target, limit=4, refresh=False)
            starts.update(f"file:{x['path']}" for x in search.get("results") or [])

        visited = set(starts)
        q = deque((s, 0) for s in sorted(starts))
        rows: list[dict[str, Any]] = []
        while q and len(visited) <= max(1, int(max_nodes)):
            node, depth = q.popleft()
            if depth >= max(0, int(max_depth)):
                continue
            neighbors = sorted(incoming.get(node, set()) | outgoing.get(node, set()))
            for neighbor in neighbors:
                if 1.0 < min_confidence:
                    continue
                relation = "DEPENDENT" if neighbor in incoming.get(node, set()) else "DEPENDENCY"
                rows.append({
                    "source": node.removeprefix("file:"),
                    "relation": relation,
                    "target": neighbor.removeprefix("file:"),
                    "depth": depth + 1,
                    "confidence": 1.0,
                    "status": "EXACT",
                })
                if neighbor not in visited and len(visited) < max_nodes:
                    visited.add(neighbor)
                    q.append((neighbor, depth + 1))

        files = sorted({x.removeprefix("file:") for x in visited})[: max(1, int(max_files))]
        return {
            "protocol": STRUCTURAL_PROTOCOL,
            "status": "UNKNOWN" if not starts else ("PARTIAL" if obs.revision.partial else "EXACT"),
            "workspace_root": str(self.root),
            "revision_id": obs.revision.revision_id,
            "target": target,
            "files": files,
            "relations": rows[: max(1, int(max_nodes))],
            "bounded": bool(q) or len(visited) > max_files,
            "mutation_scope_expanded": False,
            "canonical_mutations": 0,
            "rule": "IMPACT_FRONTIER_MAY_EXPAND_INSPECTION_NEVER_MUTATION_AUTHORITY",
        }


def unavailable_structural_context(workspace_root: str | None, exc: Exception) -> dict[str, Any]:
    return {
        "protocol": STRUCTURAL_PROTOCOL,
        "status": "STRUCTURAL_CONTEXT_UNAVAILABLE",
        "workspace_root": workspace_root,
        "reason_code": type(exc).__name__,
        "canonical_mutations": 0,
        "blocking": False,
        "rule": "FAIL_CLOSED_ON_TRUTH_EFFECT_MUTATION_DEGRADE_GRACEFULLY_ON_COGNITION",
    }
