# Glossary

Version 4, 2026-10-09 (Comment renamed Annotation, drawing put off; version 3: Hint bar and Tip settled; version 2, 2026-10-08: Board and Studio). The names Hyimg uses in its interface, its docs and its agents. English is the base language; the Russian name is the one the Russian interface shows. A name marked **(not settled)** is still waiting for the owner's decision. The cards with a picture of each term are on the «Hyimg App» board, page «UI», group «Glossary» (`Concepts/html/editors-concepts/glossary/`).

The word «Frame» is no longer used for a composed image or a reused thing: those are an **Image** and a **Component**.

Working on the canvas is the **Board**; working inside one object is a **Studio** (owner 2026-10-08). «Mode», «editor» and «editing mode» are no longer used for it. The three studios are proper names and stay English in the Russian interface too: **Image Studio**, **3D Studio**, **Dev Studio** («Открыть в Image Studio», «выйти из студии»). The dock's switch keeps short labels: Board, Image, 3D, Dev; its tooltips say the full names.

## The board

| Term | RU | What it is | Where in the UI |
|---|---|---|---|
| Board | Доска | The file you open: its pages, library and history, living in a Finder folder | Home › All boards |
| Page | Страница | One canvas of a board | Crumb › page menu (Page 1 ▾), the Pages block |
| Canvas | Холст | The endless surface of a page where everything lies | The board view, zoom and pan |
| Group | Группа | A frame with a title around things that belong together | Board, ⌘G |
| Text **(not settled)** | Текст | Text on the board: its first line the title, the lines under it an optional Markdown body, as a note in Apple Notes. A text with a body is a document, with none a heading | Board, a double click on an empty place |
| Heading | Заголовок | A text with only its title line: big text over a column of groups, a row's or a column's title in a table | Board, text |
| Timeline | Таймлайн | Phases of the work as points on a line | Board, L |
| Note | Заметка | A sticky note; the owner's are yellow, an agent's blue | Board, N |
| Reply | Ответ | A note with an arrow to another note: it answers that note, a thread as in comments | Board, Info |
| Arrow | Стрелка | A curve from any thing to any other (a picture, a card, a heading, a group, a note), with words on it; solid «is», dashed «like», dotted «maybe», blue «picked». A note's own arrow is its link, not this | Board: the round handle of one selected thing |
| Layout pattern | Шаблон раскладки | One of the ways an agent lays its work out (variants grid, A/B, a batch under its phase, before/after, review …); a choice gets numbers on its cells | hy.py patterns, the cells' numbers |
| Annotation | Аннотация | A pin with a thread on an object, an area of it or the canvas, as Figma's comments: replies, @mentions of people and their agents, Resolve. Until 2026-10-09 the interface called it Comment; the code, the server and hy.py still do (`comments`, `/api/comments`, `hy.py comments`) | Board, C or the dock's Annotation button; right click on the empty board › Annotations on this page |
| Drawing **(put off)** | Рисунок | Pen, arrow, shapes and short text on top of the canvas over any object, moving with it. Hidden since 2026-10-09 («доработать потом», docs/LATER.md); drawings already on a board still show. In the code and hy.py it is the «annotation» (`/api/annotations`, `hy.py annotations`) | Not in the interface |

## What lies on a canvas

| Term | RU | What it is | Where in the UI |
|---|---|---|---|
| Image | Картинка | Anything shown as a picture, one layer or many; editing it (Raw Editor and the rest) keeps it an Image | Board, Image Studio |
| Layer | Слой | One sheet inside an image, with its blend mode and opacity | Image Studio › Layers |
| Master layers | Мастер-слои | Raw Editor and Mask of the whole image, pinned above all layers | Image Studio › Layers › Master |
| Component | Компонент | Something made once and used many times: a logo, an icon, an iPhone screen placeholder, a whole composition | Library › Components |
| Instance | Экземпляр | One placement of a component, on the canvas or as a layer inside an image | Board, Layers |
| Original file | Исходный файл | A file on disk; Hyimg never changes it. Not the same as a Component | Library, Finder |
| HTML page | HTML-страница | A web page as a card, live when big enough on screen | Board, Dev Studio |
| 3D scene | 3D-сцена | Objects, lights and cameras as a card you turn yourself | Board, 3D Studio |

### Components

