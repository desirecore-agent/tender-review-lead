#!/usr/bin/env python3
"""Read-only TaskSpec checks. External authority arrives on stdin, not from spec.

Requires the existing Evidence-owned, hash-locked jsonschema environment.
No installs, subprocesses, network requests, or file writes. Exit 0/1/2.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import base64
import ntpath
import posixpath
import threading
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import signal
import stat
import time

MAX_JSON = 1024 * 1024
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_READS = 256
MAX_SECONDS = 20
MAX_INLINE = 8 * 1024 * 1024
EXPECTED_PACKAGES = {'attrs', 'jsonschema', 'jsonschema-specifications', 'referencing', 'rpds-py', 'typing-extensions'}

class Refused(Exception):
    def __init__(self, code, subject, invocation=False):
        self.code, self.subject, self.invocation = code, subject, invocation


def refuse(code, subject, invocation=False):
    raise Refused(code, subject, invocation)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            refuse('DUPLICATE_JSON_KEY', 'json')
        result[key] = value
    return result


def parse_json(raw):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                          parse_constant=lambda _: refuse('NONFINITE_JSON', 'json'))
    except (ValueError, UnicodeError, RecursionError):
        refuse('INVALID_JSON', 'json')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


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


def overlapping(left, right):
    return contains(left, right) or contains(right, left)


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



def physical_chain(value):
    """Bind existing scope components by descriptors, including case aliases."""
    normalized(value)
    if not all(hasattr(os, key) for key in ['O_DIRECTORY', 'O_NOFOLLOW', 'O_NONBLOCK']):
        refuse('SAFE_OPEN_UNAVAILABLE', 'scopes', True)
    descriptors, bindings = [], []
    try:
        parts = Path(value).parts
        current = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
        descriptors.append(current)
        for index, component in enumerate(parts[1:]):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(parts[1:]) - 1:
                flags |= os.O_DIRECTORY
            child = os.open(component, flags, dir_fd=current)
            descriptors.append(child)
            bindings.append((current, component, child))
            current = child
        chain = []
        for fd in descriptors:
            info = os.fstat(fd)
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                refuse('UNSAFE_SCOPE_KIND', 'scopes')
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                refuse('UNSAFE_SCOPE_LINKS', 'scopes')
            chain.append((info.st_dev, info.st_ino))
        for parent, name, child in bindings:
            entry, opened = os.stat(name, dir_fd=parent, follow_symlinks=False), os.fstat(child)
            if (entry.st_dev, entry.st_ino) != (opened.st_dev, opened.st_ino) or stat.S_ISLNK(entry.st_mode):
                refuse('SCOPE_IDENTITY_CHANGED', 'scopes')
        return tuple(chain)
    except FileNotFoundError:
        refuse('SCOPE_PATH_MISSING', 'scopes')
    except OSError:
        refuse('SCOPE_IDENTITY_UNAVAILABLE', 'scopes')
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def physical_scope_checks(scopes, reader):
    groups = {}
    for key, paths in scopes.items():
        groups[key] = []
        for value in paths:
            reader.tick()
            chain = physical_chain(value)
            reader.scope_snapshots[value] = chain
            groups[key].append(chain)
    def overlap(a, b):
        return a[-1] in b or b[-1] in a
    writes = groups['callee_write_paths'] + groups['lead_write_paths']
    if any(overlap(a, b) for a in groups['callee_write_paths'] for b in groups['lead_write_paths']) or any(overlap(a, b) for a in groups['read_only_paths'] for b in writes):
        refuse('PHYSICAL_SCOPE_OVERLAP', 'scopes')


def local_schema(reader, filename):
    location = str(Path(__file__).absolute().parent.parent / 'schemas' / filename)
    schema = parse_json((reader.read_trusted(location, MAX_JSON) if reader.inline else reader.read(location, limit=MAX_JSON))[0])
    expected_ids = {'delegation-task.schema.json': 'tender-review/lead-delegation-task/v1/schema.json', 'delegation-authority.schema.json': 'tender-review/lead-task-spec-authority/v1/schema.json', 'delegation-check-result.schema.json': 'tender-review/lead-task-spec-check/v1/schema.json', 'delegation-inline-transport.schema.json': 'tender-review/lead-task-spec-inline/v1/schema.json'}
    if schema.get('$id') != expected_ids[filename]:
        refuse('SCHEMA_IDENTITY_MISMATCH', 'checker_schema', True)
    if schema.get('$schema') != 'http://json-schema.org/draft-07/schema#':
        refuse('SCHEMA_DRAFT_MISMATCH', 'checker_schema', True)
    def visit(item):
        if isinstance(item, dict):
            if '$ref' in item and (not isinstance(item['$ref'], str) or not item['$ref'].startswith('#')):
                refuse('NONLOCAL_SCHEMA_REFERENCE', 'checker_schema', True)
            for value in item.values():
                visit(value)
        elif isinstance(item, list):
            for value in item:
                visit(value)
    visit(schema)
    return schema


def check_schema(schema, value, label, Draft7Validator, Registry):
    try:
        Draft7Validator.check_schema(schema)
        if next(Draft7Validator(schema, registry=Registry()).iter_errors(value), None) is not None:
            refuse('SCHEMA_VALIDATION_FAILED', label)
    except Refused:
        raise
    except Exception:
        refuse('SCHEMA_ENGINE_ERROR', label, True)


def unique_rows(rows, key, label):
    result = {}
    for item in rows:
        name = item[key]
        if name in result:
            refuse('DUPLICATE_ID', label)
        result[name] = item
    return result


def check_runtime(authority, reader):
    runtime = authority['runtime']
    if normalized(runtime['python_executable']) != normalized(sys.executable) or normalized(runtime['environment_prefix']) != normalized(sys.prefix) or sys.prefix == sys.base_prefix:
        refuse('RUNTIME_IDENTITY_MISMATCH', 'runtime')
    if not reader.inline:
        no_symlink_components(sys.prefix)
    # The checker-owned lock is a separate trusted runtime binding, never an extra
    # grant available to the business callee through io_scope.
    if reader.inline:
        raw = reader.runtime_lock
    else:
        if 'lock_path' not in runtime:
            refuse('MISSING_RUNTIME_LOCK_PATH', 'runtime')
        raw = reader.read(runtime['lock_path'], [{'path': runtime['lock_path'], 'kind': 'file'}])[0]
    if digest(raw) != runtime['lock_sha256']:
        refuse('LOCK_HASH_MISMATCH', 'runtime')
    try:
        text = raw.decode('utf-8').replace('\\\r\n', '').replace('\\\n', '')
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
        if sorted(line for line in lines if line.startswith('--')) != ['--only-binary=:all:', '--require-hashes']:
            refuse('LOCK_OPTIONS_INVALID', 'runtime')
        pins = {}
        for line in lines:
            if line.startswith('--'):
                continue
            match = re.fullmatch(r'([A-Za-z0-9_-]+)==([0-9]+(?:\.[0-9]+)+)(?:\s+--hash=sha256:[a-f0-9]{64})+\s*', line)
            if not match:
                refuse('LOCK_ENTRY_INVALID', 'runtime')
            name = match[1].replace('_', '-').lower()
            if name in pins:
                refuse('LOCK_DUPLICATE_PACKAGE', 'runtime')
            pins[name] = match[2]
        if set(pins) != EXPECTED_PACKAGES:
            refuse('LOCK_PACKAGE_CLOSURE', 'runtime')
        for name, version in pins.items():
            distribution = importlib.metadata.distribution(name)
            if distribution.version != version or not contains(normalized(sys.prefix), normalized(str(Path(distribution.locate_file('')).absolute()))):
                refuse('INSTALLED_DEPENDENCY_MISMATCH', 'runtime')
    except (UnicodeError, importlib.metadata.PackageNotFoundError):
        refuse('DEPENDENCY_UNAVAILABLE', 'runtime', True)


def run(spec_path, raw_authority, reader, checks):
    try:
        from jsonschema import Draft7Validator
        from referencing import Registry
    except ImportError:
        refuse('DEPENDENCY_UNAVAILABLE', 'runtime', True)
    authority = parse_json(raw_authority)
    auth_schema = local_schema(reader, 'delegation-authority.schema.json')
    spec_schema = local_schema(reader, 'delegation-task.schema.json')
    result_schema = local_schema(reader, 'delegation-check-result.schema.json')
    try:
        Draft7Validator.check_schema(result_schema)
    except Exception:
        refuse('OUTPUT_SCHEMA_INVALID', 'checker_schema', True)
    check_schema(auth_schema, authority, 'authority', Draft7Validator, Registry)
    # Validate trusted grant syntax first; grants are external, not accepted from spec.
    for key in ['read_grants', 'callee_write_grants', 'lead_write_grants']:
        for grant in authority[key]:
            reader.norm(grant['path'])
            reader.path_check(grant['path'])
            if not reader.inline and os.path.exists(grant['path']):
                if (grant['kind'] == 'directory' and not os.path.isdir(grant['path'])) or (grant['kind'] == 'file' and not os.path.isfile(grant['path'])):
                    refuse('GRANT_KIND_MISMATCH', 'authority')
    check_runtime(authority, reader)
    checks['runtime_lock'] = True
    raw_spec = reader.read(spec_path, authority['read_grants'], limit=MAX_JSON)[0]
    observed_hash = digest(raw_spec)
    reader.spec_hash = observed_hash
    if observed_hash != authority['spec_sha256']:
        refuse('SPEC_HASH_MISMATCH', 'spec')
    spec = parse_json(raw_spec)
    check_schema(spec_schema, spec, 'spec', Draft7Validator, Registry)
    checks['schema'] = True
    if any(spec[key] != authority[key] for key in ['task_id', 'revision', 'target_agent_id', 'parent_plan']):
        refuse('AUTHORITY_BINDING_MISMATCH', 'authority')
    reader.norm(authority['parent_plan']['path'])
    checks['authority'] = True
    originals = unique_rows(authority['instruction_sources'], 'source_id', 'authority_sources')
    sources = unique_rows(spec['instruction_sources'], 'source_id', 'sources')
    if set(originals) != set(sources):
        refuse('INSTRUCTION_SOURCE_SET_MISMATCH', 'sources')
    for key, item in sources.items():
        reader.tick()
        if 'text' in item:
            raw = item['text'].encode('utf-8')
        else:
            if not any(reader.contains(reader.norm(root), reader.norm(item['path'])) for root in spec['io_scope']['read_only_paths']):
                refuse('SOURCE_OUTSIDE_SPEC_READ_SCOPE', 'sources')
            raw = reader.read(item['path'], authority['read_grants'], limit=MAX_JSON)[0]
        if raw != originals[key]['text'].encode('utf-8') or digest(raw) != item['sha256']:
            refuse('INSTRUCTION_BYTES_MISMATCH', 'sources')
    checks['sources'] = True
    constraints = unique_rows(spec['hard_constraints'], 'constraint_id', 'constraints')
    resources = unique_rows(spec['resources'], 'resource_id', 'resources')
    criteria = unique_rows(spec['acceptance_criteria'], 'criterion_id', 'criteria')
    for item in constraints.values():
        reader.tick()
        if item['source_id'] not in originals or item['source_quote'] not in originals[item['source_id']]['text']:
            refuse('CONSTRAINT_SOURCE_QUOTE_MISMATCH', 'constraints')
    covered = set()
    for item in list(resources.values()) + list(criteria.values()):
        if not set(item['constraint_ids']) <= set(constraints):
            refuse('CONSTRAINT_REFERENCE_MISSING', 'references')
    for item in criteria.values():
        covered.update(item['constraint_ids'])
    if covered != set(constraints):
        refuse('ACCEPTANCE_CONSTRAINT_COVERAGE', 'references')
    checks['references'] = True
    scopes = spec['io_scope']
    for name, grant_name in [('read_only_paths', 'read_grants'), ('callee_write_paths', 'callee_write_grants'), ('lead_write_paths', 'lead_write_grants')]:
        for value in scopes[name]:
            if not reader.allowed(value, authority[grant_name]):
                refuse('SCOPE_NOT_AUTHORIZED', name)
            reader.path_check(value)
    readonly = [reader.norm(p) for p in scopes['read_only_paths']]
    if not any(reader.contains(p, reader.norm(spec_path)) for p in readonly):
        refuse('SPEC_OUTSIDE_CALLEE_READ_SCOPE', 'scopes')
    callee = [reader.norm(p) for p in scopes['callee_write_paths']]
    lead = [reader.norm(p) for p in scopes['lead_write_paths']]
    if any((reader.contains(a, b) or reader.contains(b, a)) for a in callee for b in lead) or any((reader.contains(a, b) or reader.contains(b, a)) for a in readonly for b in callee + lead):
        refuse('SCOPE_OWNERSHIP_OVERLAP', 'scopes')
    if not reader.inline:
        physical_scope_checks(scopes, reader)
    checks['scopes'] = True
    for item in resources.values():
        reader.tick()
        if not any(reader.contains(p, reader.norm(item['path'])) for p in readonly):
            refuse('RESOURCE_OUTSIDE_SPEC_READ_SCOPE', 'resources')
        raw = reader.read(item['path'], authority['read_grants'])[0]
        if digest(raw) != item['sha256']:
            refuse('RESOURCE_HASH_MISMATCH', 'resources')
    checks['resources'] = True
    reader.stable()
    for value, before in reader.scope_snapshots.items():
        if physical_chain(value) != before:
            refuse('SCOPE_IDENTITY_CHANGED', 'scopes')
    checks['stability'] = True
    return observed_hash


def inline_normalized(value, flavor):
    if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
        refuse('INVALID_ABSOLUTE_PATH', 'inline_paths')
    module = ntpath if flavor == 'windows' else posixpath
    if flavor == 'windows':
        text = value.replace('/', '\\')
        drive, tail = ntpath.splitdrive(text)
        if not drive or not tail.startswith('\\') or text.startswith(('\\\\?\\', '\\\\.\\')):
            refuse('INVALID_ABSOLUTE_PATH', 'inline_paths')
        parts = [part for part in tail.split('\\') if part]
        if any(part.endswith(('.', ' ')) or ':' in part or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part) for part in parts):
            refuse('AMBIGUOUS_WINDOWS_PATH', 'inline_paths')
        if module.normpath(text) != text:
            refuse('NONCANONICAL_PATH', 'inline_paths')
        return module.normcase(text)
    if value.startswith('//') or not module.isabs(value) or module.normpath(value) != value:
        refuse('NONCANONICAL_PATH', 'inline_paths')
    # Conservative case folding in inline mode catches common aliases without
    # pretending to know the actual filesystem's identity/case rules.
    return value.casefold()


class InlineReader(Reader):
    inline = True

    def __init__(self, flavor):
        super().__init__()
        self.flavor, self.captures, self.capture_checks = flavor, {}, 0
        self.runtime_lock = b''

    def norm(self, value):
        return inline_normalized(value, self.flavor)

    def contains(self, parent, child):
        try:
            module = ntpath if self.flavor == 'windows' else posixpath
            return module.commonpath([parent, child]) == parent
        except ValueError:
            return False

    def allowed(self, value, grants):
        value = self.norm(value)
        return any(value == self.norm(g['path']) or (g['kind'] == 'directory' and self.contains(self.norm(g['path']), value)) for g in grants)

    def path_check(self, value):
        self.norm(value)  # Never stat/open a path supplied by the inline request.

    def read(self, value, grants=None, limit=MAX_FILE, remember=True):
        self.tick()
        if grants is not None and not self.allowed(value, grants):
            refuse('READ_NOT_AUTHORIZED', 'inline_captures')
        key = self.norm(value)
        if key not in self.captures:
            refuse('CAPTURE_BYTES_MISSING', 'inline_captures')
        if self.capture_checks + self.read_count >= MAX_READS:
            refuse('READ_COUNT_BUDGET', 'limits', True)
        if key in self.snapshots:
            limit = min(limit, self.snapshots[key][2])
        raw = self.captures[key]
        if len(raw) > limit or len(raw) > MAX_TOTAL - self.total:
            refuse('CAPTURE_BYTE_BUDGET', 'inline_captures')
        self.total += len(raw)
        self.capture_checks += 1
        snapshot = (None, digest(raw), limit)
        if remember:
            if key in self.snapshots and self.snapshots[key][:2] != snapshot[:2]:
                refuse('CAPTURE_BYTES_CHANGED', 'inline_captures')
            self.snapshots[key] = snapshot
        return raw, snapshot

    def read_trusted(self, location, limit):
        # These paths are fixed adjacent package schemas, not any Spec/authority
        # locator. Portable mode does not claim physical stability of the package.
        self.tick()
        if self.read_count + self.capture_checks >= MAX_READS:
            refuse('READ_COUNT_BUDGET', 'limits', True)
        with open(location, 'rb') as stream:
            size = os.fstat(stream.fileno()).st_size
            if size > limit or size > MAX_TOTAL - self.total:
                refuse('TRUSTED_SCHEMA_BUDGET', 'checker_schema', True)
            raw = stream.read(size)
            if len(raw) != size or os.fstat(stream.fileno()).st_size != size:
                refuse('TRUSTED_SCHEMA_CHANGED', 'checker_schema', True)
        self.total += len(raw)
        self.read_count += 1
        return raw, None

    def stable(self):
        for key, before in list(self.snapshots.items()):
            # In-memory capture identity only; never claim OS file stability.
            if digest(self.captures[key]) != before[1] or len(self.captures[key]) > before[2]:
                refuse('CAPTURE_BYTES_CHANGED', 'inline_captures')


def decode_capture(value, limit):
    if not isinstance(value, str) or len(value) > ((limit + 2) // 3) * 4:
        refuse('CAPTURE_BYTE_BUDGET', 'inline_captures')
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        refuse('INVALID_BASE64', 'inline_captures')
    if len(raw) > limit or base64.b64encode(raw).decode('ascii') != value:
        refuse('INVALID_BASE64', 'inline_captures')
    return raw


def run_inline(raw_frame, checks, holder):
    try:
        from jsonschema import Draft7Validator
        from referencing import Registry
    except ImportError:
        refuse('DEPENDENCY_UNAVAILABLE', 'runtime', True)
    envelope = parse_json(raw_frame)
    reader = InlineReader('posix')
    holder['reader'] = reader
    transport_schema = local_schema(reader, 'delegation-inline-transport.schema.json')
    check_schema(transport_schema, envelope, 'inline_transport', Draft7Validator, Registry)
    reader.flavor = envelope['path_flavor']
    authority = envelope['authority']
    raw_authority = json.dumps(authority, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(raw_authority) > MAX_JSON:
        refuse('AUTHORITY_SIZE_INVALID', 'authority', True)
    check_schema(local_schema(reader, 'delegation-authority.schema.json'), authority, 'authority', Draft7Validator, Registry)
    spec_bytes = decode_capture(envelope['spec_bytes_base64'], MAX_JSON)
    reader.spec_hash = digest(spec_bytes)
    spec = parse_json(spec_bytes)
    check_schema(local_schema(reader, 'delegation-task.schema.json'), spec, 'spec', Draft7Validator, Registry)
    spec_path = envelope['spec_path']
    if not reader.allowed(spec_path, authority['read_grants']):
        refuse('READ_NOT_AUTHORIZED', 'inline_spec')
    reader.captures[reader.norm(spec_path)] = spec_bytes
    needed = {reader.norm(item['path']) for item in spec['instruction_sources'] if 'path' in item}
    needed.update(reader.norm(item['path']) for item in spec['resources'])
    supplied = set()
    total_decoded = len(spec_bytes)
    for capture in envelope['captures']:
        key = reader.norm(capture['path'])
        if key in reader.captures or key in supplied:
            refuse('DUPLICATE_CAPTURE_PATH', 'inline_captures')
        if key not in needed or not reader.allowed(capture['path'], authority['read_grants']):
            refuse('CAPTURE_NOT_AUTHORIZED_OR_NEEDED', 'inline_captures')
        raw = decode_capture(capture['bytes_base64'], MAX_FILE)
        total_decoded += len(raw)
        if total_decoded > MAX_INLINE:
            refuse('CAPTURE_BYTE_BUDGET', 'inline_captures')
        reader.captures[key] = raw
        supplied.add(key)
    if supplied != needed:
        refuse('CAPTURE_BYTES_MISSING', 'inline_captures')
    reader.runtime_lock = decode_capture(envelope['runtime_lock_bytes_base64'], MAX_FILE)
    if total_decoded + len(reader.runtime_lock) > MAX_INLINE:
        refuse('CAPTURE_BYTE_BUDGET', 'inline_captures')
    observed_hash = run(spec_path, raw_authority, reader, checks)
    return reader, observed_hash


def read_inline_frame(fd):
    # Length framing avoids waiting for EOF after a complete portable request.
    # Consume one frame only; trailing stream bytes are not part of that frame.
    header = b''
    while len(header) < 16:
        byte = os.read(fd, 1)
        if not byte:
            refuse('INLINE_FRAME_TRUNCATED', 'inline_transport', True)
        if byte == b'\n':
            break
        header += byte
    else:
        refuse('INLINE_FRAME_HEADER', 'inline_transport', True)
    if not re.fullmatch(b'[1-9][0-9]*', header):
        refuse('INLINE_FRAME_HEADER', 'inline_transport', True)
    size = int(header)
    if size > MAX_INLINE:
        refuse('INLINE_FRAME_SIZE', 'inline_transport', True)
    chunks, remaining = [], size
    while remaining:
        part = os.read(fd, min(65536, remaining))
        if not part:
            refuse('INLINE_FRAME_TRUNCATED', 'inline_transport', True)
        chunks.append(part)
        remaining -= len(part)
    return b''.join(chunks)



class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        refuse('INVALID_ARGUMENTS', 'cli', True)


def main():
    reader = None
    checks = {key: False for key in ['schema', 'authority', 'runtime_lock', 'sources', 'references', 'scopes', 'resources', 'stability']}
    output = {'result_version': 'lead-task-spec-check/v1', 'mode': 'file-posix', 'result': 'error', 'spec_sha256': None, 'checks': checks,
              'physical_scope_status': 'not_completed', 'file_stability_status': 'not_completed',
              'deadline_mode': 'not_started', 'capture_provenance': 'not_applicable',
              'semantic_completeness': 'not_established', 'violations': [], 'read_file_count': 0, 'capture_check_count': 0}
    exit_code, force_exit = 2, False
    try:
        parser = QuietParser(description=__doc__)
        parser.add_argument('--mode', choices=['file-posix', 'inline'], default='file-posix')
        parser.add_argument('--spec', help='Exact authorized file, only in file-posix mode. Inline mode accepts one length-framed envelope on stdin.')
        args = parser.parse_args()
        output['mode'] = args.mode
        if args.mode == 'inline':
            if args.spec:
                refuse('INVALID_ARGUMENTS', 'inline_cli', True)
            output.update(physical_scope_status='not_checked_inline', file_stability_status='not_checked_inline',
                          deadline_mode='thread-watchdog', capture_provenance='caller_supplied_not_authenticated')
            if os.name == 'nt':
                import msvcrt
                msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            event, holder = threading.Event(), {}
            def job():
                try:
                    raw = read_inline_frame(sys.stdin.fileno())
                    holder['reader'], holder['hash'] = run_inline(raw, checks, holder)
                except BaseException as exc:
                    holder['error'] = exc
                finally:
                    event.set()
            threading.Thread(target=job, daemon=True).start()
            if not event.wait(MAX_SECONDS):
                reader = holder.get('reader')
                force_exit = True
                refuse('CHECK_TIME_BUDGET', 'inline_transport', True)
            reader = holder.get('reader')
            if 'error' in holder:
                raise holder['error']
            output['spec_sha256'] = holder['hash']
        else:
            if not args.spec:
                refuse('INVALID_ARGUMENTS', 'file_cli', True)
            if not hasattr(signal, 'setitimer') or not hasattr(signal, 'SIGALRM') or os.name != 'posix':
                refuse('FILE_MODE_REQUIRES_POSIX', 'runtime', True)
            signal.signal(signal.SIGALRM, lambda *_: refuse('CHECK_TIME_BUDGET', 'limits', True))
            signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
            output['deadline_mode'] = 'signal'
            reader = Reader()
            raw = sys.stdin.buffer.read(MAX_JSON + 1)
            if not raw or len(raw) > MAX_JSON:
                refuse('AUTHORITY_SIZE_INVALID', 'authority', True)
            output['spec_sha256'] = run(args.spec, raw, reader, checks)
            output.update(physical_scope_status='verified_existing_paths', file_stability_status='verified')
        output['result'], exit_code = 'pass', 0
    except Refused as exc:
        output['result'] = 'error' if exc.invocation else 'fail'
        output['violations'] = [{'code': exc.code, 'subject': exc.subject}]
        exit_code = 2 if exc.invocation else 1
    except Exception:
        output['violations'] = [{'code': 'CHECKER_ERROR', 'subject': 'checker'}]
    if hasattr(signal, 'setitimer'):
        signal.setitimer(signal.ITIMER_REAL, 0)
    if reader is not None:
        output['spec_sha256'] = reader.spec_hash
        output['read_file_count'] = reader.read_count
        output['capture_check_count'] = getattr(reader, 'capture_checks', 0)
    sys.stdout.write(json.dumps(output, ensure_ascii=False, sort_keys=True) + '\n')
    sys.stdout.flush()
    if force_exit:
        # End only this checker process; do not let a blocked daemon stdin read
        # delay interpreter shutdown. No external process is signalled.
        os._exit(exit_code)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
