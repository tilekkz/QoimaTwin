from pathlib import Path
import sys
import runpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
name=sys.argv[sys.argv.index('--')+1]
if name not in {'build_personnel','build_logistics','build_storage_environment','build_equipment','assemble_large_warehouse','export_calibration_v2'}:
    raise ValueError('Unknown v2 asset build')
remaining=sys.argv[sys.argv.index('--')+2:]
sys.argv=[str(HERE/(name+'.py'))]+(['--']+remaining if remaining else [])
runpy.run_path(str(HERE/(name+'.py')),run_name='__main__')
