"""Controlled thread directory tests."""

from pathlib import Path
from uuid import uuid4

import pytest
from app.storage.thread_storage import ThreadStorage


def test_thread_storage_uses_only_fixed_children(tmp_path: Path) -> None:
    """A canonical server UUID creates exactly the approved directory tree."""
    storage = ThreadStorage(tmp_path)
    thread_id = str(uuid4())
    root = storage.create(thread_id)

    assert root == (tmp_path / "threads" / thread_id).resolve()
    assert {child.name for child in root.iterdir()} == {"uploads", "parsed", "outputs"}

    staged = storage.stage_delete(thread_id)
    assert not root.exists()
    storage.restore_staged(thread_id, staged)
    assert root.exists()

    staged = storage.stage_delete(thread_id)
    storage.purge_staged(staged)
    assert not root.exists()


@pytest.mark.parametrize("unsafe_id", ["../escape", "CON", str(uuid4()).upper()])
def test_thread_storage_rejects_noncanonical_identifiers(tmp_path: Path, unsafe_id: str) -> None:
    """Client-like path text and noncanonical UUIDs cannot become directories."""
    storage = ThreadStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.create(unsafe_id)
    assert not (tmp_path / "escape").exists()
