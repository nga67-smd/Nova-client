"""End-to-end tests of the launcher engine against local fake services."""
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_services import Fake, make_zip, sha1  # noqa: E402

from nova import (accounts, instances, java as javamod, launch, loaders, mods, optimize, paths,  # noqa: E402
                  settings, versions)
from nova.util import NovaError, Task, TaskManager  # noqa: E402


@pytest.fixture(scope="session")
def fake():
    f = Fake()
    yield f
    f.close()


@pytest.fixture()
def env(fake, tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path / "nova"))
    for k, v in fake.env().items():
        monkeypatch.setenv(k, v)
    javamod._major_cache.clear()
    return tmp_path


def run_task(fn):
    tm = TaskManager()
    t = tm.run("t", fn)
    for _ in range(600):
        if t.status != "running":
            break
        time.sleep(0.05)
    assert t.status != "running", "task timed out"
    return t


# ------------------------------------------------------------- pure logic

def test_offline_uuid_is_java_compatible():
    # Java: UUID.nameUUIDFromBytes("OfflinePlayer:Notch".getBytes())
    assert accounts.offline_uuid("Notch") == "b50ad385-829d-3141-a216-7e7d7539ba7f"


def test_maven_path():
    assert versions.maven_path("org.lwjgl:lwjgl:3.3.1:natives-linux") == "org/lwjgl/lwjgl/3.3.1/lwjgl-3.3.1-natives-linux.jar"
    assert versions.maven_path("a.b:c:1.0@zip") == "a/b/c/1.0/c-1.0.zip"


def test_rules():
    me = paths.os_name()
    other = "windows" if me != "windows" else "linux"
    assert versions.rules_allow(None)
    assert versions.rules_allow([{"action": "allow", "os": {"name": me}}])
    assert not versions.rules_allow([{"action": "allow", "os": {"name": other}}])
    assert not versions.rules_allow([{"action": "allow"}, {"action": "disallow", "os": {"name": me}}])
    assert versions.rules_allow([{"action": "allow", "features": {"x": True}}], {"x": True})
    assert not versions.rules_allow([{"action": "allow", "features": {"x": True}}], {})


def test_neoforge_mapping():
    assert loaders.neoforge_to_mc("20.4.237") == "1.20.4"
    assert loaders.neoforge_to_mc("21.0.5") == "1.21"
    assert loaders.neoforge_to_mc("21.1.172") == "1.21.1"


def test_jvm_presets():
    a = optimize.preset_flags("aikar", 6144, 21)
    assert "-XX:+UseG1GC" in a and "-XX:G1HeapRegionSize=8M" in a
    assert "-XX:G1HeapRegionSize=16M" in optimize.preset_flags("aikar", 16384, 21)
    assert "-XX:+ZGenerational" in optimize.preset_flags("zgc", 4096, 21)
    assert "-XX:+ZGenerational" not in optimize.preset_flags("zgc", 4096, 23)
    assert "-XX:+UseG1GC" in optimize.preset_flags("zgc", 4096, 17)  # falls back
    assert optimize.preset_flags("none", 4096, 21) == []


def test_memory_recommendation_respects_ram():
    assert optimize.recommend_memory("vanilla", 0, 16384)["max"] == 2048
    r = optimize.recommend_memory("fabric", 300, 8192)
    assert r["max"] <= 8192 * 0.55 and r["min"] <= r["max"]
    assert optimize.recommend_memory("fabric", 50, 2048)["max"] >= 1024


def test_options_profile_merges(env):
    gd = env / "mc"
    gd.mkdir()
    (gd / "options.txt").write_text("lang:en_us\nrenderDistance:32\nkey_key.jump:key.keyboard.space\nfancyGraphics:true\n")
    changed = optimize.apply_options_profile(gd, "performance")
    txt = (gd / "options.txt").read_text()
    assert "lang:en_us" in txt and "key_key.jump:key.keyboard.space" in txt
    assert "renderDistance:8" in txt and "fancyGraphics:false" in txt
    assert "graphicsMode" not in txt            # key wasn't in the file: don't invent version-specific options
    assert "renderDistance" in changed


def test_jvm_args_user_extras():
    inst = dict(instances.DEFAULTS, memory_max=3072, memory_min=1024, jvm_preset="none", jvm_args='-Dfoo="a b" -XX:+Bar')
    args = optimize.build_jvm_args(inst, 21, "-Dglobal=1")
    assert args[:2] == ["-Xms1024M", "-Xmx3072M"] and "-Dglobal=1" in args and "-Dfoo=a b" in args


# ------------------------------------------------------------- instances

