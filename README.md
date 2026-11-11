# Nova Launcher

A Minecraft launcher focused on **optimization** and **customization**, in black and violet.
Pure Python 3.10+ — no pip installs. The interface is a local web UI shown in a chromeless
Chrome/Edge/Brave window (falls back to your default browser).

## Run

```
python nova.py            # Windows: py nova.py
python nova.py --home D:\NovaData   # optional custom data folder
```

You need Python 3.10+. Java is optional: Nova detects installed Java or downloads the right
Temurin version (8/17/21) for each Minecraft version automatically.

Windows: double-click **Nova.bat** (opens only the launcher; errors are written to `nova.log` in the data folder).

### No Python? Use Nova.exe

The repo builds a standalone Windows `Nova.exe` on GitHub: **Actions → Build Nova.exe → Run
workflow**, then download `Nova-windows` from the finished run. `Nova.exe` opens only the launcher window (no console). If something goes wrong, errors are in
`nova.log` in the data folder, or run `Nova-debug.exe`, which shows a console. Tag a version (`v1.0.1`) to
publish it under **Releases** instead. The exe isn't code-signed, so Windows SmartScreen may
warn on first run: click *More info → Run anyway*.

## Features

**Loaders:** Vanilla, Fabric, Quilt, Forge, NeoForge, and OptiFine (you supply the OptiFine
installer jar from optifine.net, since it has no public download API).

**Optimization**
- JVM presets: Nova Balanced, Aikar's Flags, Generational ZGC, Low-end PC, none, or custom
- Automatic RAM recommendation based on your system, loader and mod count
- One-click performance mod pack (Sodium, Lithium, etc. via Modrinth where available)
- `options.txt` profiles: Performance / Balanced / Quality
- Cleanup tool for logs, crash reports and caches

**Customization**
- Six themes plus custom accent / glow colors, three background depths (OLED, Void, Nebula)
- Corner roundness, text size, density, starfield, glow and animation toggles
- Separate instances with their own mods, settings, Java and JVM args
- Duplicate, export and import instances; mod search/install/update via Modrinth

## Online play (Microsoft sign-in)

Profiles → **Sign in with Microsoft**. You approve a short code at microsoft.com/link, so your
password never touches Nova. Tokens are stored in `accounts.json` (owner-only permissions) and
refreshed automatically at launch.

One-time setup, because Nova ships without anyone else's keys:
1. Azure portal → App registrations → New registration, account type
   **Personal Microsoft accounts only**, no redirect URI.
2. Authentication → Advanced settings → **Allow public client flows: Yes**.
3. Paste the Application (client) ID into Nova's setup dialog.
4. **Mojang must approve the ID** (https://aka.ms/mce-reviewappid). Until they do, sign-in
   fails at the final step with a 403 and Nova tells you so. Only you can submit this.

Requires an account that owns Minecraft: Java Edition (Game Pass included).

## Known limits

- **Microsoft sign-in needs a one-time setup** (see below). Offline profiles still work for
  single-player and offline-mode servers.
- OptiFine must be supplied manually (see above).
- Tested against fake Mojang, loader and Microsoft/Xbox services (`pytest tests`) and a headless
  browser run of the sign-in flow. It has not been run against the real services or a real game launch.

## Tests

```
python -m pytest tests
```
