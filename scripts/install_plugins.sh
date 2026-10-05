#!/bin/bash
# Installs the Hyimg canvas plugins: Frames (image frames editor and HTML frames) and 3D objects. Each plugin is its own Git
# repository; an existing checkout beside this repository is used, otherwise it is cloned there, and a symlink to it goes into
# ~/Library/Application Support/Hyimg/plugins/<name>. Nothing is downloaded beyond the chosen repositories: the LaMa model for
# content-aware fill (about 208 MB) comes only with --lama.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
BESIDE="$(dirname "$ROOT")"
PLUGINS="${HYIMG_PLUGINS_DIR:-$HOME/Library/Application Support/Hyimg/plugins}"
LAMA_DIR="$HOME/Library/Caches/Hyimg/models/lama"
LAMA_URL="https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx"

usage() {
  cat <<'EOF'
Использование: scripts/install_plugins.sh [--frames] [--3d] [--lama] [--yes] [--remove]

Без флагов в терминале скрипт спрашивает про каждый плагин.

  --frames   Фреймы: редактор картинок на доске (слои, маски, Color Grading, заливка) и HTML-фреймы
             https://github.com/constantvis/hyimg-frames, папка плагина frames
  --3d       3D-объекты: 3D-сцена карточкой на доске, перенос в Blender (Blender не обязателен)
             https://github.com/constantvis/hyimg-3d-studio, папка плагина 3d
  --lama     скачать модель LaMa для заливки (около 208 МБ) в ~/Library/Caches/Hyimg/models/lama
  --yes      не задавать вопросов: ставить только то, что названо флагами
  --remove   убрать наши ссылки на плагины (репозитории и модель остаются)

Агенту: сначала спроси человека про каждый плагин по имени, скажи, что он дает и что ему нужно,
и запускай с флагами только того, на что он ответил «да». Модель LaMa спрашивай отдельно.
Флаги не заменяют согласие человека.

Копии плагинов берутся рядом с этим репозиторием (../hyimg-frames, ../hyimg-3d-studio)
или клонируются туда. Ссылки ставятся в ~/Library/Application Support/Hyimg/plugins
(другая папка: HYIMG_PLUGINS_DIR). После установки перезапусти сервер Hyimg (⇧⌘R).
EOF
}

want_frames=0; want_3d=0; want_lama=0; yes=0; remove=0; named=0
for arg in "$@"; do
  case "$arg" in
    --frames) want_frames=1; named=1 ;;
    --3d) want_3d=1; named=1 ;;
    --lama) want_lama=1; named=1 ;;
    --yes|-y) yes=1 ;;
    --remove) remove=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "неизвестный флаг: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

# name|folder beside hyimg|repository|what it gives
PLUGIN_LIST=(
  "frames|hyimg-frames|https://github.com/constantvis/hyimg-frames.git|Фреймы: редактор картинок на доске (слои, маски, Color Grading, заливка) и HTML-фреймы"
  "3d|hyimg-3d-studio|https://github.com/constantvis/hyimg-3d-studio.git|3D-объекты: 3D-сцена карточкой на доске, свой редактор, перенос в Blender"
)

ask() {   # ask "question" -> 0 on yes; only in an interactive terminal
  local reply
  read -r -p "$1 [y/N] " reply </dev/tty || return 1
  case "$reply" in y|Y|yes|д|Д|да|Да) return 0 ;; *) return 1 ;; esac
}

interactive=0
if [ "$yes" = 0 ] && [ -t 0 ] && [ -t 1 ]; then interactive=1; fi
if [ "$remove" = 0 ] && [ "$interactive" = 0 ] && [ "$named" = 0 ]; then
  echo "Не терминал и нет флагов: ничего не ставлю. Спроси человека и передай ответ флагами (--frames, --3d, --lama, --yes)." >&2
  usage >&2; exit 2
fi

mkdir -p "$PLUGINS"
for entry in "${PLUGIN_LIST[@]}"; do
  IFS='|' read -r name folder repo about <<<"$entry"
  link="$PLUGINS/$name"; src="$BESIDE/$folder"
  if [ "$remove" = 1 ]; then
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$src" ]; then rm "$link" && echo "убрал $link"
    elif [ -e "$link" ] || [ -L "$link" ]; then echo "не наша ссылка, не трогаю: $link"; fi
    continue
  fi
  flag=$want_frames; [ "$name" = "3d" ] && flag=$want_3d
  if [ "$flag" = 0 ]; then
    [ "$interactive" = 1 ] || continue
    echo
    echo "$about"
    echo "  источник: ${repo%.git}"
    [ "$name" = "frames" ] && echo "  нужно: macOS Vision (встроен), по желанию модель LaMa около 208 МБ"
    [ "$name" = "3d" ] && echo "  нужно: по желанию Blender для переноса сцен"
    ask "Поставить плагин «${about%%:*}»?" || { echo "пропускаю $name"; continue; }
  fi
  if [ ! -d "$src" ]; then
    echo "клонирую $repo в $src"
    git clone --quiet "$repo" "$src"
  fi
  [ -f "$src/manifest.json" ] || { echo "в $src нет manifest.json, это не плагин Hyimg" >&2; exit 1; }
  if [ -L "$link" ]; then
    if [ "$(readlink "$link")" = "$src" ]; then echo "есть  $link"; continue; fi
    echo "занято другой ссылкой, не трогаю: $link -> $(readlink "$link")"; continue
  fi
  if [ -e "$link" ]; then echo "занято папкой, не трогаю: $link"; continue; fi
  ln -s "$src" "$link" && echo "новая $link -> $src"
done

[ "$remove" = 1 ] && exit 0

if [ "$want_lama" = 0 ] && [ "$interactive" = 1 ] && [ -L "$PLUGINS/frames" ] && [ ! -f "$LAMA_DIR/lama_fp32.onnx" ]; then
  echo
  echo "Модель LaMa для заливки с учетом содержимого: около 208 МБ, Apache-2.0, ${LAMA_URL%/resolve/*}"
  echo "  без нее редактор заливает проще, без нейросети"
  ask "Скачать модель в $LAMA_DIR?" && want_lama=1
fi
if [ "$want_lama" = 1 ]; then
  if [ -f "$LAMA_DIR/lama_fp32.onnx" ]; then
    echo "есть  $LAMA_DIR/lama_fp32.onnx"
  else
    mkdir -p "$LAMA_DIR"
    echo "скачиваю модель LaMa (около 208 МБ)"
    curl -fL --progress-bar -o "$LAMA_DIR/lama_fp32.onnx.part" "$LAMA_URL"
    mv "$LAMA_DIR/lama_fp32.onnx.part" "$LAMA_DIR/lama_fp32.onnx"
    echo "новая $LAMA_DIR/lama_fp32.onnx"
    python3 -c "import onnxruntime" 2>/dev/null || echo "для заливки нужен еще onnxruntime: python3 -m pip install onnxruntime"
  fi
fi

echo
echo "Готово. Перезапусти сервер Hyimg: Вид › Перезапустить сервер (⇧⌘R)."
