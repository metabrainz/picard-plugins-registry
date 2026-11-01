"""Lightweight function-signature extraction and call-compatibility checks.

The import audit answers "does this name still resolve?". This module adds a
small, best-effort layer on top: for a plugin's *direct calls* to a Picard
function it imported, does the way the plugin calls it still match that
function's parameters on the target Picard ref?

Scope is deliberately narrow, to stay reliable and simple:

- Only *direct* calls of an imported name (``f(...)``) are analyzed — not method
  calls on instances, nor subclass/override compatibility, which would require
  type tracking.
- Only two *unambiguous* breakages are reported:
    1. a keyword argument the function no longer accepts (and it has no
       ``**kwargs``), and
    2. more positional arguments than the function accepts (and it has no
       ``*args``).
  "Missing required argument" is intentionally *not* reported: deciding
  requiredness across defaults/overloads is error-prone, and a false "you broke
  this" is worse than a missed one.

A ``Signature`` is extracted from the function's ``ast.FunctionDef``; no code is
imported or executed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Signature:
    """A function's parameter shape, as seen in its ``def``.

    Attributes:
        positional: Names of positional-or-keyword and positional-only params,
            in order.
        keyword_only: Names of keyword-only params (after ``*``).
        has_var_positional: Whether the function has ``*args``.
        has_var_keyword: Whether the function has ``**kwargs``.
    """

    positional: tuple[str, ...]
    keyword_only: frozenset[str]
    has_var_positional: bool
    has_var_keyword: bool

    @property
    def accepted_keywords(self) -> frozenset[str]:
        """Names that may be passed as keyword arguments."""
        return frozenset(self.positional) | self.keyword_only

    @property
    def max_positional(self) -> int:
        """Largest number of positional args accepted (ignoring ``*args``)."""
        return len(self.positional)

    @classmethod
    def from_function_def(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Signature:
        """Build a Signature from a function definition node.

        A leading ``self`` / ``cls`` is dropped so the signature matches how a
        bound method is actually called.
        """
        a = node.args
        positional = [p.arg for p in (*a.posonlyargs, *a.args)]
        if positional and positional[0] in {"self", "cls"}:
            positional = positional[1:]
        return cls(
            positional=tuple(positional),
            keyword_only=frozenset(p.arg for p in a.kwonlyargs),
            has_var_positional=a.vararg is not None,
            has_var_keyword=a.kwarg is not None,
        )


def find_function_def(source: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the top-level ``def``/``async def`` named ``name``, if any."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def incompatible_reason(arg_count: int, keywords: tuple[str, ...], sig: Signature) -> str | None:
    """Return why a call is incompatible with ``sig``, or None if it is fine.

    Operates on the already-extracted call shape (positional count and explicit
    keyword names). Only the two unambiguous error classes are reported (see the
    module docstring). Callers must skip calls that use ``*args``/``**kwargs``
    spreads, whose real arity is unknown.
    """
    if not sig.has_var_keyword:
        for kw in keywords:
            if kw not in sig.accepted_keywords:
                return f"keyword argument '{kw}' is no longer accepted"
    if not sig.has_var_positional and arg_count > sig.max_positional:
        return f"takes at most {sig.max_positional} positional argument(s), {arg_count} given"
    return None
