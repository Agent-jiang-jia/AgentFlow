"""Controlled per-thread directory management."""

import shutil
from pathlib import Path
from uuid import UUID, uuid4


class ThreadStorage:
    """Create and remove the fixed directory tree owned by one thread."""

    _SUBDIRECTORIES = ("uploads", "parsed", "outputs")

    def __init__(self, data_dir: Path) -> None:
        self._threads_root = (data_dir / "threads").resolve()

    def _thread_root(self, thread_id: str) -> Path:
        parsed_id = UUID(thread_id)
        if str(parsed_id) != thread_id:
            raise ValueError("Thread identifier is not canonical")
        candidate = (self._threads_root / thread_id).resolve()
        if not candidate.is_relative_to(self._threads_root):
            raise ValueError("Thread directory escaped the storage root")
        return candidate

    def create(self, thread_id: str) -> Path:
        """Create the thread root and its three fixed subdirectories."""
        root = self._thread_root(thread_id)
        root.mkdir(parents=True, exist_ok=False)
        for directory in self._SUBDIRECTORIES:
            (root / directory).mkdir()
        return root

    def remove_created(self, thread_id: str) -> None:
        """Remove a just-created tree during transaction compensation."""
        root = self._thread_root(thread_id)
        if root.exists():
            shutil.rmtree(root)

    def stage_delete(self, thread_id: str) -> Path | None:
        """Atomically move a thread tree aside before its database commit."""
        root = self._thread_root(thread_id)
        if not root.exists():
            return None
        staged = self._threads_root / f".deleting-{thread_id}-{uuid4().hex}"
        root.rename(staged)
        return staged

    def restore_staged(self, thread_id: str, staged: Path | None) -> None:
        """Restore a staged tree when database deletion is rolled back."""
        if staged is None or not staged.exists():
            return
        staged.rename(self._thread_root(thread_id))

    def purge_staged(self, staged: Path | None) -> None:
        """Permanently remove a tree after database deletion commits."""
        if staged is not None and staged.exists():
            shutil.rmtree(staged)
