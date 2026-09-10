#!/usr/bin/env python3
"""Prepare an immutable delegation input, not an authorization or execution verifier.

Every input path and expected digest must be explicitly passed by an authorized
caller. Embedded paths are never followed. POSIX safe file operations are required.
No network, dependencies, interpreter discovery, checker execution or delegation.
"""
import argparse
import errno
import hashlib
import json
import os
import stat
import sys

LIMIT = 256 * 1024
ROLES = ('lead', 'requirements', 'commercial', 'visual', 'evidence')

# Only these fixed labels can leave the process on failure. Never serialize an
# exception message, filename, JSON key/value, digest or caller argument.
ERROR_CODES = frozenset('''DUPLICATE_JSON_KEY INVALID_TEXT NON_FINITE_JSON JSON_LIMIT
OBJECT_REQUIRED SAFE_IO_UNAVAILABLE ABSOLUTE_PATH_REQUIRED UNSAFE_PATH
INVALID_EXPECTED_HASH UNSAFE_FILE INPUT_TOO_LARGE INPUT_CHANGED HASH_MISMATCH
TARGET_REQUIRED EMPTY_REQUEST ASSIGNMENT_FIELDS ROLE_TASK_REQUIRED RESOURCES_REQUIRED
IO_SCOPE_REQUIRED LEAD_BRANCH_FIELDS SPEC_REQUIRED SPEC_VERSION SPEC_ID SPEC_REVISION
REQUEST_SPEC_MISMATCH METADATA_BRANCH_FIELDS AUTHORITY_SPEC_MISMATCH
AUTHORITY_BINDING_MISMATCH AUTHORITY_REQUEST_MISMATCH BUSINESS_BRANCH_FIELDS
TARGET_MISMATCH ASSIGNMENT_SPEC_MISMATCH PREFLIGHT_SPEC_MISMATCH PREFLIGHT_NOT_PASS
PREFLIGHT_CHECKS PREFLIGHT_STATUS PREFLIGHT_MODE EMPTY_EXECUTION_RECEIPT
OUTPUT_TOO_LARGE UNSAFE_OUTPUT_NAME OUTPUT_DIRECTORY_CHANGED OUTPUT_FILE_CHANGED
OUTPUT_BYTES_CHANGED OUTPUT_WRITE_FAILED ARGUMENTS_INVALID'''.split())
ERROR_SLOTS = frozenset(('arguments', 'target_agent_id', 'kind', 'role', 'request',
                         'assignment', 'spec', 'authority', 'preflight',
                         'execution_receipt', 'output', 'output_name',
                         'output_directory', 'output_task', 'output_manifest'))


def refusal(error, slot):
    """Bounded diagnostic labels only; refusal and partial-file policy unchanged."""
    code = 'INVALID_STRUCTURE'
    if isinstance(error, UnicodeError):
        code = 'INVALID_TEXT'
    elif isinstance(error, json.JSONDecodeError):
        code = 'INVALID_JSON'
    elif isinstance(error, RecursionError):
        code = 'JSON_LIMIT'
    elif isinstance(error, OSError):
        code = {errno.ENOENT: 'PATH_NOT_FOUND', errno.EEXIST: 'OUTPUT_EXISTS',
                errno.EACCES: 'ACCESS_REFUSED', errno.EPERM: 'ACCESS_REFUSED',
                errno.ELOOP: 'UNSAFE_PATH', errno.ENOTDIR: 'UNSAFE_PATH'}.get(
                    error.errno, 'IO_ERROR')
    elif (type(error) is ValueError and len(error.args) == 1
          and isinstance(error.args[0], str) and error.args[0] in ERROR_CODES):
        code = error.args[0]
    return {'result': 'error', 'code': 'PREPARATION_REFUSED', 'reason_code': code,
            'slot': slot if slot in ERROR_SLOTS else 'arguments',
            'partial_output_policy': 'preserved_if_created'}


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes invalid caller-supplied values to stderr.
        raise ValueError('ARGUMENTS_INVALID')


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hex_digest(value):
    return len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def decode(data):
    require(not data.startswith(b'\xef\xbb\xbf') and b'\x00' not in data, 'INVALID_TEXT')
    return data.decode('utf-8', errors='strict')


