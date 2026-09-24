# Cursor Pro+ Glass Desktop Widget

Unofficial always-on-top Windows widget for your **Cursor** plan usage — without opening the browser dashboard.

> Not affiliated with Cursor / Anysphere. Uses local Cursor login data + Cursor web APIs (can change).

---

## Do I need to rebuild the EXE every time?

| How you run it | Need rebuild after code changes? |
| --- | --- |
| **`scripts\launch.bat`** (Python source) | **No** — edits apply next launch |
| **`dist\CursorWidget\CursorWidget.exe`** | **Yes** — EXE is a frozen snapshot |

Use source while developing. Rebuild the EXE when you want a shareable / release build.

---

## For most people (download & run)

1. Open this repo’s **Releases** page  
2. Download **`CursorWidget-Windows-vX.Y.Z.zip`**  
3. Unzip and run **`Start Cursor Widget.bat`** (or `CursorWidget.exe`)  
4. Be signed into Cursor IDE on that PC  

Needs Windows 10/11 (64-bit). No Python required for the Release zip.

SmartScreen may warn (unsigned app) → **More info → Run anyway** if you trust the build.

---

## Project layout

```
Cursor Widget/
├── README.md                 ← you are here
├── LICENSE / SECURITY.md
├── requirements.txt
├── CursorWidget.spec         ← PyInstaller recipe
├── src/                      ← app source
│   ├── CursorWidget.py
│   └── index.html
├── assets/                   ← EXE / window icon
│   ├── app-icon.ico
│   └── app-icon.png
├── scripts/                  ← launch / build / pack
│   ├── launch.bat
│   ├── build.bat             ← cleans old dist/build then rebuilds
│   ├── pack-release.bat
│   └── pack-release.ps1
├── docs/
│   └── DEVELOPMENT.md
└── .github/workflows/
    └── release.yml
```

`dist/`, `build/`, and `release/` are generated locally and **not** committed to git.

---

## Developers

### Run from source
```bat
scripts\launch.bat
```

### Clean rebuild EXE (wipes old dist/build first)
```bat
scripts\build.bat
```
Output: `dist\CursorWidget\CursorWidget.exe` (with Cursor-style icon)

### Pack GitHub Release zip
```bat
scripts\pack-release.bat 0.1.0
```
→ `release\CursorWidget-Windows-v0.1.0.zip`

### Publish on GitHub
1. Push this repo  
2. Either upload the zip on **Releases**, or tag `v0.1.0` and let Actions build it  

---

## Privacy
- Reads Cursor auth DB read-only  
- Optional cookie override: `%USERPROFILE%\.cursor_widget_config.json` (local only — never commit)

See [SECURITY.md](SECURITY.md).

---

## License
MIT — [LICENSE](LICENSE)
