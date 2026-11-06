"""Build/check and optionally run isolated algorithm timings; never touches original results."""
import argparse,csv,hashlib,json,os,platform,statistics,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def detect_cpu():
    """Record this run's processor, rather than the historical experiment host."""
    if os.name=='nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                name=winreg.QueryValueEx(key,'ProcessorNameString')[0].strip()
                if name:return name
        except (ImportError,OSError,AttributeError):
            pass
    return platform.processor().strip() or platform.machine() or 'unknown'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--compiler',required=True,help='C++ compiler executable (g++, clang++, or zig)')
    p.add_argument('--run',action='store_true',help='Run only when other experiments have finished')
    p.add_argument('--skip-build',action='store_true')
    p.add_argument('--length',type=int,default=1048576)
    p.add_argument('--queries',type=int,default=262144)
    p.add_argument('--reps',type=int,default=5)
    a=p.parse_args()
    exe=ROOT/('benchmark.exe' if os.name=='nt' else 'benchmark')
    prefix=[a.compiler,'c++'] if Path(a.compiler).stem=='zig' else [a.compiler]
    cmd=prefix+['-O3','-std=c++17',str(ROOT/'benchmark.cpp'),'-o',str(exe)]
    if not a.skip_build:subprocess.run(cmd,check=True)
    check=subprocess.check_output([str(exe),'--check'],text=True)
    (ROOT/'correctness_check.txt').write_text(check,encoding='utf8')
    env={'platform':platform.platform(),'machine':platform.machine(),'python':platform.python_version(),'cpu':detect_cpu(),'compiler_version':subprocess.check_output(([a.compiler,'version'] if Path(a.compiler).stem=='zig' else [a.compiler,'--version']),text=True).strip(),'build_command':cmd,'correctness':check.strip(),'memory_definition':'sizeof(single state object) + capacity()*sizeof(element) for its owned vectors; includes Hash coefficient buffer, vector control blocks, scalar caches, padding and dictionary Entries; excludes allocator metadata, input/query vectors, executable/runtime and OS process RSS','timing_definition':'steady_clock, per-method update and two separate query loops; allocation, input generation, validation, hash initialization and final shrink coefficient calculation excluded; dictionary maintenance, per-update/per-query hash evaluations and checksum accumulation included','hash_seed':'2026102600 + repetition, warmup uses repetition 0','stream_seed':2026102901,'query_seed':2026102902,'order_seed':2026102903,'warmup_rounds':1,'counted_rounds':a.reps,'query_workloads':'present: uniform sample of stream positions (empirical frequency weighted); uniform: independent 32-bit keys over the whole universe, may contain very few present keys','source_hashes':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['benchmark.cpp','original_components.hpp','run_benchmark.py']}}
    if a.run:
        run=[str(exe),str(a.length),str(a.queries),str(a.reps)]
        start=time.perf_counter()
        with (ROOT/'timings.csv').open('w',encoding='utf8',newline='') as f:subprocess.run(run,stdout=f,check=True)
        env.update(run_command=run,elapsed_seconds=time.perf_counter()-start,run_completed=True)
        rows=list(csv.DictReader((ROOT/'timings.csv').open(encoding='utf8')))
        if len(rows)!=10*(a.reps+1):raise RuntimeError('Incomplete timing rows')
        summaries=[]
        for M in [1280,5120]:
            for algorithm in ['CMS_shrink','CS_shrink','proposed_projected','Misra_Gries','CMM_mean']:
                group=[r for r in rows if int(r['payload_words'])==M and r['algorithm']==algorithm and r['warmup']=='0']
                assert len(group)==a.reps
                result={'algorithm':algorithm,'payload_words':M,'T':a.length,'queries':a.queries,'runs':len(group),'state_and_capacity_bytes':int(group[0]['state_and_capacity_bytes'])}
                for label,column,n in [('update','update_seconds',a.length),('present_query','present_query_seconds',a.queries),('uniform_query','uniform_query_seconds',a.queries)]:
                    rates=[n/float(r[column])/1e6 for r in group]
                    result[label+'_mops_mean']=statistics.mean(rates)
                    result[label+'_mops_median']=statistics.median(rates)
                    result[label+'_mops_min']=min(rates)
                    result[label+'_mops_max']=max(rates)
                summaries.append(result)
        with (ROOT/'summary.csv').open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
        (ROOT/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf8')
        print(json.dumps(summaries,indent=2))
    (ROOT/'environment.json').write_text(json.dumps(env,indent=2),encoding='utf8')

if __name__=='__main__':main()
