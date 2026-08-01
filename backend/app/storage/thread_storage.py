"""Controlled per-thread directory management."""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

_STAGED_THREAD = re.compile(
    r"^\.deleting-(?P<thread_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})-[0-9a-f]{32}$"
)


@dataclass(frozen=True, slots=True)
class ThreadRecoveryResult:
    """Counts produced while reconciling database threads and local trees."""

    restored: int = 0
    purged: int = 0
    created: int = 0


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

    def recover(self, existing_thread_ids: set[str]) -> ThreadRecoveryResult:
        """Resolve interrupted directory deletes and recreate fixed thread folders."""
        self._threads_root.mkdir(parents=True, exist_ok=True)
        restored = 0
        purged = 0
        created = 0

        staged_by_thread: dict[str, list[Path]] = {}
        for candidate in sorted(self._threads_root.iterdir(), key=lambda path: path.name):
            match = _STAGED_THREAD.fullmatch(candidate.name)
            if match is None or candidate.is_symlink() or not candidate.is_dir():
                continue
            thread_id = match.group("thread_id")
            staged_by_thread.setdefault(thread_id, []).append(candidate)

        for thread_id, staged_directories in staged_by_thread.items():
            root = self._thread_root(thread_id)
            if thread_id in existing_thread_ids and not root.exists():
                staged_directories.pop(0).rename(root)
                restored += 1
            for staged in staged_directories:
                shutil.rmtree(staged)
                purged += 1

        for thread_id in existing_thread_ids:
            root = self._thread_root(thread_id)
            if not root.exists():
                root.mkdir(parents=True)
                created += 1
            for directory in self._SUBDIRECTORIES:
                (root / directory).mkdir(exist_ok=True)

        for candidate in tuple(self._threads_root.iterdir()):
            if candidate.is_symlink() or not candidate.is_dir():
                continue
            try:
                parsed_id = UUID(candidate.name)
            except ValueError:
                continue
            if str(parsed_id) != candidate.name or candidate.name in existing_thread_ids:
                continue
            shutil.rmtree(candidate)
            purged += 1

        return ThreadRecoveryResult(restored=restored, purged=purged, created=created)