def parse(text):
    def invalid(_):
        raise ValueError('NON_FINITE_JSON')
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
    stack = [(value, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        require(count <= 20000 and depth <= 32, 'JSON_LIMIT')
        if isinstance(item, float):
            require(item == item and abs(item) != float('inf'), 'NON_FINITE_JSON')
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)
    require(isinstance(value, dict), 'OBJECT_REQUIRED')
    return value


def directory(path):
    require(os.name == 'posix' and all(hasattr(os, x) for x in
            ('O_NOFOLLOW', 'O_DIRECTORY', 'O_NONBLOCK')), 'SAFE_IO_UNAVAILABLE')
    require(path.startswith('/') and not path.startswith('//'), 'ABSOLUTE_PATH_REQUIRED')
    parts = path.split('/')[1:]
    require(all(p and p not in ('.', '..') for p in parts) or path == '/', 'UNSAFE_PATH')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in ([] if path == '/' else parts):
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=fd)
            os.close(fd)
            fd = new
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_bound(pair):
    path, expected = pair
    require(hex_digest(expected), 'INVALID_EXPECTED_HASH')
    parent, name = os.path.split(path)
    require(name not in ('', '.', '..'), 'UNSAFE_PATH')
    parent_fd = directory(parent)
    fd = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'UNSAFE_FILE')
        require(before.st_size <= LIMIT, 'INPUT_TOO_LARGE')
        data = b''
        while len(data) <= LIMIT:
            chunk = os.read(fd, min(65536, LIMIT + 1 - len(data)))
            if not chunk:
                break
            data += chunk
        after = os.fstat(fd)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(identity(before) == identity(after) == identity(current), 'INPUT_CHANGED')
        require(len(data) <= LIMIT and len(data) == before.st_size, 'INPUT_TOO_LARGE')
        require(digest(data) == expected, 'HASH_MISMATCH')
        return {'path': path, 'sha256': expected, 'byte_length': len(data)}, decode(data)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent_fd)


