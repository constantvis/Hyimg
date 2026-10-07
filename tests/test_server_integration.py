"""Real HTTP/process tests against disposable libraries, never the user's data."""
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def request(port, route, body=None, content='application/json', headers=None):
    if isinstance(body, dict):
        body = json.dumps(body).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{port}{route}', data=body, headers={'Content-Type': content, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def get(port, route):
    status, body = request(port, route)
    assert status == 200, body
    return json.loads(body)


@pytest.fixture
def servers(tmp_path):
    running = []

    def launch(name, *, root=None, state=None, compat=None, style=None, rules=None):
        library = root or tmp_path / name
        library.mkdir(exist_ok=True)
        port = free_port()
        project = str(uuid.uuid4())
        env = {k: v for k, v in os.environ.items() if not k.startswith(('HYIMG_', 'REVIEW_'))}
        env.update(HYIMG_LIBRARY_ROOT=str(library), HYIMG_PROJECT_ID=project, PYTHONDONTWRITEBYTECODE='1')
        # the interface in Russian: these tests check its Russian words (owner 2026-10-06: English by default, Russian by the setting)
        (tmp_path / f'{name}-settings.json').write_text(json.dumps({'cv.lang': 'ru'}))
        env['HYIMG_SETTINGS'] = str(tmp_path / f'{name}-settings.json')
        # the board's library rules: this test's own file, never the person's library-rules.json
        rules_file = tmp_path / f'{name}-rules.json'
        rules_file.write_text(json.dumps({project: rules} if rules else {}))
        env['HYIMG_LIBRARY_RULES'] = str(rules_file)
        if state:
            env['HYIMG_STATE_ROOT'] = str(state)
        if compat:
            env['HYIMG_COMPAT_PORT'] = str(compat)
        if style:
            env['HYIMG_STYLE_REFS'] = str(style)
        log = open(tmp_path / f'{name}.log', 'w+')
        process = subprocess.Popen([sys.executable, str(ROOT / 'review/server.py'), str(port)], env=env, stdout=log, stderr=log)
        running.append((process, log))
        for _ in range(100):
            if process.poll() is not None:
                break
            try:
                health = get(port, '/api/health')
                (tmp_path / f'{name}-health.json').write_text(json.dumps(health, indent=2))
                assert health == {'app': 'Hyimg', 'projectId': project, 'libraryRoot': str(library.resolve()), 'pid': process.pid, 'port': port}
                return process, port, library, log
            except (OSError, urllib.error.URLError):
                time.sleep(.05)
        log.flush()
        log.seek(0)
        return process, port, library, log

    yield launch
    for process, log in running:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        log.close()


def image_bytes(color='red'):
    output = io.BytesIO()
    Image.new('RGB', (12, 8), color).save(output, 'PNG')
    return output.getvalue()


def test_preserves_old_board_and_serves_code_html(servers, tmp_path):
    library = tmp_path / 'legacy'
    boards = library / '_review/boards'
    boards.mkdir(parents=True)
    original = b'{"schema":1,"revision":17,"items":{"old":{"path":"v1/frame.png","x":1,"y":2,"w":30,"ar":1.5,"crop":[0,0,1,1]}},"groups":{},"custom":{"preserve":true}}\n'
    (boards / 'main.json').write_bytes(original)
    (boards / 'pages.json').write_text('{"pages":[{"id":"main","title":"My board"}]}')
    (library / '_review/v2.html').write_text('STALE DATA HTML')
    before = {p.name: p.read_bytes() for p in boards.iterdir()}
    process, port, _, _ = servers('legacy-start', root=library)
    assert process.poll() is None
    assert get(port, '/api/board')['custom'] == {'preserve': True}
    assert get(port, '/api/pages')['pages'][0]['title'] == 'My board'
    for route, filename in [('/', 'v2.html'), ('/canvas', 'canvas.html'), ('/v1', 'index.html')]:
        assert request(port, route) == (200, (ROOT / 'review' / filename).read_bytes())
    assert before == {p.name: p.read_bytes() for p in boards.iterdir()}


