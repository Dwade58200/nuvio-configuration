# -*- coding: utf-8 -*-
"""Tests pour scripts/trakt_auth.py -- aucun appel réseau réel."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from trakt_auth import demander_code_appareil, echanger_code_contre_jeton  # noqa: E402


class FausseReponse:
    def __init__(self, json_data=None, status_code=200, text=""):
        self._json = json_data or {}
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_demander_code_appareil():
    with patch("trakt_auth.requests.post") as mock_post:
        mock_post.return_value = FausseReponse({
            "device_code": "abc",
            "user_code": "WXYZ1234",
            "verification_url": "https://trakt.tv/activate",
            "expires_in": 600,
            "interval": 5,
        })
        resultat = demander_code_appareil("mon-client-id")

        assert resultat["user_code"] == "WXYZ1234"
        appel = mock_post.call_args
        assert appel.kwargs["json"] == {"client_id": "mon-client-id"}


def test_echanger_code_reussite():
    with patch("trakt_auth.requests.post") as mock_post:
        mock_post.return_value = FausseReponse({"access_token": "abc", "refresh_token": "xyz"})
        resultat = echanger_code_contre_jeton("id", "secret", "device123")
        assert resultat == {"access_token": "abc", "refresh_token": "xyz"}


def test_echanger_code_en_attente_retourne_none():
    with patch("trakt_auth.requests.post") as mock_post:
        mock_post.return_value = FausseReponse(status_code=400)
        assert echanger_code_contre_jeton("id", "secret", "device123") is None


def test_echanger_code_expire_quitte_le_script():
    with patch("trakt_auth.requests.post") as mock_post:
        mock_post.return_value = FausseReponse(status_code=410)
        try:
            echanger_code_contre_jeton("id", "secret", "device123")
            assert False, "aurait dû lever SystemExit"
        except SystemExit:
            pass


def test_echanger_code_refuse_quitte_le_script():
    with patch("trakt_auth.requests.post") as mock_post:
        mock_post.return_value = FausseReponse(status_code=418)
        try:
            echanger_code_contre_jeton("id", "secret", "device123")
            assert False, "aurait dû lever SystemExit"
        except SystemExit:
            pass


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
