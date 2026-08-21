from __future__ import annotations

import pytest


@pytest.fixture
def settings(tmp_path):
    from juno.config import Settings

    data = tmp_path / "data"
    inbox = tmp_path / "inbox"
    data.mkdir()
    inbox.mkdir()
    return Settings(
        juno_data_dir=data,
        juno_inbox_dir=inbox,
        embedding_backend="stub",
        juno_api_token="test-token",
        telegram_bot_token="",
    )
