"""Publish verified migration copies through the running app that owns the store.

This module never deletes conversation files or writes the live summary cache.
Move means publish the target and archive the source through the native API.
"""

import hashlib
import json
import os
import re
import sqlite3
import ssl
import time
import urllib.request
import uuid
from pathlib import Path


def _identifier(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('Invalid conversation identifier')
    return value


def _readonly(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('Expected a database file')
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)


def _tables(connection):
    def quoted(name):
        return '"' + name.replace('"', '""') + '"'
    return {
        row[0]: tuple(column[1] for column in connection.execute(
            'PRAGMA table_info(' + quoted(row[0]) + ')'))
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    }


def _signature(path):
    """Match migration_engine's logical signature, including committed WAL rows."""
    connection = _readonly(path)
    try:
        connection.execute('BEGIN')
        digest = hashlib.sha256()
        for name, columns in sorted(_tables(connection).items()):
            digest.update(repr((name, columns)).encode('utf-8'))
            table = '"' + name.replace('"', '""') + '"'
            for row in sorted(connection.execute('SELECT * FROM ' + table).fetchall(), key=repr):
                digest.update(repr(row).encode('utf-8'))
                digest.update(b'\n')
        return digest.hexdigest()
    finally:
        connection.close()


def _varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _bytes_field(number, value):
    return _varint((number << 3) | 2) + _varint(len(value)) + value


def _fields(data):
    if not isinstance(data, bytes):
        raise ValueError('Expected protobuf bytes')
    position = 0

    def read_varint():
        nonlocal position
        value = 0
        for shift in range(0, 70, 7):
            if position >= len(data):
                raise ValueError('Truncated protobuf field')
            byte = data[position]
            position += 1
            if shift == 63 and byte > 1:
                raise ValueError('Oversized protobuf integer')
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError('Oversized protobuf integer')

    result = {}
    while position < len(data):
        key = read_varint()
        number, wire = key >> 3, key & 7
        if number < 1 or number > 536870911:
            raise ValueError('Invalid protobuf field number')
        if wire == 0:
            value = read_varint()
        elif wire in (1, 2, 5):
            size = read_varint() if wire == 2 else (8 if wire == 1 else 4)
            if position + size > len(data):
                raise ValueError('Truncated protobuf field')
            value = data[position:position + size]
            position += size
        else:
            raise ValueError('Unsupported protobuf wire type')
        if number in (4, 15) and number in result:
            raise ValueError('Repeated identity or annotation field')
        result[number] = (wire, value)
    return result


def _trajectory_id(raw):
    wire, value = _fields(raw).get(4, (None, None))
    if wire != 2:
        raise ValueError('Summary has no trajectory identifier')
    return _identifier(value.decode('ascii'))


def _windows_process_session_id(pid):
    """Read the Windows logon session without sending any process control request."""
    import ctypes
    from ctypes import wintypes
    session = wintypes.DWORD()
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    query = kernel32.ProcessIdToSessionId
    query.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    query.restype = wintypes.BOOL
    if not query(int(pid), ctypes.byref(session)):
        raise OSError(ctypes.get_last_error(), 'Cannot establish process session ownership')
    return int(session.value)


class _NativeOwner:
    """An authenticated loopback connection to the primary running native engine."""

    def __init__(self):
        import psutil
        current_user = psutil.Process().username()
        if not isinstance(current_user,str) or not current_user.strip():
            raise RuntimeError('Current Windows user ownership is unavailable')
        self.owner_user = current_user.casefold()
        self.owner_session = _windows_process_session_id(os.getpid())
        if not isinstance(self.owner_session,int) or self.owner_session < 0:
            raise RuntimeError('Current Windows session ownership is unavailable')
        roots = []
        for variable, suffix in [('LOCALAPPDATA', ('Programs', 'antigravity')),
                                 ('ProgramFiles', ('Antigravity',)),
                                 ('ProgramFiles(x86)', ('Antigravity',))]:
            base = os.environ.get(variable)
            if base:
                roots.append(Path(base).joinpath(*suffix))
        expected = {os.path.normcase(str(root / 'resources' / 'bin' / 'language_server.exe'))
                    for root in roots}
        matches = []
        for process in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'username']):
            info = process.info
            if (info.get('name') or '').lower() != 'language_server.exe':
                continue
            process_user = info.get('username')
            if not info.get('exe'):
                if isinstance(process_user,str) and process_user.strip() and process_user.casefold() != self.owner_user:
                    continue
                raise RuntimeError('Native engine executable ownership is unavailable')
            if os.path.normcase(info.get('exe')) not in expected:
                continue
            if not isinstance(process_user,str) or not process_user.strip():
                raise RuntimeError('Native engine user ownership is unavailable')
            if process_user.casefold() != self.owner_user:
                continue
            process_session = _windows_process_session_id(process.pid)
            if not isinstance(process_session,int) or process_session < 0:
                raise RuntimeError('Native engine session ownership is unavailable')
            arguments = info.get('cmdline')
            if not isinstance(arguments,(list,tuple)) or not arguments:
                raise RuntimeError('Native engine profile ownership is unavailable')
            if self._argument(arguments, '--app_data_dir') == 'antigravity':
                # Sessions of the same Windows user share the primary store.
                # Do not publish while another session can write that store.
                if process_session != self.owner_session:
                    raise RuntimeError('Primary native store is owned by another session of this user')
                matches.append((process, arguments))
        if len(matches) != 1:
            raise RuntimeError('A single primary Antigravity engine must be running')
        self.process, arguments = matches[0]
        self.created = self.process.create_time()
        self.csrf = self._argument(arguments, '--csrf_token')
        if not self.csrf:
            raise RuntimeError('Native engine authentication is unavailable')
        self.store = Path.home() / '.gemini' / 'antigravity'
        self.conversations_dir = self.store / 'conversations'
        roaming = os.environ.get('APPDATA')
        if not roaming:
            raise RuntimeError('Native engine log location is unavailable')
        log = Path(roaming) / 'Antigravity' / 'logs' / 'language_server.log'
        ports = re.findall(r'listening on .*? port at (\d+) for HTTPS', log.read_text('utf-8'))
        if not ports:
            raise RuntimeError('Native engine HTTPS port is unavailable')
        self.port = int(ports[-1])
        self.context = ssl._create_unverified_context()
        # Ignore environment proxies for this authenticated loopback-only channel.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=self.context))
        self._check_owner()

    @staticmethod
    def _argument(arguments, name):
        for index, argument in enumerate(arguments):
            if argument == name and index + 1 < len(arguments):
                return arguments[index + 1]
            if argument.startswith(name + '='):
                return argument.split('=', 1)[1]
        return None

    def _check_owner(self):
        if not self.process.is_running() or self.process.create_time() != self.created:
            raise RuntimeError('Native engine changed during migration')
        process_user = self.process.username()
        if not isinstance(process_user,str) or process_user.casefold() != self.owner_user:
            raise RuntimeError('Native engine user ownership changed during migration')
        process_session = _windows_process_session_id(self.process.pid)
        if not isinstance(process_session,int) or process_session != self.owner_session:
            raise RuntimeError('Native engine session ownership changed during migration')
        listening = {connection.laddr.port for connection in self.process.net_connections(kind='tcp')
                     if connection.status == 'LISTEN' and connection.laddr}
        if self.port not in listening:
            raise RuntimeError('Native engine no longer owns the selected port')

    def _request(self, method, payload, content_type='application/json', timeout=15):
        allowed = {'WaitForConversationFullyIdle', 'GetConversationMetadata',
                   'JetboxWriteSummary', 'UpdateConversationAnnotations'}
        if method not in allowed:
            raise ValueError('Unsupported migration operation')
        self._check_owner()
        request = urllib.request.Request(
            f'https://127.0.0.1:{self.port}/exa.language_server_pb.LanguageServerService/{method}',
            data=payload, headers={'Content-Type': content_type,
                                   'Connect-Protocol-Version': '1',
                                   'x-codeium-csrf-token': self.csrf})
        with self.opener.open(request, timeout=timeout) as response:
            result = response.read(8 * 1024 * 1024 + 1)
            if len(result) > 8 * 1024 * 1024:
                raise RuntimeError('Native migration response exceeds its size limit')
        self._check_owner()
        return result

    def _json(self, method, payload):
        return json.loads(self._request(method, json.dumps(payload).encode('utf-8')))

    def wait_idle(self, cid):
        result = self._json('WaitForConversationFullyIdle', {
            'conversationId': cid, 'inactivityTimeoutSeconds': 1,
            'stabilizationDurationSeconds': 1, 'returnOnExecutorError': True})
        return not result.get('timedOut', False)

    def publish(self, cid, raw):
        self._request('JetboxWriteSummary',
                      _bytes_field(1, cid.encode()) + _bytes_field(2, raw),
                      'application/proto')

    def metadata(self, cid):
        return self._json('GetConversationMetadata', {'conversationId': cid})

    def archived(self, cid):
        connection = _readonly(self.store / 'conversation_summaries.db')
        try:
            row = connection.execute(
                'SELECT raw_summary FROM conversation_summaries WHERE conversation_id=?',
                (cid,)).fetchone()
            if row is None:
                raise ValueError('Native conversation summary is missing')
            annotations = _fields(row[0]).get(15, (2, b''))
            if annotations[0] != 2:
                raise ValueError('Malformed native annotations')
            archived = _fields(annotations[1]).get(4, (0, 0))
            if archived[0] != 0:
                raise ValueError('Malformed native archival state')
            return bool(archived[1])
        finally:
            connection.close()

    def archive(self, cid, value=True):
        seconds, nanos = divmod(time.time_ns(), 1000000000)
        timestamp = (_varint(8) + _varint(seconds)
                     + _varint(16) + _varint(nanos))
        annotations = _varint(32) + _varint(int(value)) + _bytes_field(5, timestamp)
        payload = (_bytes_field(1, cid.encode()) + _bytes_field(2, annotations)
                   + _varint(24) + _varint(1))
        self._request('UpdateConversationAnnotations', payload, 'application/proto')


