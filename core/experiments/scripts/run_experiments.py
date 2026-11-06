"""Build and rerun fixed configurations without network access."""
import argparse, concurrent.futures, csv, json, os, platform, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--case',default='all',help='all, public, model, or an exact case id')
 p.add_argument('--config',default='experiments/config/cases.json')
 p.add_argument('--out',default='results/reproduced')
 p.add_argument('--jobs',type=int,default=2)
 p.add_argument('--reps',type=int)
 p.add_argument('--portable',action='store_true')
 p.add_argument('--cxx',default=os.environ.get('CXX','g++'))
 a=p.parse_args();out=ROOT/a.out;out.mkdir(parents=True,exist_ok=True)
 build=ROOT/'build';build.mkdir(exist_ok=True)
 exe=build/('experiment_portable' if a.portable else 'experiment')
 if os.name=='nt':exe=exe.with_suffix('.exe')
 prefix=[a.cxx,'c++'] if Path(a.cxx).stem=='zig' else [a.cxx]
 cmd=prefix+['-O3','-std=c++17',str(ROOT/'experiments/src/experiment.cpp'),'-o',str(exe)]
 if a.portable:cmd.insert(len(prefix),'-DCMS_FORCE_PORTABLE')
 subprocess.run(cmd,check=True)
 cases=json.loads((ROOT/a.config).read_text())
 cases=[c for c in cases if a.case=='all' or c['id']==a.case or c['kind']==a.case]
 if not cases:raise SystemExit('No configuration matched')
 def run(c):
  reps=a.reps or c['repetitions']
  command=[str(exe),str(ROOT/c['input']),str(c['bits']),str(c['payload_words']),str(reps),str(c['d']),str(c['absent_samples']),str(c['rep_start'])]
  start=time.perf_counter()
  target=out/(c['id']+'.csv');temporary=target.with_suffix('.csv.tmp')
  with temporary.open('w') as f:
   subprocess.run(command,stdout=f,check=True)
   f.flush();os.fsync(f.fileno())
  rows=list(csv.DictReader(temporary.open()))
  if len(rows)!=reps*13 or any(None in row or any(value is None for value in row.values()) for row in rows):raise RuntimeError('Incomplete CSV '+str(temporary))
  temporary.replace(target)
  print(c['id'],'complete',flush=True)
  return dict(case=c['id'],seconds=time.perf_counter()-start,repetitions=reps,command=command)
 start=time.perf_counter()
 with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,a.jobs)) as pool:records=list(pool.map(run,cases))
 (out/'run_environment.json').write_text(json.dumps(dict(platform=platform.platform(),python=platform.python_version(),compiler=subprocess.check_output(([a.cxx,'version'] if Path(a.cxx).stem=='zig' else [a.cxx,'--version']),text=True).splitlines()[0],build_command=cmd,portable=a.portable,elapsed_seconds=time.perf_counter()-start,runs=records,warning='Wall times cover the multi-method evaluator, not isolated streaming throughput.'),indent=2))
if __name__=='__main__':main()