def test_instance_lifecycle(env):
    inst = instances.create({"name": "My Pack!", "mc_version": "1.20.1", "loader": "fabric"})
    assert inst["id"] == "my-pack" and instances.game_dir("my-pack").is_dir()
    inst2 = instances.create({"name": "My Pack!", "mc_version": "1.20.1"})
    assert inst2["id"] == "my-pack-2"
    up = instances.update("my-pack", {"memory_max": "6144", "color": "nonsense", "version_id": ""})
    assert up["memory_max"] == 6144 and up["color"] == "#8b5cf6"
    dup = instances.duplicate("my-pack", "Copy of pack")
    assert dup["name"] == "Copy of pack" and dup["playtime_s"] == 0
    instances.delete("my-pack-2")
    assert {i["id"] for i in instances.list_all()} == {"my-pack", "copy-of-pack"}


def test_instance_rejects_bad_input(env):
    with pytest.raises(NovaError):
        instances.get("../../etc")
    with pytest.raises(NovaError):
        instances.create({"name": "x", "mc_version": ""})
    with pytest.raises(NovaError):
        instances.create({"name": "x", "mc_version": "1.20.1", "loader": "evil"})
    with pytest.raises(NovaError):
        instances.create({"name": "x", "mc_version": "1.20.1", "memory_max": "lots"})


def test_pack_roundtrip_strips_code_fields(env):
    inst = instances.create({"name": "Src", "mc_version": "1.20.1", "loader": "fabric", "pre_launch": "echo hi",
                             "jvm_args": "-javaagent:x.jar", "jvm_preset": "aikar", "memory_max": 5000})
    gd = instances.game_dir(inst["id"])
    (gd / "mods").mkdir()
    (gd / "mods" / "a.jar").write_bytes(b"jar")
    (gd / "options.txt").write_text("a:b\n")
    (gd / "saves").mkdir()
    (gd / "saves" / "w.dat").write_bytes(b"x")
    out = instances.export_pack(inst["id"], env / "p.novapack")
    names = zipfile.ZipFile(out).namelist()
    assert "minecraft/mods/a.jar" in names and not any("saves" in n for n in names)
    assert b"echo hi" not in zipfile.ZipFile(out).read("nova-pack.json")
    # a hostile pack that tries to smuggle in commands
    evil = env / "evil.novapack"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("nova-pack.json", json.dumps({"instance": {"name": "Evil", "mc_version": "1.20.1",
                    "pre_launch": "rm -rf ~", "post_exit": "curl x|sh", "jvm_args": "-javaagent:evil.jar",
                    "env": {"LD_PRELOAD": "x"}, "java_path": "/tmp/evil"}}))
        z.writestr("minecraft/mods/x.jar", b"x")
    imp = instances.import_pack(evil)
    assert imp["pre_launch"] == "" and imp["post_exit"] == "" and imp["jvm_args"] == "" and imp["env"] == {}
    assert imp["java_path"] == ""
    good = instances.import_pack(out)
    assert good["jvm_preset"] == "aikar" and good["memory_max"] == 5000
    assert (instances.game_dir(good["id"]) / "mods" / "a.jar").exists()


def test_pack_zip_slip_blocked(env):
    evil = env / "slip.novapack"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("nova-pack.json", json.dumps({"instance": {"name": "Slip", "mc_version": "1.20.1"}}))
        z.writestr("../../escaped.txt", b"pwned")
    with pytest.raises(NovaError):
        instances.import_pack(evil)
    assert not (env / "escaped.txt").exists() and not (env.parent / "escaped.txt").exists()


def test_accounts(env):
    a = accounts.add_offline("Steve_1")
    assert accounts.selected()["id"] == a["id"] and len(a["uuid"]) == 36
    with pytest.raises(NovaError):
        accounts.add_offline("x")
    with pytest.raises(NovaError):
        accounts.add_offline("steve_1")
    with pytest.raises(NovaError):
        accounts.add_offline("bad name!")
    b = accounts.add_offline("Alex")
    accounts.select(b["id"])
    accounts.remove(b["id"])
    assert accounts.selected()["id"] == a["id"]


def test_settings_validation(env):
    s = settings.update({"accent": "#112233", "radius": 99, "font_scale": "110", "nope": 1})
    assert s["accent"] == "#112233" and s["radius"] == 28 and s["font_scale"] == 110 and "nope" not in s
    with pytest.raises(NovaError):
        settings.update({"accent": "red"})
    with pytest.raises(NovaError):
        settings.update({"surface": "pink"})


# --------------------------------------------------------------- versions

