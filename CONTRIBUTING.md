# Contributing to Snow Island

Thanks for wanting to help! ❄️

## Reporting bugs and ideas
Use the [issue forms](https://github.com/404existenceerror-dot/snow-island/issues/new/choose). For bugs, please include:
- what you did and what happened
- a screenshot or short recording if you can
- the output of `SnowIsland.exe --diagnose` (it doesn't include song titles or files)

## Working on the code
1. Install Python 3.10+ and clone the repo.
2. Run `start.bat` once. It creates `.venv` and installs the libraries.
3. Run the app with a console, so errors are visible:
   ```bat
   .venv\Scripts\python.exe snow_island.py
   ```
   Quit the tray app first, since only one copy can run at a time.

### Where things live
- `island.py`: the island (drawing, animation, buttons, dragging)
- `winter.py`: snow, piles, snowballs, snowmen, snow truck
- `media.py`: now-playing info from Windows media controls
- `art.py`: all hand-drawn graphics
- `winapi.py` / `macapi.py` / `linuxapi.py`: Windows / macOS / Linux helpers (desktop icons, battery, CPU, window checks).
  `osapi.py` picks the right one; both expose the same functions.
- `settings.py`: defaults and saving; `settings_dialog.py`: the settings window

### Guidelines
- Keep it **local**: no network calls, analytics or accounts.
- Keep it light on CPU. Test with lots of snow and a 4K screen if you can.
- New settings go in `DEFAULTS` in `settings.py` and get a control in `settings_dialog.py`.
- One feature or fix per pull request, with a short description and a screenshot or GIF for visual changes.

## Making a release
1. Bump `__version__` in `snow_island.py`.
2. Commit, then push a tag: `git tag vX.Y.Z` and `git push origin vX.Y.Z`.
3. GitHub Actions builds the Windows exe, the Mac apps and the Linux app and creates the Release.
