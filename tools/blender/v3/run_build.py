"""Run one local V3 build module in a fresh background Blender process.

blender --background --factory-startup --threads 2 --python
tools/blender/v3/run_build.py -- build_calibration
"""
from pathlib import Path
import re
import runpy
import sys

import bpy

HERE = Path(__file__).resolve().parent
if not bpy.app.background:
    raise RuntimeError("V3 builds must not clear a user's live Blender scene")
if "--" not in sys.argv or len(sys.argv) <= sys.argv.index("--") + 1:
    raise ValueError("Pass a local build module after --")
arguments = sys.argv[sys.argv.index("--") + 1:]
name = arguments[0].removesuffix(".py")
if not re.fullmatch(r"(?:build|assemble)_[a-z0-9_]+", name):
    raise ValueError("Only local V3 build_/assemble_ modules are allowed")
script = HERE / (name + ".py")
if not script.is_file():
    raise FileNotFoundError(script)
sys.path.insert(0, str(HERE))
sys.argv = [str(script)] + (["--"] + arguments[1:] if len(arguments) > 1 else [])
runpy.run_path(str(script), run_name="__main__")
