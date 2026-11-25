# Nova Visuals

A client-side cosmetic Fabric mod for Minecraft Java: glowing trails and particles, a gothic cosmetics set (devil wings, halos, horns, a pentagram, bats, auras), a night sky with aurora, stars and a blood moon, client-side time and weather, a custom HUD, and a dark, rounded ClickGUI. Everything is cosmetic and only changes what *you* see. It never changes gameplay, sends nothing to servers, and gives no advantage.

Original code and assets. Inspired by the general idea of "visual clients", not copied from any.

## Supported versions

| Minecraft | Status |
|-----------|--------|
| 1.21 / 1.21.1 | builds in CI |
| 1.21.2 / 1.21.3 | builds in CI |
| 1.21.4 | builds in CI (main target) |
| 1.21.5 | builds in CI (rendering not checked in game) |
| 1.21.8 | builds in CI; Mojang reworked rendering in 1.21.6, so the world effects are the least certain here (they switch themselves off instead of crashing if the renderer rejects them) |
| 1.21.6, 1.21.7, 1.21.9 and newer | not built |
| 1.20.x and older | not supported (needs Java 21 and different APIs) |

Needs Fabric Loader 0.16+ and Fabric API, Java 21.

"Builds in CI" means the project compiles against that version's mappings. See *Honest limitations* below.

## Install

1. Install Fabric Loader for your Minecraft version and put **Fabric API** in `mods/`.
2. Download the jar for your version from the [`visuals-latest` release](../../releases/tag/visuals-latest) (`nova-visuals-<mod version>+mc<version>.jar`) and put it in `mods/`.
3. Start the game and press **Right Shift** to open the menu (the key can be changed under Controls -> Nova Visuals).

Sodium and Iris: the mod draws through vanilla render layers at the end of the translucent world pass and uses no custom shaders, so it does not touch what those mods replace. It has not been tested with shader packs.

## Build it yourself

```
cd visuals-mod
gradle build            # Gradle 8.10+ and Java 21
```

The jar ends up in `build/libs/`. `gradle.properties` holds the Minecraft, Yarn, Loader and Fabric API versions for 1.21.4. To build for another version, change them there (the CI workflow `.github/workflows/build-visuals.yml` shows the values it uses, and looks up the newest matching Fabric versions automatically). Version-specific calls live in `versions/<minecraft version>/java/dev/nova/visuals/Compat.java`; add a folder for a new version.

## What is in it

**Particles / Visuals**: Movement trail (color-shifting ribbon with sparkles), jump and landing rings, hit sparks and impact rings, floating stars, atmospheric particles (dust, fireflies, embers, sparkles, ash). All glow effects use additive blending and share one configurable bloom (strength and size). Particles come from a pooled, struct-of-arrays pool of 8192 and are drawn in batches per texture.

**Environment**: animated skybox (nebula clouds and a glowing horizon), star field with twinkling and shooting stars, customizable sun and moon (size, color, rays, blood moon), aurora borealis, client-side time (fixed, always night, always day, fast cycle), client-side weather (clear, rain, thunderstorm), improved rain streaks and snowflakes that only fall where the sky is open.

**Cosmetics (gothic)**: wings (Devil, Gothic bat, Angel, Raven; flapping, glowing bones and tips, shed embers or feathers), halos (Holy, Dark thorns, Runes), horns (Devil, Ram, Crown spikes), a rotating pentagram magic circle, orbiting bats with glowing eyes, auras (infernal embers, soul fire, blood motes, void wisps). Turn on *Show cosmetics on other players* in Settings to see them on others too (still only on your screen).

**HUD** (all elements can be dragged and resized in the layout editor, positions are saved): FPS and coordinates, animated keystrokes, CPS counter, potion effects with timers, custom crosshair (6 styles, opens while moving), cinematic bars, color grade and vignette.

**Menu**: category sidebar (Visuals, Particles, Environment, Animations, Cosmetics, HUD, Settings), search over every module, animated toggle switches, sliders, choice buttons, an RGB/HSV/HEX color picker, accent colors (static, breathing, or rainbow), blurred background, soft shadows and glow, open/close animation, and a live preview panel.

**Config**: every module is its own switch. Settings are saved automatically to `config/nova-visuals.json`. Quality: Low, Medium, High, Ultra (particle counts, ring smoothness, glow layers). Built-in presets (Gothic, Aurora Night, Neon, Minimal, Cinematic), your own presets (`config/nova-visuals-presets/`), and import/export through the clipboard.

## Code layout

```
core/     Time (delta time), Easing, Smooth (animations), Colors
config/   Module, Setting, ModuleManager, Config (JSON, presets, import/export), Settings, Presets
gfx/      Gfx (render layers, quads), Frame (per-frame world drawing context), Pose
fx/       ParticleEngine (pool), RingPool, WorldFx (the world render hook)
modules/  the effect, environment and cosmetic modules
hud/      HUD modules, crosshair, overlay, cinematic bars
gui/      ClickGui, HudEditor, Draw (rounded rectangles, shadows, glow)
mixin/    InGameHudMixin (optional, hides the vanilla crosshair)
```

World effects are drawn once per frame in `WorldRenderEvents.AFTER_TRANSLUCENT` into a private vertex buffer, with the vanilla `eyes` render layer for additive glow and the translucent emissive layer for solid shapes. Those layers set up and restore blend, depth and cull state themselves, so nothing is left changed.

## Honest limitations

- **Not tested inside the game.** The sandbox this was written in cannot run Minecraft. The mod compiles for every version above, but how things *look* (positions, sizes, colors) has not been seen by a human. Expect to tweak sizes in the menu, and please report anything that looks wrong.
- **No custom GLSL post-processing.** Real motion blur, true saturation/LUT color grading, framebuffer bloom and custom fog need a post-process shader pipeline that differs on every version and conflicts with Iris and Sodium, and could not be tested here. The substitutes are: sprite-based bloom, a tint plus vignette overlay for color grading, and vanilla's own menu blur. Fog color and distance are not changed.
- **No cinematic camera movement or custom item-swing animations.** These need invasive mixins into the camera and hand rendering that cannot be checked without running the game. Cinematic bars are included instead.
- Rain and snow are drawn *on top of* the vanilla weather; vanilla rain is not hidden.
- Cosmetics are client-side: other players do not see your wings.
- The vanilla crosshair is hidden through one optional mixin. If a version changes that method, the mixin is skipped (no crash) and both crosshairs show.

License: same as the rest of this repository.