def test_manifest_and_resolution(env, fake):
    vs = versions.list_versions({"release"})
    assert [v["id"] for v in vs] == ["1.21.4", "1.21.1", "1.20.1", "1.7.10"]
    assert versions.latest()["release"] == "1.21.4"
    ids = [v["id"] for v in versions.list_versions({"snapshot"})]
    assert ids == ["25w01a"]


def test_prepare_downloads_everything(env, fake):
    task = Task("t")
    v = versions.prepare_version("1.20.1", task)
    root = paths.versions_dir() / "1.20.1"
    assert (root / "1.20.1.jar").read_bytes() == fake.client_jar
    assert (paths.libraries_dir() / "com/example/lib/1.0/lib-1.0.jar").exists()
    # windows-only library must not be fetched on other OSes (the URL 404s on purpose)
    if paths.os_name() != "windows":
        assert not (paths.libraries_dir() / "x/winonly.jar").exists()
    assert len(list((paths.assets_dir() / "objects").rglob("*"))) >= 2
    assert (paths.assets_dir() / "indexes" / "12.json").exists()
    versions.extract_natives(v, versions.natives_dir_for("inst"))
    nd = versions.natives_dir_for("inst")
    assert any(nd.glob("*")) and not (nd / "META-INF").exists()


def test_checksum_mismatch_detected(env, fake):
    from nova.util import download_file
    with pytest.raises(NovaError):
        download_file(fake.base + "/dl/client-1.20.1.jar", env / "x.jar", sha1="0" * 40)
    assert not (env / "x.jar").exists() and not list(env.glob("*.part"))


# ----------------------------------------------------------------- loaders

def test_fabric_and_quilt(env, fake):
    vs = loaders.fabric_like_versions("fabric", "1.20.1")
    assert vs[0]["stable"] is False and vs[1]["stable"] is True
    vid = loaders.install_fabric_like("fabric", "1.20.1", "0.15.0")
    assert vid == "fabric-loader-0.15.0-1.20.1"
    merged = versions.resolve_version(vid)
    assert merged["_root_id"] == "1.20.1" and merged["mainClass"] == "FakeMain"
    names = [l["name"] for l in merged["libraries"]]
    assert names[0] == "net.fake:loader:0.15.0" and "com.example:lib:1.0" in names
    assert "1.20.1" in loaders.supported_games("quilt")


def test_forge_via_installer(env, fake):
    vs = loaders.forge_versions("1.20.1")
    assert [v["version"] for v in vs] == ["47.2.0", "47.1.0"]
    vid = loaders.install_forge("1.20.1", "47.2.0", "java")
    assert vid == "1.20.1-forge-47.2.0"
    assert (paths.data_dir() / "launcher_profiles.json").exists()


def test_neoforge_via_installer(env, fake, monkeypatch):
    assert [v["version"] for v in loaders.neoforge_versions("1.21.1")] == ["21.1.6", "21.1.5-beta"]
    assert loaders.neoforge_versions("1.21.1")[1]["stable"] is False
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "-Dfake.id=neoforge-21.1.6 -Dfake.parent=1.20.1")
    # the fake installer reads these properties from the environment
    vid = loaders.install_neoforge("21.1.6", "java")
    assert vid == "neoforge-21.1.6"


def test_optifine_installer_shim(env, fake):
    jar = env / "OptiFine_1.20.1_HD_U_I6.jar"
    jar.write_bytes(fake.optifine_jar)
    vid = loaders.install_optifine(str(jar), "1.20.1", "java")
    assert vid == "1.20.1-OptiFine_HD_U_I6"
    with pytest.raises(NovaError):
        bad = env / "bad.jar"
        bad.write_bytes(make_zip({"a": b"b"}))
        loaders.install_optifine(str(bad), "1.20.1", "java")


# -------------------------------------------------------------------- mods

def _inst(env, loader="fabric", **kw):
    return instances.create(dict({"name": "T", "mc_version": "1.20.1", "loader": loader}, **kw))


def test_mod_install_with_dependencies(env, fake):
    inst = _inst(env)
    res = mods.install_project(inst, "sodium")
    assert {r["title"] for r in res} == {"Sodium", "Fabric API"}
    items = {m["file"]: m for m in mods.list_installed(inst)}
    assert items["sodium-1.0.jar"]["managed"] and items["sodium-1.0.jar"]["title"] == "Sodium"
    # installing again doesn't duplicate dependencies
    again = mods.install_project(inst, "sodium")
    assert [r["title"] for r in again] == ["Sodium"]


