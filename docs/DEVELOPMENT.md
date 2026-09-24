# Development notes

## Layout
- App code lives in `src/`
- Icons in `assets/`
- Build / launch helpers in `scripts/`

## Run
```bat
scripts\launch.bat
```

## Clean EXE rebuild
`scripts\build.bat` always:
1. Kills a running `CursorWidget.exe`
2. Deletes `dist/` and `build/`
3. Runs PyInstaller with `--clean`

So you never mix old binaries with new code.

## Auth / APIs
- Prefer `https://cursor.com` (not `www` — redirects drop cookies)
- Summary: `GET /api/usage-summary`
- History: `POST /api/dashboard/get-filtered-usage-events`

## Icon
`assets/app-icon.ico` is baked into the EXE via `CursorWidget.spec` and applied to the Qt window at runtime.
