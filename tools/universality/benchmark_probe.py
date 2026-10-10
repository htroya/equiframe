"""Installed benchmark profile: payload, capability, true and false API cases."""

import argparse
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

p = argparse.ArgumentParser()
for name in ("manifest", "wheel", "source", "output"):
    p.add_argument("--" + name, type=Path, required=True)
p.add_argument("--profile", required=True)
a = p.parse_args()
spec = importlib.util.spec_from_file_location(
    "profile_probe", Path(__file__).with_name("compatibility_probe.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
binding = m.runtime_binding(json.loads(a.manifest.read_text()))
import equiframe_benchmark as eb

if eb.__version__ != "0.12.0a11":
    raise ValueError("Wrong benchmark candidate")
if any(name in sys.modules for name in m.OPTIONAL):
    raise ValueError("Eager optional import")
site = Path(eb.__file__).resolve().parents[1]
if not site.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Benchmark is not installed")
with zipfile.ZipFile(a.wheel) as z:
    for name in z.namelist():
        if not name.startswith("equiframe_benchmark/") or name.endswith("/"):
            continue
        if (site / name).read_bytes() != z.read(name):
            raise ValueError("Benchmark payload differs")
available = {
    name: importlib.util.find_spec(name) is not None
    for name in ("pyarrow", "pandas", "polars", "duckdb", "sklearn", "psutil")
}
expected = {
    "pyarrow": True,
    **{
        name: a.profile in ("engines", "all") for name in ("pandas", "polars", "duckdb")
    },
    "sklearn": a.profile in ("ml", "all"),
    "psutil": a.profile in ("resources", "all"),
}
if available != expected:
    raise ValueError("Benchmark extras differ: " + repr(available))
output = a.output.parent / "public-api"
output.mkdir()
binding["base_api"] = m.base_api(a.source, output, arrow=True)
binding["tabular_api"] = m.tabular_api(output)
from pydantic import ValidationError

try:
    eb.ScaleSpec(case_id="invalid", rows=-1, width=2)
except ValidationError:
    pass
else:
    raise ValueError("Invalid benchmark scale accepted")
binding["benchmark_invalid_scale_rejected"] = True
binding["extras"] = available
if available["psutil"]:
    import psutil

    measurement = psutil.Process().memory_info()
    if measurement.rss <= 0:
        raise ValueError("Invalid actual resource observation")
    binding["observed_rss_bytes"] = measurement.rss
a.output.write_text(json.dumps(binding, indent=2) + "\n")
print(json.dumps({"profile": a.profile, "status": "PASS"}))
