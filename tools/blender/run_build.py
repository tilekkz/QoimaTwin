"""Blender does not automatically add the --python script directory to sys.path."""
from pathlib import Path
import runpy
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
name=sys.argv[sys.argv.index('--')+1]
if name not in {'build_environment','build_rack_bay','build_crate','build_picker_cart','build_packing_station','build_forklift','build_ibc_tote','build_buffer_pallet','assemble_warehouse'}:
    raise ValueError('Unknown project asset build')
runpy.run_path(str(HERE/(name+'.py')),run_name='__main__')
