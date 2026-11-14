"""Service endpoints. Every one can be overridden with an environment variable
(used by the test-suite to point at local fake servers)."""
import os


def _e(name: str, default: str) -> str:
    return os.environ.get(name, default).rstrip("/") if name != "NOVA_MOJANG_MANIFEST" else os.environ.get(name, default)


def mojang_manifest() -> str:
    return os.environ.get("NOVA_MOJANG_MANIFEST", "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")


def asset_base() -> str:
    return _e("NOVA_ASSET_BASE", "https://resources.download.minecraft.net")


def libraries_base() -> str:
    return _e("NOVA_LIBRARIES_BASE", "https://libraries.minecraft.net")


def fabric_meta() -> str:
    return _e("NOVA_FABRIC_META", "https://meta.fabricmc.net/v2")


def quilt_meta() -> str:
    return _e("NOVA_QUILT_META", "https://meta.quiltmc.org/v3")


def forge_maven() -> str:
    return _e("NOVA_FORGE_MAVEN", "https://maven.minecraftforge.net")


def neoforge_maven() -> str:
    return _e("NOVA_NEOFORGE_MAVEN", "https://maven.neoforged.net/releases")


def neoforge_api() -> str:
    return _e("NOVA_NEOFORGE_API", "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge")


def modrinth_api() -> str:
    return _e("NOVA_MODRINTH_API", "https://api.modrinth.com/v2")


def curseforge_api() -> str:
    return _e("NOVA_CURSEFORGE_API", "https://api.curseforge.com/v1")


# Optional: a CurseForge API key shipped inside Nova. Normally each user adds their own in Settings.
BUILTIN_CURSEFORGE_KEY = ""


def adoptium_api() -> str:
    return _e("NOVA_ADOPTIUM_API", "https://api.adoptium.net/v3")


# Nova's built-in Microsoft app (client) ID. Paste the ID of the Azure app that Mojang approved here
# and everyone who runs this copy of Nova can sign in without any setup. A user can still override it
# in Profiles -> Change app ID. The NOVA_MS_CLIENT_ID environment variable wins over this value.
BUILTIN_MS_CLIENT_ID = "bd999a2b-2433-403e-b3cb-98ce6cee09fb"


def default_ms_client_id() -> str:
    return os.environ.get("NOVA_MS_CLIENT_ID", BUILTIN_MS_CLIENT_ID).strip()


# Discord Rich Presence. Create an application at https://discord.com/developers/applications named
# "Nova Launcher" (that name is what Discord shows after "Playing") and paste its Application ID here.
# In the app's Rich Presence -> Art Assets, upload an image named "nova". Empty = presence stays off.
BUILTIN_DISCORD_CLIENT_ID = "1570576985665835038"


def default_discord_client_id() -> str:
    return os.environ.get("NOVA_DISCORD_CLIENT_ID", BUILTIN_DISCORD_CLIENT_ID).strip()
