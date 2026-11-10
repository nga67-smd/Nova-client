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


def adoptium_api() -> str:
    return _e("NOVA_ADOPTIUM_API", "https://api.adoptium.net/v3")