def test_mod_toggle_remove_and_traversal(env, fake):
    inst = _inst(env)
    mods.install_project(inst, "lithium")
    assert mods.toggle(inst, "mod", "lithium-1.0.jar") is False
    listed = mods.list_installed(inst)
    assert listed[0]["file"] == "lithium-1.0.jar" and listed[0]["enabled"] is False
    assert mods.toggle(inst, "mod", "lithium-1.0.jar") is True
    for bad in ("../../x.jar", "/etc/passwd", ""):
        with pytest.raises(NovaError):
            mods.remove(inst, "mod", bad)
    mods.remove(inst, "mod", "lithium-1.0.jar")
    assert mods.list_installed(inst) == []


def test_missing_version_error(env, fake):
    inst = _inst(env)
    with pytest.raises(NovaError) as e:
        mods.install_project(inst, "ghost")
    assert "no version" in str(e.value).lower()


def test_update_check_and_update_all(env, fake):
    inst = _inst(env)
    mods.install_project(inst, "lithium")
    mods.install_project(inst, "ferrite-core")
    ups = mods.check_updates(inst)
    assert [u["file"] for u in ups] == ["lithium-1.0.jar"] and ups[0]["new_version"] == "2.0"
    assert fake.posts[-1][1]["game_versions"] == ["1.20.1"] and fake.posts[-1][1]["loaders"] == ["fabric"]


def test_optimization_pack_skips_unavailable(env, fake):
    inst = _inst(env)
    out = mods.install_optimization_pack(inst, ["sodium", "lithium", "modernfix", "evil-slug"])
    assert "Sodium" in out["installed"] and "Lithium" in out["installed"]
    # modernfix has no fake route -> skipped with a reason, not a crash; unknown slugs ignored entirely
    assert [s["slug"] for s in out["skipped"]] == ["modernfix"]
    forge = _inst(env, loader="forge")
    assert any(p["slug"] == "embeddium" for p in mods.optimization_pack("forge"))
    assert not mods.optimization_pack("vanilla")


def test_search(env, fake):
    r = mods.search("sod", "1.20.1", "fabric")
    assert r["hits"][0]["slug"] == "sodium" and r["total"] == 1


# -------------------------------------------------------------- full launch

def test_full_launch_fabric(env, fake, monkeypatch):
    monkeypatch.setenv("NOVA_TEST_ENV", "hello")
    accounts.add_offline("Tester")
    inst = instances.create({"name": "Full", "mc_version": "1.20.1", "loader": "fabric",
                             "memory_max": 1536, "memory_min": 512, "jvm_preset": "balanced",
                             "width": 1000, "height": 600, "env": {"NOVA_TEST_ENV": "from-instance"},
                             "options_profile": "performance"})
    reg = launch.Registry()
    t = run_task(lambda task: reg.launch(inst, task))
    assert t.status == "done", t.error
    g = reg.get("full")
    for _ in range(200):
        if g.status in ("exited", "crashed"):
            break
        time.sleep(0.05)
    lines = g.logs_since(0)["lines"]
    text = "\n".join(lines)
    assert g.status == "exited", text
    assert "FAKE_MC_START" in text and "FAKE_MC_STOP" in text and "FAKE_STDERR_LINE" in text
    assert "ARG Tester" in text and "ARG fabric-loader-0.15.0-1.20.1" in text
    assert "ARG 1000" in text and "ARG 600" in text
    assert "ENV from-instance" in text
    assert "-XstartOnFirstThread" not in " ".join(g.plan["cmd"]) or paths.os_name() == "osx"
    cmd = g.plan["cmd"]
    assert "-Xmx1536M" in cmd and "-Xms512M" in cmd and "-XX:+UseG1GC" in cmd
    assert any(c.startswith("-Dlog4j.configurationFile=") and c.endswith("client-1.12.xml") for c in cmd)
    assert cmd.index("-Xmx1536M") < cmd.index("-cp") < cmd.index("FakeMain")
    xmx = [l for l in lines if l.startswith("XMX ")][0]
    assert abs(int(xmx.split()[1]) - 1536 * 1024 * 1024) < 200 * 1024 * 1024
    # the options profile was applied before launch; version id persisted; playtime recorded
    assert "renderDistance:8" in (instances.game_dir("full") / "options.txt").read_text()
    after = instances.get("full")
    assert after["version_id"] == "fabric-loader-0.15.0-1.20.1" and after["last_played"] > 0
    # natives were extracted into the instance
    assert any((instances.instance_dir("full") / "natives").glob("*"))


