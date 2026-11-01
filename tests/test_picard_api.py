"""Tests for resolving the Picard plugin-API surface."""

from unittest.mock import patch

import pytest

from registry_lib.picard_api import ApiSurfaceError, fetch_api_surface


class _FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def test_fetch_api_surface_parses_dunder_all():
    source = "from picard.cluster import Cluster\n__all__ = [\n    'Album',\n    'Track',\n    't_',\n]\n"
    with patch("registry_lib.picard_api.requests.get", return_value=_FakeResponse(200, source)):
        surface = fetch_api_surface("master")
    assert surface.ref == "master"
    assert surface.module == "picard.plugin3.api"
    assert surface.exported_names == frozenset({"Album", "Track", "t_"})


def test_fetch_api_surface_404_is_clear_error():
    with patch("registry_lib.picard_api.requests.get", return_value=_FakeResponse(404)):
        with pytest.raises(ApiSurfaceError, match="not found at"):
            fetch_api_surface("nonexistent-tag")


def test_fetch_api_surface_missing_dunder_all():
    with patch("registry_lib.picard_api.requests.get", return_value=_FakeResponse(200, "x = 1\n")):
        with pytest.raises(ApiSurfaceError, match="does not define __all__"):
            fetch_api_surface("master")
