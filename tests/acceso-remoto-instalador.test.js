/** El instalador mete cloudflared (versión y SHA-256 fijados) y el build lo descarga antes de compilar. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const leer = (...p) => fs.readFileSync(path.join(__dirname, "..", ...p), "utf8").replace(/^﻿/, "");

test("setup.iss copia cloudflared.exe y aborta si falta", () => {
  const iss = leer("installer", "setup.iss");
  const exe = "..\\vendor\\cloudflared\\cloudflared.exe";
  assert.ok(iss.includes('Source: "' + exe + '"; DestDir: "{app}"; Flags: ignoreversion'));
  assert.ok(iss.includes('#if !FileExists(AddBackslash(SourcePath) + "' + exe + '")'));
});
test("el build descarga cloudflared y el binario no entra en git", () => {
  assert.ok(leer("build_installer.ps1").includes("descargar-cloudflared.ps1"));
  assert.match(leer(".gitignore"), /^vendor\/cloudflared\/\s*$/m);
});
test("la descarga fija versión y SHA-256 y comprueba el hash", () => {
  const ps = leer("tools", "descargar-cloudflared.ps1");
  assert.match(ps, /\$VERSION = "\d{4}\.\d+\.\d+"/);
  assert.match(ps, /\$SHA256\s*=\s*"[0-9a-f]{64}"/);
  assert.ok(ps.includes("Get-FileHash"));
});
