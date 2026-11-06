"""Compare every numerical output with the retained same-setting references."""
import argparse,csv,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def keyed(p):return {(r['algorithm'],int(r['rep'])):r for r in csv.DictReader(p.open())}
def main():
 (ROOT/'validation').mkdir(parents=True,exist_ok=True)
 ap=argparse.ArgumentParser();ap.add_argument('--results',default='results/reproduced');a=ap.parse_args()
 total=0;maxrel=0.;checks=[]
 for case in json.loads((ROOT/'experiments/config/cases.json').read_text()):
  p=ROOT/a.results/(case['id']+'.csv')
  if not p.exists():continue
  got=keyed(p);ref=keyed(ROOT/'results/reference'/p.name)
  for key,r in got.items():
   e=ref[key]
   for col in ['mse','present_mse','absent_mse','query_mc_se']:
    x,y=float(r[col]),float(e[col]);rel=abs(x-y)/max(abs(y),1e-30);maxrel=max(maxrel,rel)
    if not math.isclose(x,y,rel_tol=1e-9,abs_tol=1e-18):raise AssertionError((case['id'],key,col,x,y))
   for col in ['bits','T','K','payload_words','d','w0','w','k','absent_samples']:
    if r[col]!=e[col]:raise AssertionError((case['id'],key,col,r[col],e[col]))
  total+=len(got);checks.append(dict(case=case['id'],records=len(got)))
 if not checks:raise SystemExit('No reproduced CSV found')
 out=dict(passed=True,configurations=len(checks),records=total,maximum_relative_difference=maxrel,checks=checks)
 (ROOT/'validation'/('reproduction_'+Path(a.results).name+'.json')).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
