from __future__ import annotations

import runpy
from pathlib import Path


CONF_PATH = Path(__file__).resolve().parents[1] / "docs" / "conf.py"


def test_google_site_verification_meta_tag_is_empty_when_env_not_set(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_SITE_VERIFICATION", raising=False)

    conf = runpy.run_path(str(CONF_PATH))

    assert conf["ogp_custom_meta_tags"] == []


def test_google_site_verification_meta_tag_uses_env_value(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SITE_VERIFICATION", 'abc"<tag>')

    conf = runpy.run_path(str(CONF_PATH))

    assert conf["ogp_custom_meta_tags"] == ['<meta name="google-site-verification" content="abc&quot;&lt;tag&gt;" />']