- Everything inside a component is the same in all its instances. Everything on top of an instance (its own master Raw Editor, Mask, transform, opacity, effects) belongs to that instance only.
- A double click on an instance opens it in Image Studio: the component's layers show locked, the instance's own master layers can be changed, and «Edit component» opens the component itself.
- «Edit component» opens it over the same canvas, no page switch. The crumb grows: `Page 1 › Studio cover › Logo`, one step more for a nested component. Save or Esc go back one level, any crumb jumps there. While editing, the block «Used in · N» shows every instance. Buttons: «Save» and «Save as new component».
- Commands: Create component ⌥⌘K; Duplicate ⌘D or ⌥-drag (another instance); Duplicate as new component (an independent copy); Detach instance (back to plain layers); Go to component.
- Colour: components and instances are purple; an instance wears the instance badge, a component its own.

## Library

| Term | RU | What it is | Where in the UI |
|---|---|---|---|
| Library | Библиотека | Every file of the board's folder, with folders and filters | Top-left button, the Library block |
| Library › Components | Библиотека › Компоненты | Where components live (not on a page), with how often each is used | Library, section Components |
| Properties clipboard | Буфер свойств | A copied look (Raw Editor, Mask, crop, trim, size, opacity, page) to paste on other pictures | Right click › Copy properties ⌥⌘C, Paste properties ⌥⌘V |

## The interface

| Term | RU | What it is | Where in the UI |
|---|---|---|---|
| Board (working on the canvas) | Доска | Working on the canvas: cards, groups, notes, as opposed to a Studio. The first segment of the dock's switch | The switch at the right end of the dock |
| Studio | Studio (в тексте «студия») | Working inside one object, as opposed to the Board; each kind of object has its own: Image Studio, 3D Studio, Dev Studio. Leave it with Done, Esc or Board | The switch at the right end of the dock |
| Image Studio | Image Studio | The studio of an image or a frame: layers, Raw Editor, masks, brush, fill | Dock › Image, a double click on an image or a frame |
| 3D Studio | 3D Studio | The studio of a 3D scene: objects, lights, cameras, materials, render | Dock › 3D, «3D Studio» over a 3D card, a double click |
| Dev Studio | Dev Studio | The studio of an HTML page: its element tree, the live page, an inspector that writes into the file | Dock › Dev, a double click on an HTML card |
| Block | Блок | A panel beside your work: drag it by ✥, fold it, float it | Left and right columns |
| Tab | Вкладка | Blocks merged into one, used one at a time; drag a tab out to split | A block's header |
| Section | Раздел | Part of one tool inside a block, opened by its chevron | Raw Editor, Properties |
| Key hint | Подсказка клавиш | The keys of what you are doing right now, beside it, gone when you stop. On a surface just the ↵, in its ink; in glass with words where there is no surface | A note's corner, a field's end, under a drag or a resize |
| Hint bar | Строка подсказок | The main keys of the Studio or tool you just opened, in one line at the top, gone once you use one | Top centre of the board's free part, under the top row |
| Tip | Совет | One short line about one thing you can do here. It stays still: one per visit, a click shows the next, × hides the place's tips | The library's header, an empty page |

### Hints

- Which one is decided by what the person is doing. Doing something: a **Key hint** beside it. Just opened a Studio or picked a tool: the **Hint bar**. Only looking: a **Tip** in its place.
- The Key hint and the Hint bar are one primitive, `<hy-keyhint>`, and the bar is its place at the top. One shows at a time: an action's key hint takes the bar's place.
- Where the action has a surface (a note, a heading, a field), the key hint is written on it: the ↵ glyph alone, no word, no key plate (owner 2026-10-09). The glass capsule with words is for a drag, a resize and the Hint bar.
- The Tip is `<hy-tip>`, round 12's version 9 (owner 2026-10-09: «9 версия идеальна — делай»). Something done the long way shows its quick way once.
- All three learn from the same counts (`cv.keyhintUsed`) and follow one setting, Settings › Interface › Key hints: Always, Until learned, Off.
- Not this family: a footnote (`<hy-hint>`) and ⓘ explain what is on screen, and the keys shown on buttons while ⌘ is held are the buttons' own labels.
- All three are built and settled (2026-10-09, DESIGN.md «Семья подсказок»).

## People

| Term | RU | What it is | Where in the UI |
|---|---|---|---|
| Person | Человек | Someone who works on the board | Notes, history, notifications |
| Agent | Агент | An AI working for a person; shown as that person's avatar with a small agent badge at the bottom right | Notes, history, notifications |

## Colours

Blue: selection, the important action (Save, Render). Purple: images in Image Studio, components and instances. Green: Dev Studio and HTML pages. Pink: 3D Studio and 3D scenes.
