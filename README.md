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

Windows: double-click **Nova.bat**. The window stays open so you can read any error.

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
- 27 themes, custom colors, animated and imported backgrounds (see below), three surface depths
- Corner roundness, text size, density, starfield, glow and animation toggles
- Separate instances with their own mods, settings, Java and JVM args
- Duplicate, export and import instances; mod search/install/update via Modrinth

## Themes and animated backgrounds

Settings -> Themes has 27 ready-made themes (Ocean, Cyberpunk, Synthwave, Matrix, Sakura, Galaxy,
Aurora...). Everything in a theme stays editable: accent colors, page color, gradient and angle,
pattern, font, corners, text size. **Save current look** keeps your own themes (up to 30).

**Backgrounds:** a flat or gradient theme background, a *Flowing gradient* or *Aurora* animation, or
your own file via **Import image, GIF or video**: PNG / JPEG / WebP / GIF (up to 8 MB) or MP4 / WebM
(up to 64 MB). GIFs and videos animate; set the dimming slider so text stays readable. Animated
backgrounds can pause while Minecraft is running, and stop with Animations off or reduced-motion.
Imported files are checked by content (not the file name) and are never uploaded anywhere.
MP4 playback depends on your browser's codecs; if a video doesn't play, use WebM or a GIF.

## Discord Rich Presence

Shows "Playing Nova Launcher" (instance, Minecraft version, loader) on your Discord profile. Create an
application at discord.com/developers named "Nova Launcher", upload a Rich Presence art asset named
`nova`, and set its Application ID in `nova/config.py` (`BUILTIN_DISCORD_CLIENT_ID`) or the
`NOVA_DISCORD_CLIENT_ID` environment variable. Toggle it under Settings -> Discord.

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
