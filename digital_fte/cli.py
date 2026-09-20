from __future__ import annotations
import argparse,json
from pathlib import Path
from .engine import TaskEngine

def build_parser():
    p=argparse.ArgumentParser(description="Run Digital FTE tasks from a vault")
    p.add_argument("--vault",type=Path,default=Path("AI_Employee_Vault"))
    sub=p.add_subparsers(dest="command",required=True); run=sub.add_parser("run"); run.add_argument("task",type=Path)
    return p

def main():
    a=build_parser().parse_args(); result=TaskEngine(a.vault).process(a.task)
    print(json.dumps(result.__dict__,default=str,indent=2)); return 0 if result.status=="completed" else 1

if __name__=="__main__": raise SystemExit(main())
