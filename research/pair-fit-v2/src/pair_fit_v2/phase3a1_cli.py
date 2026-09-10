import argparse, json
from pathlib import Path
from pair_fit_v2 import phase3a1_shot_zone_acquisition as phase
def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--cache-root",type=Path,default=Path("research/pair-fit-v2/cache")); g=p.add_mutually_exclusive_group(required=True); g.add_argument("--preview",action="store_true"); g.add_argument("--initialize",action="store_true"); g.add_argument("--live",action="store_true"); g.add_argument("--analyze",action="store_true"); g.add_argument("--residual-analyze",action="store_true"); g.add_argument("--dependency-preview",action="store_true"); g.add_argument("--dependency-initialize",action="store_true"); g.add_argument("--dependency-live",action="store_true"); a=p.parse_args(argv)
    result=phase.planned(a.cache_root) if a.preview else phase.initialize(a.cache_root) if a.initialize else phase.acquire(a.cache_root,live=True,policy=phase.RESIDUAL_RECONCILIATION_POLICY) if a.live else phase.analyze(a.cache_root) if a.analyze else phase.analyze_residual_window(a.cache_root,policy=phase.RESIDUAL_RECONCILIATION_POLICY) if a.residual_analyze else phase.dependency_preview(a.cache_root) if a.dependency_preview else phase.initialize_dependency(a.cache_root) if a.dependency_initialize else phase.acquire_dependency(a.cache_root,live=True)
    print(json.dumps(result,indent=2,sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
