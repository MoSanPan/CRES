"""Regenerate tables, abstract reductions, and paired conditional intervals."""
import argparse,csv,json,statistics
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
LABELS={'zero':'Zero','constant':'Constant','CMS_min':'CMS min','CU_min':'CMS-CU min','CMS_mean_plus':'CMS mean projected','CS_mean_plus':'CS mean projected','CS_median_plus':'CS median projected','CMS_shrink':'CMS shrinkage','CS_shrink':'CS shrinkage','dictionary_CMS_raw':'Dictionary CMS unshrunk','proposed_affine':'Proposed affine','proposed_projected':'Proposed projected','Misra_Gries':'Misra-Gries'}
def writecsv(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--results',default='results/reference');p.add_argument('--out',default='results/derived');p.add_argument('--bootstrap',type=int,default=20000);a=p.parse_args()
 dest=ROOT/a.out;dest.mkdir(parents=True,exist_ok=True)
 cases=json.loads((ROOT/'experiments/config/cases.json').read_text());summary=[];arrays={}
 for c in cases:
  file=ROOT/a.results/(c['id']+'.csv')
  if not file.exists():raise ValueError('Missing configuration '+c['id'])
  rows=list(csv.DictReader(file.open()))
  for alg in LABELS:
   rr=sorted([r for r in rows if r['algorithm']==alg],key=lambda r:int(r['rep']))
   if len(rr)!=20 or [int(r['rep']) for r in rr]!=list(range(20)):raise ValueError('Official summaries require reps 0..19: '+c['id']+' '+alg)
   v=np.array([float(r['mse']) for r in rr]);arrays[c['id'],alg]=v
   summary.append(dict(configuration=c['id'],kind=c['kind'],bits=c['bits'],payload_words=c['payload_words'],algorithm=alg,label=LABELS[alg],mean_mse=float(v.mean()),se_mse=float(v.std(ddof=1)/np.sqrt(20)),mean_present_mse=statistics.mean(float(r['present_mse']) for r in rr),mean_absent_mse=statistics.mean(float(r['absent_mse']) for r in rr),mean_query_mc_se=statistics.mean(float(r['query_mc_se']) for r in rr)))
 writecsv(dest/'summary_by_configuration.csv',summary)
 public=[c for c in cases if c['kind']=='public'];contributions=[];aggregates=[]
 rng=np.random.default_rng(20261026);draws=rng.integers(0,20,size=(a.bootstrap,20))
 for alg in LABELS:
  if alg=='proposed_projected':continue
  gain=[];bybits={16:[],32:[]};boot=np.zeros(a.bootstrap)
  for c in public:
   A=arrays[c['id'],'proposed_projected'];B=arrays[c['id'],alg]
   v=100*(1-A.mean()/B.mean());gain.append(v);bybits[c['bits']].append(v)
   contributions.append(dict(configuration=c['id'],baseline=alg,reduction_percent=v))
   if a.bootstrap:boot+=100*(1-A[draws].mean(axis=1)/B[draws].mean(axis=1))/len(public)
  lo,hi=np.quantile(boot,[.025,.975]) if a.bootstrap else [float('nan')]*2
  aggregates.append(dict(baseline=alg,label=LABELS[alg],macro_reduction_percent=float(np.mean(gain)),mean16_percent=float(np.mean(bybits[16])),mean32_percent=float(np.mean(bybits[32])),configurations=len(gain),paired_ci_low=float(lo),paired_ci_high=float(hi)))
 writecsv(dest/'reduction_by_configuration.csv',contributions);writecsv(dest/'macro_reductions.csv',aggregates)
 targets={r['baseline']:r for r in aggregates if r['baseline'] in ['CS_mean_plus','CS_shrink']}
 (dest/'abstract_numbers.json').write_text(json.dumps(dict(definition='Average 20 repetitions within each setting, then equally average 12 setting-specific percentage reductions.',comparators=targets,bootstrap_replicates=a.bootstrap,bootstrap_seed=20261026),indent=2))
 with (dest/'macro_table.tex').open('w') as f:
  f.write('\\begin{tabular}{lr}\\hline\nBaseline & Mean MSE reduction (\\%)\\\\\\hline\n')
  for r in aggregates:
   f.write(r['label']+' & '+f"{r['macro_reduction_percent']:.2f}"+'\\\\\n')
  f.write('\\hline\\end{tabular}\n')
 print(json.dumps(targets,indent=2))
if __name__=='__main__':main()