def prepare(args, diagnostics=None):
    diagnostics = {} if diagnostics is None else diagnostics
    diagnostics['slot'] = 'target_agent_id'
    require(bool(args.target_agent_id.strip()), 'TARGET_REQUIRED')
    diagnostics['slot'] = 'request'
    request_ref, text = read_bound(args.request)
    require(bool(text.strip()), 'EMPTY_REQUEST')
    diagnostics['slot'] = 'assignment'
    assignment_ref, assignment_text = read_bound(args.assignment)
    assignment = parse(assignment_text)
    required = {'role_task', 'io_scope', 'resources', 'parent_plan', 'delivery_requirements'}
    require(set(assignment) == required, 'ASSIGNMENT_FIELDS')
    require(isinstance(assignment['role_task'], str) and assignment['role_task'].strip(), 'ROLE_TASK_REQUIRED')
    require(isinstance(assignment['resources'], list), 'RESOURCES_REQUIRED')
    require(isinstance(assignment['io_scope'], dict), 'IO_SCOPE_REQUIRED')
    refs = {'request': request_ref, 'assignment': assignment_ref}
    value = {'protocol': 'tender-delegation-input/v1', 'kind': args.kind,
             'role': args.role, 'target_agent_id': args.target_agent_id,
             'original_request': dict(request_ref, text=text), 'assignment': assignment}
    if args.kind == 'lead-request':
        diagnostics['slot'] = 'kind'
        require(args.role == 'lead' and not any((args.spec, args.preflight, args.execution_receipt, args.authority)), 'LEAD_BRANCH_FIELDS')
    else:
        diagnostics['slot'] = 'spec'
        require(args.spec is not None, 'SPEC_REQUIRED')
        spec_ref, spec_text = read_bound(args.spec)
        spec = parse(spec_text)
        require(spec.get('spec_version') == 'lead-delegation-task/v1', 'SPEC_VERSION')
        require(isinstance(spec.get('task_id'), str) and bool(spec['task_id']), 'SPEC_ID')
        require(type(spec.get('revision')) is int and spec['revision'] >= 1, 'SPEC_REVISION')
        matches = [s for s in spec.get('instruction_sources', []) if
                   isinstance(s, dict) and s.get('sha256') == request_ref['sha256'] and
                   (s.get('text') == text or s.get('path') == request_ref['path'])]
        require(bool(matches), 'REQUEST_SPEC_MISMATCH')
        value['task_spec'] = dict(spec_ref, task_id=spec['task_id'], revision=spec['revision'], value=spec)
        refs['spec'] = spec_ref
        if args.kind == 'metadata-preflight':
            diagnostics['slot'] = 'authority' if not args.authority else 'kind'
            require(args.role == 'evidence' and args.authority and not args.preflight and not args.execution_receipt, 'METADATA_BRANCH_FIELDS')
            diagnostics['slot'] = 'authority'
            authority_ref, authority_text = read_bound(args.authority)
            authority = parse(authority_text)
            require(authority.get('spec_sha256') == spec_ref['sha256'], 'AUTHORITY_SPEC_MISMATCH')
            for key in ('task_id', 'revision', 'target_agent_id', 'parent_plan'):
                require(authority.get(key) == spec.get(key), 'AUTHORITY_BINDING_MISMATCH')
            source_ids = {item.get('source_id') for item in matches}
            require(any(isinstance(item, dict) and item.get('source_id') in source_ids and
                        item.get('text') == text for item in authority.get('instruction_sources', [])),
                    'AUTHORITY_REQUEST_MISMATCH')
            # Preserve complete independently supplied bytes as data; the existing checker
            # remains the authority/TaskSpec validator and receives these original bytes.
            value['authority'] = dict(authority_ref, text=authority_text)
            refs['authority'] = authority_ref
        else:
            diagnostics['slot'] = ('preflight' if not args.preflight else
                                   'execution_receipt' if not args.execution_receipt else 'kind')
            require(args.role != 'lead' and args.preflight and args.execution_receipt and not args.authority, 'BUSINESS_BRANCH_FIELDS')
            diagnostics['slot'] = 'target_agent_id'
            require(spec.get('target_agent_id') == value['target_agent_id'], 'TARGET_MISMATCH')
            diagnostics['slot'] = 'assignment'
            for key in ('io_scope', 'resources', 'parent_plan', 'delivery_requirements'):
                require(assignment[key] == spec.get(key), 'ASSIGNMENT_SPEC_MISMATCH')
            diagnostics['slot'] = 'preflight'
            result_ref, result_text = read_bound(args.preflight)
            result = parse(result_text)
            require(result.get('result_version') == 'lead-task-spec-check/v1' and
                    result.get('spec_sha256') == spec_ref['sha256'], 'PREFLIGHT_SPEC_MISMATCH')
            require(result.get('result') == 'pass' and result.get('violations') == [] and
                    result.get('semantic_completeness') == 'not_established', 'PREFLIGHT_NOT_PASS')
            check_keys = {'schema', 'authority', 'runtime_lock', 'sources', 'references', 'scopes', 'resources', 'stability'}
            require(isinstance(result.get('checks'), dict) and set(result['checks']) == check_keys and
                    all(v is True for v in result['checks'].values()), 'PREFLIGHT_CHECKS')
            if result.get('mode') == 'file-posix':
                require(result.get('physical_scope_status') == 'verified_existing_paths' and
                        result.get('file_stability_status') == 'verified', 'PREFLIGHT_STATUS')
            elif result.get('mode') == 'inline':
                require(result.get('physical_scope_status') == 'not_checked_inline' and
                        result.get('file_stability_status') == 'not_checked_inline' and
                        result.get('capture_provenance') == 'caller_supplied_not_authenticated', 'PREFLIGHT_STATUS')
            else:
                raise ValueError('PREFLIGHT_MODE')
            diagnostics['slot'] = 'execution_receipt'
            receipt_ref, receipt_text = read_bound(args.execution_receipt)
            require(bool(receipt_text.strip()), 'EMPTY_EXECUTION_RECEIPT')
            value['preflight'] = dict(result_ref, value=result, execution_receipt=receipt_ref)
            refs.update(preflight=result_ref, execution_receipt=receipt_ref)
    diagnostics['slot'] = 'output'
    payload = (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')
    require(len(payload) <= LIMIT, 'OUTPUT_TOO_LARGE')
    # Verify every explicit source again before exclusive publication. This narrows the
    # race, not an atomic multi-file snapshot or proof of caller authorization.
    for slot, ref in refs.items():
        diagnostics['slot'] = slot
        read_bound((ref['path'], ref['sha256']))
    diagnostics['slot'] = 'output_name'
    name = args.output_name
    require(1 <= len(name) <= 80 and name[0].isalnum() and
            all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name),
            'UNSAFE_OUTPUT_NAME')
    # The directory must already exist and be independently authorized. mkdir does
    # not return an inode, so we deliberately do not create a directory then guess
    # whether a later open reached the directory we created.
    diagnostics['slot'] = 'output_directory'
    fd = directory(args.output_directory)
    opened = []
    manifest = {'protocol': 'tender-delegation-input-manifest/v1', 'inputs': refs,
                'taskSource': {'path': args.output_directory.rstrip('/') + '/' + name + '.task.json',
                               'expectedSha256': digest(payload)},
                'byte_length': len(payload), 'execution_authenticity': 'not_established'}
    def directory_identity():
        diagnostics['slot'] = 'output_directory'
        current = directory(args.output_directory)
        try:
            expected, observed = os.fstat(fd), os.fstat(current)
            require((expected.st_dev, expected.st_ino) == (observed.st_dev, observed.st_ino),
                    'OUTPUT_DIRECTORY_CHANGED')
        finally:
            os.close(current)
    def verify_outputs():
        directory_identity()
        for filename, out, content in opened:
            diagnostics['slot'] = 'output_task' if filename == name + '.task.json' else 'output_manifest'
            expected = os.fstat(out)
            observed = os.stat(filename, dir_fd=fd, follow_symlinks=False)
            identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_nlink)
            require(stat.S_ISREG(observed.st_mode) and expected.st_nlink == 1 and
                    identity(expected) == identity(observed), 'OUTPUT_FILE_CHANGED')
            os.lseek(out, 0, os.SEEK_SET)
            observed_bytes = b''
            while len(observed_bytes) <= len(content):
                part = os.read(out, min(65536, len(content) + 1 - len(observed_bytes)))
                if not part:
                    break
                observed_bytes += part
            require(observed_bytes == content, 'OUTPUT_BYTES_CHANGED')
        directory_identity()
    try:
        for filename, content in [(name + '.task.json', payload),
                                  (name + '.manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))]:
            verify_outputs()
            diagnostics['slot'] = 'output_task' if filename == name + '.task.json' else 'output_manifest'
            # Creation and acquisition of this file identity are one O_EXCL open.
            # Both descriptors stay open until the final path and byte checks.
            out = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=fd)
            opened.append((filename, out, content))
            offset = 0
            while offset < len(content):
                written = os.write(out, content[offset:])
                require(written > 0, 'OUTPUT_WRITE_FAILED')
                offset += written
            os.fsync(out)
            verify_outputs()
        diagnostics['slot'] = 'output_directory'
        os.fsync(fd)
        verify_outputs()
    finally:
        for _, out, _ in opened:
            os.close(out)
        os.close(fd)
    # A concurrent actor with the same OS rights can change these paths after
    # verification. This is not a two-file transaction or lasting tamper protection.
    return manifest


def main():
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('lead-request', 'metadata-preflight', 'business'), required=True)
    parser.add_argument('--role', choices=ROLES, required=True)
    parser.add_argument('--target-agent-id', required=True, help='Current verified target identity; never inferred from role or a development UUID.')
    for name in ('request', 'assignment', 'spec', 'preflight', 'execution-receipt', 'authority'):
        parser.add_argument('--' + name, nargs=2, metavar=('PATH', 'EXPECTED_SHA256'), required=name in ('request', 'assignment'))
    parser.add_argument('--output-directory', required=True, help='Existing explicitly authorized coordination directory. Never created by this helper.')
    parser.add_argument('--output-name', required=True, help='New simple version name (ASCII letters/digits/underscore/hyphen, max 80). Existing task or manifest files are refused.')
    diagnostics = {'slot': 'arguments'}
    try:
        result = prepare(parser.parse_args(), diagnostics)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError, KeyError, TypeError) as error:
        # No task text, source paths or exception values leak through diagnostics.
        print(json.dumps(refusal(error, diagnostics['slot'])), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
