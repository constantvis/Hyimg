"""The plugins an agent must ask about (owner 2026-10-05: «if we give this repository to an agent, it must know and ASK the person
whether they want to install the plugins, 3D and image frames»): /agent names the missing ones once, and scripts/install_plugins.sh
installs only what it is told to."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/install_plugins.sh"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def plugin(folder, title):
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({"title": title, "canvas": "canvas.js"}, ensure_ascii=False))
    (folder / "canvas.js").write_text("export default {};\n")
    return folder


def agent_text(tmp_path, plugin_dirs):
    lib, home = tmp_path / "lib", tmp_path / "home"   # a home of its own: the real ~/Library/Application Support/Hyimg/plugins stays out
    (lib / "a").mkdir(parents=True); home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(home), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_PLUGINS=os.pathsep.join(map(str, plugin_dirs)),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru"}))   # the interface in Russian (owner 2026-10-06: English by default)
    port = free_port(); log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError:
                time.sleep(0.1)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/agent") as r:
            return r.read().decode()
    finally:
        proc.terminate(); proc.wait(5); log.close()


def test_agent_page_names_missing_plugins_once(tmp_path):
    page = agent_text(tmp_path, [])
    assert "## Плагины" in page and "Плагинов нет." in page
    assert "Спроси человека" in page and "install_plugins.sh" in page
    assert page.count("https://github.com/constantvis/hyimg-image-studio") == 1 and page.count("https://github.com/constantvis/hyimg-3d-studio") == 1
    assert page.count("https://github.com/constantvis/hyimg-dev-studio") == 1
    assert "LaMa" in page and "Blender" in page


def test_agent_page_lists_installed_plugins_and_only_the_missing_one(tmp_path):
    root = tmp_path / "plugins"; root.mkdir()
    os.symlink(plugin(tmp_path / "src/hyimg-image-studio", "Фреймы"), root / "frames")
    page = agent_text(tmp_path, [root])
    assert "Подключен «Фреймы» (`frames`)" in page
    assert "hyimg-image-studio" not in page.split("Не установлены")[-1]
    assert "https://github.com/constantvis/hyimg-3d-studio" in page


def test_agent_page_says_nothing_is_missing_when_all_are_there(tmp_path):
    root = tmp_path / "plugins"; root.mkdir()
    os.symlink(plugin(tmp_path / "src/f", "Фреймы"), root / "frames")
    os.symlink(plugin(tmp_path / "src/d", "3D-объекты"), root / "3d")
    os.symlink(plugin(tmp_path / "src/v", "Дев-студия"), root / "dev")
    page = agent_text(tmp_path, [root])
    assert "Не установлены" not in page and "Подключен «3D-объекты» (`3d`)" in page


@pytest.mark.skipif(sys.platform == "win32", reason="bash script")
def test_install_script_links_only_the_named_plugins_and_never_asks_without_a_terminal(tmp_path):
    beside = tmp_path / "repos"; hyimg = beside / "hyimg"
    (hyimg / "scripts").mkdir(parents=True)
    (hyimg / "scripts/install_plugins.sh").write_bytes(SCRIPT.read_bytes()); os.chmod(hyimg / "scripts/install_plugins.sh", 0o755)
    plugin(beside / "hyimg-image-studio", "Фреймы"); plugin(beside / "hyimg-3d-studio", "3D-объекты")
    target = tmp_path / "plugins"
    env = {**os.environ, "HOME": str(tmp_path / "home"), "HYIMG_PLUGINS_DIR": str(target)}
    run = lambda *a: subprocess.run(["bash", str(hyimg / "scripts/install_plugins.sh"), *a], env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=60)
    r = run()   # no flags and no terminal: nothing is installed, the agent is told to ask
    assert r.returncode == 2 and "Спроси человека" in r.stderr and not target.exists()
    r = run("--frames", "--yes")
    assert r.returncode == 0, r.stderr
    assert (target / "frames").resolve() == (beside / "hyimg-image-studio").resolve() and not (target / "3d").exists()
    assert not (tmp_path / "home/Library/Caches/Hyimg/models").exists()   # the model only with --lama
    r = run("--remove")
    assert r.returncode == 0 and not (target / "frames").exists()
