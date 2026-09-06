"""Ferry AST Diff & Syntax Inspector.

Performs dry-run AST validation and semantic interface diffing before file writes
are committed to the filesystem.

Key capabilities:
1. Dry-Run Syntax Validation: Catches SyntaxError / IndentationError in Python code
   before touching disk, returning actionable error payloads to the agent.
2. Semantic Symbol Extraction: Parses top-level and class-level functions, classes,
   and type annotations to extract public contract signatures.
3. Interface Diffing: Distinguishes between breaking interface modifications
   (signature changes, removed exports) vs. harmless internal body edits.
"""

import ast
import difflib
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

try:
    from packages.fullerence.types import ASTDiff, ASTDiffType
except Exception:
    class ASTDiffType(str, Enum):
        SIGNATURE_CHANGED = "signature_changed"
        ADDED_EXPORT = "added_export"
        DELETED_EXPORT = "deleted_export"
        BODY_CHANGED = "body_changed"

    class ASTDiff(BaseModel):
        id: str
        causal_node_id: str
        file_path: str
        diff_type: ASTDiffType
        symbol_id: str
        before_signature: Optional[str] = None
        after_signature: Optional[str] = None
        raw_diff: Optional[str] = None
        created_at: int = Field(default_factory=lambda: int(time.time()))


class SyntaxValidationResult(BaseModel):
    is_valid: bool
    error_message: Optional[str] = None
    line_number: Optional[int] = None
    column_offset: Optional[int] = None


class SymbolSignature(BaseModel):
    symbol_id: str           # e.g., "func:login", "class:AuthService.method:verify"
    name: str
    kind: str                # "function", "async_function", "class"
    signature: str           # e.g., "def login(user: str, token: str) -> bool"
    docstring: Optional[str] = None
    line_start: int
    line_end: int


