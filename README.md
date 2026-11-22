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
- Button pictures: import your own image as the background of main, other and delete buttons (Settings -> Buttons)
- Separate instances with their own mods, settings, Java and JVM args
- Duplicate, export and import instances
- Mods, shaders and resource packs from **Modrinth and CurseForge**, with required dependencies and update checks

## CurseForge

Modrinth works out of the box. For CurseForge, get a free API key at https://console.curseforge.com
and paste it in Discover (pick CurseForge) or Settings -> CurseForge. The key is stored in the data folder
(`curseforge.key`) and only sent to api.curseforge.com. Some authors block downloads outside
CurseForge's own site; Nova tells you when that happens. CurseForge modpacks aren't importable yet.

## Cosmetics

The **Cosmetics** tab designs a Nova look: hats, face gear, chest emblems, boots and capes carrying the
Nova mark, with your own main and trim colors, on top of your Minecraft skin (or an uploaded PNG, or Nova's
default skin). Hats, face, chest and boots are painted into the skin, so **Save & use on my Minecraft account**
(Microsoft profiles) shows them to everyone online. Minecraft can't upload custom capes, so the cape (and the
skin, for offline profiles) is shown on your own character by the Nova in-game mod.

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


## Nova Roblox (a Bloxstrap-style Roblox launcher)

`NovaRoblox.exe` (from the same Releases page) is a second app built from this code, with its own data folder.
Nova does not download or install Roblox. It finds the Roblox already on your PC (Roblox's own install, or a copy
from Bloxstrap or Voidstrap) and tunes and opens that one.

- **Play from roblox.com**: press *Connect* once, then *Play* on roblox.com opens Roblox through Nova. When a newer
  Roblox is out, the game is handed to Roblox's own launcher first so it can update. Sign-in stays in your browser.
- **Ready-made skies** (Sunset, Starry night, Pastel, Deep space, Ocean), **Apply again** and **Check sky** buttons. Nova also
  puts your sky in Bloxstrap/Voidstrap's Modifications folder so they stop undoing it. Close Roblox before changing the sky.
- **Open sky folder** opens the right folder in one click (Voidstrap/Bloxstrap: their Modifications sky folder) and **Import sky pack (.zip)** uses a downloaded skybox fix / sky pack (files like `sky512_ft.tex`) as your sky.
- **Skybox fix** (the community fix that swaps six cached sky mesh files in Roblox's `rbx-storage`) is built in. It turns on by itself with a custom sky and is removed when you go back to the default.
- **Refresh on close**: when Roblox closes, Nova puts your sky, skybox fix and flags back, so a change made while Roblox was open (or an update undoing it) is applied for the next start. Keep Nova open in the background for this.
- **Your skies**: every imported sky pack is kept in a list; pick any with one click. Import many at once (a folder of sky folders, or several .zip files).
- **Crosshair**: pick one of 7 ready-made crosshairs (any color, 3 sizes) or import your own picture. It replaces the in-game aim cursor (`ArrowFarCursor` / `MouseLockedCursor`), optionally the normal pointer too. Games that draw their own crosshair keep it.
- **Weather**: rain, snow or a thunderstorm (with lightning) over your screen in Low, Mild or Heavy. It is a see-through, click-through layer on top of the screen (Nova can't draw inside Roblox), shown only while you are in a game (not on the Roblox app home page) unless you turn that off.
- **Clean Roblox logs & temp files** in Maintenance.
- **Sky**: pick a color or any picture (one for every side, or each side). Nova cuts a square, converts it to the
  512x512 DXT1 `.tex` files Roblox uses and puts them over its default sky, so every game that doesn't build its own sky
  changes. A button opens Roblox's sky textures folder. Restart Roblox to see a change.
- **FastFlags**: *High optimization* (lowest quality everywhere: no shadows, post effects or grass, lowest textures),
  presets (FPS limit, graphics API, ...) and your own flags. Roblox ignores flags it doesn't allow.
- **Extras**: change the death sound (mute it or use your own .ogg/.mp3/.wav) and set any FPS limit from 30 to 9999.
- **Same look as Nova**: themes, backgrounds, button pictures and Discord "Playing Roblox" presence.

Run from source with `python novarbx.py`. Nova Roblox isn't made by or connected to Roblox Corporation.
