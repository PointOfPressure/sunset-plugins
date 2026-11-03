#!/usr/bin/env python3
# Packs a plugin folder (horizon-native.json + mixins/<id>/) as dist/<id>-<version>.hnmod.
# Usage: tools/pack.py examples/hello-plugin
import json, pathlib, sys, zipfile

plugin = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "examples/hello-plugin").resolve()
manifest = json.loads((plugin / "horizon-native.json").read_text())
out = pathlib.Path("dist") / f"{manifest['id']}-{manifest['version']}.hnmod"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(plugin / "horizon-native.json", "horizon-native.json")
    src = plugin / "mixins" / manifest["id"]
    for f in sorted(src.iterdir()):
        if f.suffix in (".rs", ".toml"):
            z.write(f, f"mixins/{manifest['id']}/{f.name}")
print(out)
