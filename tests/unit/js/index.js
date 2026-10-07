// `node --test tests/unit/js/` names this directory, and node 22 runs a directory as its index.js: this file loads every *.test.mjs
// beside it, so the whole folder runs as one suite. `node --test tests/unit/js/*.test.mjs` runs the files one by one instead.
const fs = require("node:fs"), path = require("node:path"), { pathToFileURL } = require("node:url");
for (const f of fs.readdirSync(__dirname).filter(f => f.endsWith(".test.mjs")).sort()) import(pathToFileURL(path.join(__dirname, f)).href);
