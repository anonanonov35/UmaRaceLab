"""Record small finish-rule evidence from the user's metadata outside Git."""
from pathlib import Path
import argparse
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uma_lab.data import DEFAULT_INSTALL
from uma_lab.race_margins import read_finish_rules

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata',type=Path,default=DEFAULT_INSTALL/'UmamusumePrettyDerby_Data/il2cpp_data/Metadata/global-metadata.dat')
    parser.add_argument('--output',type=Path,default=Path(tempfile.gettempdir())/'uma-race-lab-build25384634/finish-rules.json')
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):
        raise ValueError('Extracted evidence must stay outside the source repository')
    rules=read_finish_rules(args.metadata)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(rules,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(args.output),'constants':rules['constants'],'categories':len(rules['horse_length_enum']),'native_bodies_recovered':False}))