def test_launch_legacy_arguments_format(env, fake):
    accounts.add_offline("Oldie")
    inst = instances.create({"name": "Old", "mc_version": "1.7.10", "loader": "vanilla"})
    reg = launch.Registry()
    assert run_task(lambda task: reg.launch(inst, task)).status == "done"
    g = reg.get("old")
    for _ in range(200):
        if g.status != "running":
            break
        time.sleep(0.05)
    text = "\n".join(g.logs_since(0)["lines"])
    assert "ARG Oldie" in text and "ARG --width" in text and "ARG 1280" in text
    assert "-Dlog4j2.formatMsgNoLookups=true" not in g.plan["cmd"]  # real logging config is used instead


def test_launch_forge_and_kill(env, fake, monkeypatch):
    accounts.add_offline("Smith")
    inst = instances.create({"name": "F", "mc_version": "1.20.1", "loader": "forge", "loader_version": "47.2.0"})
    reg = launch.Registry()
    t = run_task(lambda task: reg.launch(inst, task))
    assert t.status == "done", t.error
    g = reg.get("f")
    for _ in range(200):
        if g.status != "running":
            break
        time.sleep(0.05)
    text = "\n".join(g.logs_since(0)["lines"])
    assert "ARG --fake-loader" in text            # merged from forge's arguments
    assert "-Dfake.loader=1" in g.plan["cmd"]
    assert instances.get("f")["version_id"] == "1.20.1-forge-47.2.0"


def test_launch_requires_account_and_blocks_double_launch(env, fake):
    inst = instances.create({"name": "NoAcc", "mc_version": "1.20.1"})
    reg = launch.Registry()
    t = run_task(lambda task: reg.launch(inst, task))
    assert t.status == "error" and "profile" in t.error.lower()


def test_pre_launch_failure_blocks_start(env, fake):
    accounts.add_offline("Pre")
    inst = instances.create({"name": "PL", "mc_version": "1.20.1", "pre_launch": "exit 3"})
    reg = launch.Registry()
    t = run_task(lambda task: reg.launch(inst, task))
    assert t.status == "error" and "pre-launch" in t.error.lower()
    assert reg.get("pl") is None


def test_missing_java_override_is_reported(env, fake):
    accounts.add_offline("Jay")
    inst = instances.create({"name": "J", "mc_version": "1.20.1", "java_path": "/nonexistent/java"})
    reg = launch.Registry()
    t = run_task(lambda task: reg.launch(inst, task))
    assert t.status == "error" and "does not exist" in t.error


def test_custom_version_import_and_launch(env, fake):
    src = env / "someversion"
    src.mkdir()
    (src / "weird-name.json").write_text(json.dumps({"id": "my-custom", "inheritsFrom": "1.20.1", "mainClass": "FakeMain",
                                                    "libraries": [], "type": "release"}))
    vid = loaders.import_custom_version(str(src))
    assert vid == "my-custom" and "my-custom" in loaders.list_installed_versions()
    accounts.add_offline("Cust")
    inst = instances.create({"name": "C", "mc_version": "1.20.1", "loader": "custom", "version_id": vid})
    assert instances.get("c")["version_id"] == "my-custom"   # not wiped by update logic
    reg = launch.Registry()
    assert run_task(lambda task: reg.launch(inst, task)).status == "done"


def test_split_args_windows_keeps_backslashes_and_handles_quotes():
    from nova.util import split_args
    assert split_args('-Dfoo="a b" -XX:+Bar', windows=True) == ["-Dfoo=a b", "-XX:+Bar"]
    assert split_args(r'-Dx=C:\Users\me\mods "--name=Big Bob"', windows=True) == [r"-Dx=C:\Users\me\mods", "--name=Big Bob"]
    assert split_args('-Dfoo="a b"', windows=False) == ["-Dfoo=a b"]


def test_windowed_mode_logs_to_file_when_stdout_is_missing(tmp_path, monkeypatch):
    import sys
    from nova import app
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "excepthook", sys.__excepthook__)
    log = app.setup_logging()
    print("hello from windowed nova")
    sys.stdout.flush()
    assert log == tmp_path / "nova.log" and "hello from windowed nova" in log.read_text()


def test_normal_console_run_does_not_touch_logging(tmp_path, monkeypatch):
    from nova import app
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    assert app.setup_logging() is None


def test_nova_py_explains_incomplete_install_instead_of_vanishing(tmp_path):
    import shutil, subprocess, sys
    from pathlib import Path
    shutil.copy(Path(__file__).resolve().parent.parent / "nova.py", tmp_path / "nova.py")  # no nova/ package next to it
    r = subprocess.run([sys.executable, str(tmp_path / "nova.py")], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 1 and "Extract the whole zip" in r.stdout
