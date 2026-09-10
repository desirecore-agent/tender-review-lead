"""Lead-owned bounded raw-byte reader, extracted from check_task_spec.py.

Copyright (c) 2026 DesireCore Contributors. MIT; see Agent repository LICENSE.
No checker execution or external dependency imports. Original bounded Reader and
path functions are preserved; private development provenance is not a dependency.
"""
import os
import stat
import time
from pathlib import Path
from prepare_delegation_input import digest

MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_READS = 256
MAX_SECONDS = 20

class Refused(Exception):
    def __init__(self, code, subject, invocation=False):
        self.code, self.subject, self.invocation = code, subject, invocation


def refuse(code, subject, invocation=False):
    raise Refused(code, subject, invocation)


def normalized(value):
    if not isinstance(value, str) or not value or '\x00' in value or not os.path.isabs(value):
        refuse('INVALID_ABSOLUTE_PATH', 'paths')
    if value.startswith('//') or len(value) > 4096 or len(Path(value).parts) > 256 or os.path.normpath(value) != value or any(part == '..' for part in Path(value).parts):
        refuse('NONCANONICAL_PATH', 'paths')
    return os.path.normcase(value)


def contains(parent, child):
    try:
        return os.path.commonpath([parent, child]) == parent
    except ValueError:
        return False


def allowed(value, grants):
    value = normalized(value)
    return any(value == normalized(g['path']) or (g['kind'] == 'directory' and contains(normalized(g['path']), value)) for g in grants)


def no_symlink_components(value):
    path = Path(value)
    for item in reversed([path, *path.parents]):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            refuse('SYMLINK_PATH', 'paths')
        if item != path and not stat.S_ISDIR(info.st_mode):
            refuse('NON_DIRECTORY_ANCESTOR', 'paths')


class Reader:
    inline = False
    norm = staticmethod(normalized)
    contains = staticmethod(contains)
    allowed = staticmethod(allowed)
    path_check = staticmethod(no_symlink_components)
    def __init__(self):
        self.read_count, self.total = 0, 0
        self.snapshots = {}
        self.identity_limits = {}
        self.scope_snapshots = {}
        self.spec_hash = None
        self.deadline = time.monotonic() + MAX_SECONDS

    def tick(self):
        if time.monotonic() > self.deadline:
            refuse('CHECK_TIME_BUDGET', 'limits', True)

    def read(self, value, grants=None, limit=MAX_FILE, remember=True):
        self.tick()
        # Authorization precedes stat/open of any spec-derived path.
        if grants is not None and not allowed(value, grants):
            refuse('READ_NOT_AUTHORIZED', 'read_scope')
        normalized(value)
        if value in self.snapshots:
            limit = min(limit, self.snapshots[value][2])
        no_symlink_components(value)
        if not all(hasattr(os, flag) for flag in ['O_NOFOLLOW', 'O_NONBLOCK', 'O_DIRECTORY']) or os.open not in os.supports_dir_fd:
            refuse('SAFE_OPEN_UNAVAILABLE', 'runtime', True)
        if self.read_count >= MAX_READS:
            refuse('READ_COUNT_BUDGET', 'limits', True)
        directories = []
        try:
            parts = Path(value).parts
            # Pin every directory component. O_NOFOLLOW on only the final file
            # would still permit an intermediate-directory symlink swap.
            current = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
            directories.append(current)
            entries = []
            for component in parts[1:-1]:
                next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
                directories.append(next_fd)
                entries.append((current, component, next_fd))
                current = next_fd
            before = os.stat(parts[-1], dir_fd=current, follow_symlinks=False)
            limit = min(limit, self.identity_limits.get((before.st_dev, before.st_ino), limit))
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
                refuse('UNSAFE_OR_OVERSIZE_FILE', 'files')
            if before.st_size > MAX_TOTAL - self.total:
                refuse('TOTAL_BYTE_BUDGET', 'limits', True)
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
            try:
                opened = os.fstat(fd)
                identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
                if identity(before) != identity(opened) or not stat.S_ISREG(opened.st_mode):
                    refuse('FILE_IDENTITY_CHANGED', 'files')
                chunks, remaining = [], before.st_size
                while remaining:
                    self.tick()
                    chunk = os.read(fd, min(65536, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                raw = b''.join(chunks)
                after_fd = os.fstat(fd)
            finally:
                os.close(fd)
            after_path = os.stat(parts[-1], dir_fd=current, follow_symlinks=False)
            if len(raw) != before.st_size or len(raw) > limit or identity(before) != identity(after_fd) or identity(before) != identity(after_path):
                refuse('FILE_CHANGED_DURING_READ', 'files')
            for parent_fd, component, directory_fd in entries:
                bound = os.fstat(directory_fd)
                current_entry = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
                if not stat.S_ISDIR(current_entry.st_mode) or (bound.st_dev, bound.st_ino) != (current_entry.st_dev, current_entry.st_ino):
                    refuse('DIRECTORY_IDENTITY_CHANGED', 'files')
        except OSError:
            refuse('FILE_IO_ERROR', 'files', True)
        finally:
            for directory_fd in reversed(directories):
                os.close(directory_fd)
        self.read_count += 1
        self.total += len(raw)
        snapshot = (identity(before), digest(raw), limit)
        self.identity_limits[(before.st_dev, before.st_ino)] = limit
        if remember:
            if value in self.snapshots and self.snapshots[value][:2] != snapshot[:2]:
                refuse('FILE_SNAPSHOT_CHANGED', 'files')
            self.snapshots[value] = snapshot
        return raw, snapshot

    def stable(self):
        for value, before in list(self.snapshots.items()):
            _, after = self.read(value, limit=before[2], remember=False)
            if before[:2] != after[:2]:
                refuse('FILE_SNAPSHOT_CHANGED', 'files')
