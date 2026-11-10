"""Shared v2 output namespace; v1 source assets remain untouched."""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import asset_common as common
common.VERSION='qoima-72x48-v2'
from asset_common import *

def finish(asset_id,root,batch_runtime=None):
    root['layout_version']=common.VERSION
    if batch_runtime is None:
        batch_runtime=not root.get('preserve_articulation',False)
    return common.finish(asset_id,root,batch_runtime=batch_runtime,namespace='v2')