def _validate_target(record, directory):
    cid = _identifier(record['target_id'])
    path = Path(record['db_path']).resolve(strict=True)
    if path.name != cid + '.db' or path.parent != directory:
        raise ValueError('Target is outside the native conversation store')
    expected = record['expected_step_count']
    if type(expected) is not int or expected < 0:
        raise ValueError('Invalid target step count')
    tid = _identifier(record['trajectory_id'])
    raw = record['summary']['raw_summary']
    if _trajectory_id(raw) != tid:
        raise ValueError('Target summary identity is inconsistent')
    connection = _readonly(path)
    try:
        connection.execute('BEGIN')
        if connection.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('Target database is malformed')
        if connection.execute('SELECT trajectory_id,cascade_id FROM trajectory_meta').fetchall() != [(tid, cid)]:
            raise ValueError('Target database identity is inconsistent')
        if connection.execute('SELECT count(*) FROM steps').fetchone()[0] != expected:
            raise ValueError('Target step count changed')
        if 'expected_counts' in record:
            counts = {name: connection.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                      for name in _tables(connection)}
            if counts != record['expected_counts']:
                raise ValueError('Target ancillary rows changed')
    finally:
        connection.close()


def _journal(path, state):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(state, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _wait_archival(owner, cid, value):
    # Native summary persistence may finish just after the annotation RPC.
    for attempt in range(21):
        if owner.archived(cid) is value:
            return True
        if attempt < 20:
            time.sleep(0.05)
    return False


def _verify_sources(owner, directory, signatures):
    for cid, signature in signatures.items():
        if not owner.wait_idle(cid) or _signature(directory / (cid + '.db')) != signature:
            raise RuntimeError('Source became active or changed during native migration')


def commit_migration(records, source_ids, mode, backup_path):
    """Commit a fully built batch; retain every source file, even on failure."""
    state = {'phase': 'preflight', 'published_ids': [], 'publication_attempted': [],
             'sources_archived': [], 'archival_attempted': [],
             'sources_restored': [], 'rollback_errors': []}
    owner = None
    journal = None
    old_archival = {}
    try:
        if mode not in ('copy', 'move') or not records or not source_ids:
            raise ValueError('Invalid migration batch')
        source_ids = [_identifier(cid) for cid in source_ids]
        targets = [_identifier(record['target_id']) for record in records]
        if len(set(source_ids)) != len(source_ids) or len(set(targets)) != len(targets) or set(source_ids) & set(targets):
            raise ValueError('Migration source and target identities must be distinct')
        backup = Path(backup_path).resolve(strict=True)
        if not backup.is_dir():
            raise ValueError('Migration backup directory is missing')
        expected_signatures = {}
        for record in records:
            for cid, signature in record['source_signatures'].items():
                _identifier(cid)
                if not isinstance(signature, str) or not re.fullmatch(r'[0-9a-f]{64}', signature):
                    raise ValueError('Invalid source signature')
                if cid in expected_signatures and expected_signatures[cid] != signature:
                    raise ValueError('Migration uses different snapshots of one source')
                expected_signatures[cid] = signature
        if set(expected_signatures) != set(source_ids):
            raise ValueError('Source signature coverage is incomplete')
        for cid in source_ids:
            if _signature(backup / (cid + '.db')) != expected_signatures[cid]:
                raise ValueError('Migration backup does not match its source snapshot')
        owner = _NativeOwner()
        directory = Path(owner.conversations_dir).resolve(strict=True)
        for record in records:
            _validate_target(record, directory)
        for cid in source_ids:
            if not owner.wait_idle(cid):
                raise RuntimeError('Source conversation is still active; migration was not committed')
            if _signature(directory / (cid + '.db')) != expected_signatures[cid]:
                raise RuntimeError('Source changed since the migration snapshot')
            if mode == 'move':
                old_archival[cid] = owner.archived(cid)
                if type(old_archival[cid]) is not bool:
                    raise ValueError('Native archival state is not a boolean')
        journal = backup / ('native-commit-' + uuid.uuid4().hex + '.json')
        state.update(mode=mode, source_ids=source_ids, target_ids=targets, phase='publishing')
        _journal(journal, state)
        for record in records:
            cid = record['target_id']
            state['publication_attempted'].append(cid)
            _journal(journal, state)
            owner.publish(cid, record['summary']['raw_summary'])
            native = owner.metadata(cid)
            if (native.get('trajectoryId') != record['trajectory_id']
                    or native.get('numSteps', 0) != record['expected_step_count']):
                raise RuntimeError('Native owner did not verify the target identity and step count')
            state['published_ids'].append(cid)
            _journal(journal, state)
        _verify_sources(owner, directory, expected_signatures)
        if mode == 'move':
            state['phase'] = 'archiving'
            for cid in source_ids:
                _verify_sources(owner, directory, expected_signatures)
                state['archival_attempted'].append(cid)
                _journal(journal, state)
                owner.archive(cid)
                if not _wait_archival(owner, cid, True):
                    raise RuntimeError('Native owner did not confirm source archival')
                state['sources_archived'].append(cid)
                _journal(journal, state)
                _verify_sources(owner, directory, expected_signatures)
        state['phase'] = 'committed'
        _journal(journal, state)
        return {'success': True, 'published_ids': state['published_ids'],
                'sources_archived': state['sources_archived'],
                'source_action': 'archived' if mode == 'move' else 'files_retained',
                'journal_path': str(journal)}
    except Exception as error:
        # A request can apply before its response fails. Restore all attempted
        # source annotations; leave copied data and original files intact.
        if owner is not None:
            for cid in reversed(state['archival_attempted']):
                try:
                    owner.archive(cid, old_archival[cid])
                    if not _wait_archival(owner, cid, old_archival[cid]):
                        raise RuntimeError('Native owner did not confirm archival rollback')
                    state['sources_restored'].append(cid)
                except Exception:
                    state['rollback_errors'].append(cid)
        state['sources_archived'] = [cid for cid in state['sources_archived']
                                     if cid not in state['sources_restored']]
        state['phase'] = 'failed'
        state['error'] = str(error)
        if journal is not None:
            try:
                _journal(journal, state)
            except OSError:
                state['journal_write_failed'] = True
        return {'success': False, 'error': str(error),
                'published_ids': state['published_ids'],
                'pending_target_ids': state['publication_attempted'],
                'sources_archived': state['sources_archived'],
                'archival_status': ('unconfirmed' if state['rollback_errors'] else
                                    'rolled_back' if state['archival_attempted'] else 'not_started'),
                'source_files_retained': True, 'rollback_errors': state['rollback_errors'],
                'journal_path': str(journal) if journal is not None else None}