def test_projects_upload_feedback_board_notes_history_and_restart(servers, tmp_path):
    process, port, library, _ = servers('a')
    _, second, other, _ = servers('b')
    status, body = request(port, '/api/upload?name=sample.png', image_bytes(), 'image/png')
    assert status == 200
    uploaded = json.loads(body)['path']
    assert (library / uploaded).read_bytes() == image_bytes()
    assert get(second, '/api/items') == []
    assert request(port, '/api/feedback', {'path': uploaded, 'fav': True, 'scores': {'composition': 3}, 'comment': 'Keep'})[0] == 200
    board = {'schema': 1, 'revision': 0, 'items': {'image': {'path': uploaded, 'x': 0, 'y': 0, 'w': 100, 'ar': 1.5}, 'note': {'type': 'note', 'text': 'Retain texture', 'x': 0, 'y': 0, 'w': 80, 'h': 20}}, 'groups': {}}
    code, result = request(port, '/api/board', board)
    assert code == 200, result
    assert not any(k.endswith('_error') for k in json.loads(result))
    assert (library / 'notes/main__note.json').is_file()
    assert request(port, '/api/history', {'action': 'save', 'name': 'main', 'label': 'checkpoint'})[0] == 200
    assert len(get(port, '/api/history')) >= 1
    assert request(port, '/api/live', {'src': 'canvas', 'page': 'main'})[0] == 200
    assert (library / '_review/live.json').is_file()
    assert get(second, '/api/board')['items'] == {}
    assert not (other / 'added').exists()
    saved = (library / '_review/boards/main.json').read_bytes()
    process.terminate()
    process.wait(timeout=5)
    _, reopened, _, _ = servers('reopen', root=library)
    assert (library / '_review/boards/main.json').read_bytes() == saved
    assert get(reopened, '/api/board')['items']['note']['text'] == 'Retain texture'
    assert get(reopened, '/api/items')[0]['feedback']['comment'] == 'Keep'


def test_traversal_and_symlink_escape(servers, tmp_path):
    _, port, library, _ = servers('paths')
    secret = tmp_path / 'outside.png'
    secret.write_bytes(image_bytes())
    (library / 'escape.png').symlink_to(secret)
    for path in ['../outside.png', str(secret), 'escape.png']:
        assert request(port, '/img?p=' + urllib.parse.quote(path))[0] == 404
        assert request(port, '/api/feedback', {'path': path, 'fav': True})[0] == 400
    assert request(port, '/api/board?name=../outside')[0] == 404
    assert request(port, '/api/board?name=../outside', {'items': {}})[0] == 400
    assert not secret.with_suffix('.json').exists()


def test_single_writer_and_compat_listener(servers):
    compat = free_port()
    first, port, library, _ = servers('owner', compat=compat)
    assert get(compat, '/api/health')['pid'] == first.pid
    assert get(compat, '/api/health')['port'] == compat
    duplicate, _, _, log = servers('duplicate', root=library)
    assert duplicate.wait(timeout=5) != 0
    assert 'already owns this state folder' in log.read()
    assert get(port, '/api/health')['pid'] == first.pid


def test_occupied_compat_port_does_not_start_primary(servers):
    with socket.socket() as blocker:
        blocker.bind(('127.0.0.1', 0))
        blocker.listen()
        process, port, _, log = servers('occupied', compat=blocker.getsockname()[1])
        assert process.wait(timeout=5) != 0
        assert 'Cannot bind Hyimg port' in log.read()
        with pytest.raises(urllib.error.URLError):
            request(port, '/api/health')


def test_generic_filters_and_separate_state_root(servers, tmp_path):
    state = tmp_path / 'state'
    _, port, library, _ = servers('generic', state=state)
    (library / 'cover.png').write_bytes(image_bytes())
    (library / 'pose3d').mkdir()
    (library / 'pose3d/previz-image.png').write_bytes(image_bytes())
    assert {item['name'] for item in get(port, '/api/items')} == {'cover', 'previz-image'}
    assert request(port, '/api/board', {'revision': 0, 'items': {}, 'groups': {}})[0] == 200
    assert (state / 'boards/main.json').is_file()
    assert not (library / '_review').exists()


def test_library_rules_mount_and_hide_filters(servers, tmp_path):
    # a board's own rules (library-rules.json, 2026-10-05): a folder hidden by path, intermediates by name, no files from the root,
    # an outside folder as a collection with its title
    style = tmp_path / 'styles'
    (style / 'moodboard').mkdir(parents=True)
    (style / 'moodboard/reference.png').write_bytes(image_bytes())
    library = tmp_path / 'rules-filter'
    (library / 'debug').mkdir(parents=True)
    (library / 'visible').mkdir()
    (library / 'debug/hidden.png').write_bytes(image_bytes())
    (library / 'visible/frame.png').write_bytes(image_bytes())
    (library / 'visible/_raw-crop.png').write_bytes(image_bytes())
    (library / 'cover.png').write_bytes(image_bytes())
    rules = {'hide': ['debug'], 'skipFilePrefixes': ['_raw-'], 'rootFiles': False,
             'mounts': [{'prefix': 'ext/moodboard', 'path': 'moodboard', 'title': 'Moodboard'}]}
    _, port, _, _ = servers('rules-filter-start', root=library, style=style, rules=rules)
    items = get(port, '/api/items')
    assert {item['path'] for item in items} == {'visible/frame.png', 'ext/moodboard/reference.png'}
    assert next(i['title'] for i in items if i['path'].startswith('ext/')) == 'Moodboard'
    assert request(port, '/img?p=ext/moodboard/reference.png') == (200, image_bytes())