class ASTInspector:
    """Inspector for AST syntax validation and semantic interface diffing."""

    # -------------------------------------------------------------
    # 1. Dry-Run Syntax Validation
    # -------------------------------------------------------------
    @staticmethod
    def validate_syntax(code: str, file_path: str = "") -> SyntaxValidationResult:
        """Validates that code parses cleanly without syntax errors.
        
        Currently supports Python natively; returns immediately with True
        for non-Python files.
        """
        if file_path and not file_path.endswith((".py", ".pyw")):
            return SyntaxValidationResult(is_valid=True)

        try:
            ast.parse(code)
            return SyntaxValidationResult(is_valid=True)
        except SyntaxError as err:
            return SyntaxValidationResult(
                is_valid=False,
                error_message=f"SyntaxError: {err.msg} at line {err.lineno}, col {err.offset}",
                line_number=err.lineno,
                column_offset=err.offset,
            )
        except Exception as err:
            return SyntaxValidationResult(
                is_valid=False,
                error_message=f"ParseError: {str(err)}",
            )

    # -------------------------------------------------------------
    # 2. Extract Signatures
    # -------------------------------------------------------------
    @classmethod
    def extract_symbols(cls, code: str, file_path: str = "") -> Dict[str, SymbolSignature]:
        """Extracts top-level functions, classes, and class methods with full signatures."""
        if file_path and not file_path.endswith((".py", ".pyw")):
            return {}

        symbols: Dict[str, SymbolSignature] = {}
        try:
            tree = ast.parse(code)
        except Exception:
            return symbols

        lines = code.splitlines()

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = cls._format_function_signature(node, lines)
                sym_id = f"func:{node.name}"
                symbols[sym_id] = SymbolSignature(
                    symbol_id=sym_id,
                    name=node.name,
                    kind="async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                    signature=sig,
                    docstring=ast.get_docstring(node),
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                )
            elif isinstance(node, ast.ClassDef):
                cls_sig = f"class {node.name}"
                if node.bases:
                    bases_str = ", ".join(cls._format_ast_expr(b) for b in node.bases)
                    cls_sig += f"({bases_str})"
                
                cls_id = f"class:{node.name}"
                symbols[cls_id] = SymbolSignature(
                    symbol_id=cls_id,
                    name=node.name,
                    kind="class",
                    signature=cls_sig,
                    docstring=ast.get_docstring(node),
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                )

                # Also extract methods inside the class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_sig = cls._format_function_signature(item, lines)
                        method_id = f"class:{node.name}.method:{item.name}"
                        symbols[method_id] = SymbolSignature(
                            symbol_id=method_id,
                            name=item.name,
                            kind="method",
                            signature=method_sig,
                            docstring=ast.get_docstring(item),
                            line_start=item.lineno,
                            line_end=item.end_lineno or item.lineno,
                        )

        return symbols

    # -------------------------------------------------------------
    # 3. Diff Before vs After Code
    # -------------------------------------------------------------
    @classmethod
    def compute_ast_diffs(
        cls,
        before_code: str,
        after_code: str,
        file_path: str,
        causal_node_id: str = "",
    ) -> List[ASTDiff]:
        """Computes semantic AST diffs between original code and mutated code.
        
        Identifies:
        - ADDED_EXPORT: New function or class
        - DELETED_EXPORT: Removed function or class
        - SIGNATURE_CHANGED: Modified parameters or return types
        - BODY_CHANGED: Signature remained identical, but implementation body changed
        """
        now = int(time.time())
        node_id = causal_node_id or f"diff_{uuid.uuid4().hex[:8]}"

        # If not a Python file, compute a basic line diff
        if file_path and not file_path.endswith((".py", ".pyw")):
            raw_diff = "\n".join(
                difflib.unified_diff(
                    before_code.splitlines(),
                    after_code.splitlines(),
                    fromfile="before",
                    tofile="after",
                    lineterm="",
                )
            )
            if before_code != after_code:
                return [
                    ASTDiff(
                        id=f"diff_{uuid.uuid4().hex[:10]}",
                        causal_node_id=node_id,
                        file_path=file_path,
                        diff_type=ASTDiffType.BODY_CHANGED,
                        symbol_id=f"file:{file_path}",
                        raw_diff=raw_diff,
                        created_at=now,
                    )
                ]
            return []

        before_symbols = cls.extract_symbols(before_code, file_path)
        after_symbols = cls.extract_symbols(after_code, file_path)

        diffs: List[ASTDiff] = []
        raw_full_diff = "\n".join(
            difflib.unified_diff(
                before_code.splitlines(),
                after_code.splitlines(),
                fromfile="before",
                tofile="after",
                lineterm="",
            )
        )

        # A. Check for Added Exports
        for sym_id, after_sym in after_symbols.items():
            if sym_id not in before_symbols:
                diffs.append(
                    ASTDiff(
                        id=f"diff_{uuid.uuid4().hex[:10]}",
                        causal_node_id=node_id,
                        file_path=file_path,
                        diff_type=ASTDiffType.ADDED_EXPORT,
                        symbol_id=sym_id,
                        after_signature=after_sym.signature,
                        raw_diff=raw_full_diff,
                        created_at=now,
                    )
                )

        # B. Check for Deleted Exports
        for sym_id, before_sym in before_symbols.items():
            if sym_id not in after_symbols:
                diffs.append(
                    ASTDiff(
                        id=f"diff_{uuid.uuid4().hex[:10]}",
                        causal_node_id=node_id,
                        file_path=file_path,
                        diff_type=ASTDiffType.DELETED_EXPORT,
                        symbol_id=sym_id,
                        before_signature=before_sym.signature,
                        raw_diff=raw_full_diff,
                        created_at=now,
                    )
                )

        # C. Check for Changed Signatures vs. Body Changes
        for sym_id, after_sym in after_symbols.items():
            if sym_id in before_symbols:
                before_sym = before_symbols[sym_id]
                if before_sym.signature != after_sym.signature:
                    diffs.append(
                        ASTDiff(
                            id=f"diff_{uuid.uuid4().hex[:10]}",
                            causal_node_id=node_id,
                            file_path=file_path,
                            diff_type=ASTDiffType.SIGNATURE_CHANGED,
                            symbol_id=sym_id,
                            before_signature=before_sym.signature,
                            after_signature=after_sym.signature,
                            raw_diff=raw_full_diff,
                            created_at=now,
                        )
                    )

        # D. If no signature added/deleted/changed, but raw code changed -> BODY_CHANGED
        if not diffs and before_code != after_code:
            diffs.append(
                ASTDiff(
                    id=f"diff_{uuid.uuid4().hex[:10]}",
                    causal_node_id=node_id,
                    file_path=file_path,
                    diff_type=ASTDiffType.BODY_CHANGED,
                    symbol_id=f"file:{file_path}",
                    raw_diff=raw_full_diff,
                    created_at=now,
                )
            )

        return diffs

    # -------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------
    @classmethod
    def _format_function_signature(
        cls,
        node: Any,
        lines: List[str],
    ) -> str:
        """Formats a function definition into a clean canonical signature string."""
        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        args_list: List[str] = []

        # Standard arguments
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {cls._format_ast_expr(arg.annotation)}"
            args_list.append(arg_str)

        # *args
        if node.args.vararg:
            var_str = f"*{node.args.vararg.arg}"
            if node.args.vararg.annotation:
                var_str += f": {cls._format_ast_expr(node.args.vararg.annotation)}"
            args_list.append(var_str)

        # **kwargs
        if node.args.kwarg:
            kw_str = f"**{node.args.kwarg.arg}"
            if node.args.kwarg.annotation:
                kw_str += f": {cls._format_ast_expr(node.args.kwarg.annotation)}"
            args_list.append(kw_str)

        ret_str = ""
        if node.returns:
            ret_str = f" -> {cls._format_ast_expr(node.returns)}"

        return f"{prefix}{node.name}({', '.join(args_list)}){ret_str}"

    @classmethod
    def _format_ast_expr(cls, expr: Optional[ast.AST]) -> str:
        """Serializes an AST expression back to clean text (e.g. annotations)."""
        if expr is None:
            return ""
        try:
            return ast.unparse(expr)
        except Exception:
            # Fallback for Python versions before unparse or custom ASTs
            if isinstance(expr, ast.Name):
                return expr.id
            if isinstance(expr, ast.Constant):
                return repr(expr.value)
            return str(type(expr).__name__)
