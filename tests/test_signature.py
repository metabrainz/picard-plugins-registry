"""Tests for function-signature extraction and call-compatibility checks."""

from registry_lib.signature import Signature, find_function_def, incompatible_reason


def _sig(source: str, name: str) -> Signature:
    node = find_function_def(source, name)
    assert node is not None
    return Signature.from_function_def(node)


def test_from_function_def_basic():
    sig = _sig("def f(a, b, c=1):\n    pass\n", "f")
    assert sig.positional == ("a", "b", "c")
    assert sig.keyword_only == frozenset()
    assert not sig.has_var_positional
    assert not sig.has_var_keyword
    assert sig.max_positional == 3
    assert sig.accepted_keywords == {"a", "b", "c"}


def test_from_function_def_varargs_and_kwonly():
    sig = _sig("def f(a, *args, b, c=2, **kw):\n    pass\n", "f")
    assert sig.positional == ("a",)
    assert sig.keyword_only == {"b", "c"}
    assert sig.has_var_positional
    assert sig.has_var_keyword
    assert sig.accepted_keywords == {"a", "b", "c"}


def test_method_drops_self():
    node = find_function_def("class C:\n    pass\n", "C")  # not a function
    assert node is None
    sig = _sig("def m(self, x):\n    pass\n", "m")
    assert sig.positional == ("x",)


def test_find_function_def_missing():
    assert find_function_def("x = 1\n", "f") is None


def test_incompatible_unknown_keyword():
    sig = _sig("def f(a, b):\n    pass\n", "f")
    assert incompatible_reason(1, ("z",), sig) == "keyword argument 'z' is no longer accepted"


def test_incompatible_too_many_positional():
    sig = _sig("def f(a, b):\n    pass\n", "f")
    reason = incompatible_reason(3, (), sig)
    assert reason is not None
    assert "at most 2 positional" in reason


def test_compatible_call_returns_none():
    sig = _sig("def f(a, b, c=1):\n    pass\n", "f")
    assert incompatible_reason(2, ("c",), sig) is None


def test_var_keyword_accepts_any_keyword():
    sig = _sig("def f(a, **kw):\n    pass\n", "f")
    assert incompatible_reason(1, ("anything",), sig) is None


def test_var_positional_accepts_many():
    sig = _sig("def f(a, *args):\n    pass\n", "f")
    assert incompatible_reason(5, (), sig) is None