def test_no_rules_shows_every_picture(servers, tmp_path):
    # a fresh install has no rules and no projects of anyone's: every picture under the folder is a frame, a reference folder
    # given at registration shows each of its folders as a collection
    style = tmp_path / 'refs'
    (style / 'moodboard').mkdir(parents=True)
    (style / 'moodboard/reference.png').write_bytes(image_bytes())
    library = tmp_path / 'plain'
    for n, rel in enumerate(('cover.png', 'pose3d/a.png', 'previz/b.png', 'masks-1/c.png', 'visible/_raw-d.png')):
        (library / rel).parent.mkdir(parents=True, exist_ok=True)
        (library / rel).write_bytes(image_bytes((40 * n, 0, 0)))   # unlike pictures: equal bytes are one picture
    _, port, _, _ = servers('plain-start', root=library, style=style)
    assert {item['path'] for item in get(port, '/api/items')} == {'cover.png', 'pose3d/a.png', 'previz/b.png', 'masks-1/c.png',
                                                                 'visible/_raw-d.png', 'ext/moodboard/reference.png'}
    assert get(port, '/api/taggroups') == []


def test_host_origin_guards_preserve_metadata(servers):
    compat = free_port()
    _, port, library, _ = servers('guards', compat=compat)
    code, uploaded = request(port, '/api/upload?name=guard.png', image_bytes(), 'image/png')
    assert code == 200
    path = json.loads(uploaded)['path']
    board = {'schema': 1, 'revision': 0, 'items': {'pic': {'path': path, 'x': 12, 'y': 23, 'w': 120, 'ar': 1.5, 'crop': [.1, .2, .8, .9]}}, 'groups': {}, 'removed': {'older.png': True}, 'custom': {'retain': [1, 2]}}
    assert request(port, '/api/board', board)[0] == 200
    snapshot = {str(p.relative_to(library)): p.read_bytes() for p in library.rglob('*') if p.is_file()}
    rejected = []
    for host in ['attacker.example:' + str(port), 'localhost', '127.0.0.1:' + str(compat), 'localhost.evil:' + str(port)]:
        for route in ['/api/board', '/api/items', '/api/health', '/img?p=' + path]:
            status, _ = request(port, route, headers={'Host': host})
            rejected.append({'host': host, 'route': route, 'status': status})
            assert status == 403
    for headers in [{'Origin': 'https://evil.example'}, {'Origin': 'null'}, {'Origin': f'http://localhost:{compat}'}, {'Origin': f'http://localhost:{port}/'}, {'Sec-Fetch-Site': 'cross-site'}]:
        status, _ = request(port, '/api/feedback', {'path': path, 'fav': True, 'comment': 'forbidden'}, headers=headers)
        rejected.append({'headers': headers, 'status': status})
        assert status == 403
    assert snapshot == {str(p.relative_to(library)): p.read_bytes() for p in library.rglob('*') if p.is_file()}
    for listener in [port, compat]:
        for hostname in ['localhost', '127.0.0.1']:
            headers = {'Host': f'{hostname}:{listener}', 'Origin': f'http://{hostname}:{listener}', 'Sec-Fetch-Site': 'same-origin'}
            assert request(listener, '/api/feedback', {'path': path, 'comment': 'allowed'}, headers=headers)[0] == 200
    assert get(port, '/api/board')['custom'] == {'retain': [1, 2]}
    assert get(port, '/api/board')['items']['pic']['crop'] == [.1, .2, .8, .9]
    (library.parent / 'guard-responses.json').write_text(json.dumps(rejected, indent=2))


def test_parent_death_releases_server_and_writer_lock(servers, tmp_path):
    library = tmp_path / 'parent-library'
    library.mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('HYIMG_', 'REVIEW_'))}
    env.update(HYIMG_LIBRARY_ROOT=str(library), HYIMG_PROJECT_ID=str(uuid.uuid4()), PYTHONDONTWRITEBYTECODE='1')
    helper = "import os,subprocess,sys; os.environ['HYIMG_PARENT_PID']=str(os.getpid()); p=subprocess.Popen([sys.executable,sys.argv[1],sys.argv[2]]); p.wait()"
    with open(tmp_path / 'parent.log', 'w') as log:
        parent = subprocess.Popen([sys.executable, '-c', helper, str(ROOT / 'review/server.py'), str(port)], env=env, stdout=log, stderr=log)
        try:
            for attempt in range(100):
                try:
                    health = get(port, '/api/health')
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(.05)
            else:
                pytest.fail('parent-owned server never became healthy')
            parent.kill()
            parent.wait(timeout=5)
            for attempt in range(100):
                try:
                    request(port, '/api/health')
                except (OSError, urllib.error.URLError):
                    break
                time.sleep(.05)
            else:
                pytest.fail('server remained available after parent death')
            replacement, replacement_port, _, _ = servers('replacement', root=library)
            assert replacement.poll() is None
            assert get(replacement_port, '/api/health')['pid'] != health['pid']
            (tmp_path / 'parent-lifecycle.json').write_text(json.dumps({'parentPid': parent.pid, 'originalServerPid': health['pid'], 'originalPortClosed': True, 'replacementPid': replacement.pid, 'lockReacquired': True}, indent=2))
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=5)
