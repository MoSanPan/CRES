"""Frozen-protocol extension; reads the original package without modifying it."""
import argparse, concurrent.futures, csv, hashlib, io, json, math, os, platform, re, statistics, subprocess, time, zipfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT.parent / 'core'
METRICS = ['mse', 'present_mse', 'absent_mse', 'frequency_weighted_mse', 'query_mc_se']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def prepare():
    manifest, cases = [], []
    def save(name, values, provenance):
        p = ROOT / 'inputs' / (name + '.bin')
        data = np.asarray(values, dtype='<u4').tobytes()
        p.write_bytes(data)
        manifest.append(dict(input=name, sha256=sha(data), T=len(values), **provenance))
        return name
    public = {'ANU_public_prefix': (ORIGINAL / 'data/raw/ANU_public_prefix.raw').read_bytes()}
    with zipfile.ZipFile(ORIGINAL / 'data/archives/IBM_trials.zip') as z:
        for device in ['Belem', 'Quito']:
            pat = re.compile(r'S_2023_trials/' + device + r'/Basic_QRNG_' + device + r'/Basic_QRNG_' + device + r'_(\d+)\.txt')
            names = sorted((n for n in z.namelist() if pat.fullmatch(n)), key=lambda n: int(pat.fullmatch(n).group(1)))
            bitstr = ''.join(''.join(z.read(n).decode('ascii').split()) for n in names)
            if set(bitstr) - set('01') or len(bitstr) % 8:
                raise ValueError('invalid IBM input')
            public['IBM_' + device] = np.packbits(np.frombuffer(bitstr.encode(), dtype=np.uint8) - 48).tobytes()
            assert public['IBM_' + device][:65536] == (ORIGINAL / ('data/raw/IBM_' + device + '.raw')).read_bytes()
            (ROOT / 'validation' / ('IBM_' + device + '_members.json')).write_text(json.dumps(names, indent=2), encoding='utf8')
    def add(group, inp, bits, words, residual_fraction=.5, stream_id=0, **meta):
        width = int((words // 5) * residual_fraction)
        idx = len(cases)
        cases.append(dict(id=f'{group}_{idx:03}', group=group, input=inp, bits=bits, payload_words=words,
            d=5, residual_width=width, residual_fraction=residual_fraction, stream_id=stream_id,
            repetitions=5, rep_start=100, absent_samples=131072, **meta))
    for name, raw in public.items():
        for bits in [16, 32]:
            stride = bits // 8
            for block in range(4):
                start, stop = block * 8192 * stride, (block + 1) * 8192 * stride
                values = np.frombuffer(raw[start:stop], dtype='>u2' if bits == 16 else '>u4')
                assert len(values) == 8192
                inp = save(f'{name}_{bits}_block{block}', values, dict(kind='public_nonoverlapping_block', source=name, bits=bits, byte_start=start, byte_stop=stop, full_raw_sha256=sha(raw)))
                for words in [1280, 5120]:
                    add('public_blocks', inp, bits, words, stream_id=block, source=name, T=8192)
    anu = public['ANU_public_prefix']
    for length in [4096, 16384, 65536, 262144]:
        inp = save(f'ANU_scale_T{length}', np.frombuffer(anu[:length*4], dtype='>u4'), dict(kind='public_nested_prefix', source='ANU_public_prefix', bits=32, byte_start=0, byte_stop=length*4, full_raw_sha256=sha(anu)))
        for words in [320, 1280, 5120, 20480]:
            add('scale_budget', inp, 32, words, source='ANU_public_prefix', T=length)
    allocation_inputs = []
    for name, bits in [('ANU_public_prefix', 16), ('ANU_public_prefix', 32), ('IBM_Belem', 32)]:
        stride = bits//8
        inp=save(f'{name}_{bits}_allocation', np.frombuffer(public[name][:16384*stride], dtype='>u2' if bits==16 else '>u4'), dict(kind='public_prefix', source=name, bits=bits, byte_start=0, byte_stop=16384*stride))
        allocation_inputs.append((inp,bits,name))
    for beta in [0., 2**-10, 2**-5, .125, .5]:
        for stream in range(4):
            seed=2026102900+stream
            rng=np.random.default_rng(seed)
            x=rng.integers(0,2**32,16384,dtype=np.uint32)
            keep=rng.random(len(x))<beta
            for i in range(1,len(x)):
                if keep[i]:x[i]=x[i-1]
            inp=save(f'sticky_b{beta:g}_s{stream}',x,dict(kind='model', model='sticky_uniform', bits=32, beta=beta, generator='NumPy PCG64', seed=seed, conditional_collision_entropy=-math.log2(beta*beta+(1-beta*beta)/2**32)))
            for words in [1280,5120]:
                add('source_dependence',inp,32,words,stream_id=stream,source='sticky_uniform',beta=beta,T=16384,source_seed=seed)
            if beta==.125 and stream==0: allocation_inputs.append((inp,32,'sticky_uniform_beta_0.125'))
    for h in [12,16,24,32]:
        for stream in range(4):
            seed=2026103900+stream
            rng=np.random.default_rng(seed)
            x=rng.integers(0,2**h,16384,dtype=np.uint32)
            inp=save(f'uniform_h{h}_s{stream}',x,dict(kind='model',model='uniform_fixed_support',bits=32,support_bits=h,conditional_collision_entropy=h,generator='NumPy PCG64',seed=seed))
            for words in [1280,5120]:
                add('source_entropy',inp,32,words,stream_id=stream,source='uniform_fixed_support',support_bits=h,T=16384,source_seed=seed)
    for inp,bits,name in allocation_inputs:
        for words in [1280,5120]:
            for fraction in [.125,.25,.5,1.]:
                add('allocation',inp,bits,words,residual_fraction=fraction,source=name,T=16384)
    protocol=dict(created='2026-10-29',frozen_before_execution=True,case_count=len(cases),hash_repetitions=5,
        hash_rep_start=100,hash_seed='2026102600 + rep',absent_query_seed='7740041 + rep',absent_samples=131072,
        public_block_dependence='Nonoverlapping byte blocks; no claim of probabilistic independence. 16/32-bit encodings share raw bytes.',
        source_repeats='Four separately seeded model realizations per beta or support setting, with five hash/query repetitions within each realization.',
        parameter_pairing='The same four seeds are reused across beta levels (and a separate seed family across support levels) as common random numbers; parameter settings are not independent source replicates.',
        comparators=dict(total=14,original_retained=13,added='CMM_mean: local implementation of median rowwise collision correction, clipped to [0, minimum CMS bucket]. Not author code.'),
        no_pooling='Do not pool public, scale, allocation, dependence and entropy studies into original 12-configuration headline.',
        no_dictionary_baseline='All allocations retain a residual CMS; fraction 1 is the no-dictionary full CMS endpoint.',
        queries='Full-universe MSE; present-key uniform MSE; frequency-weighted MSE = sum f_q(error_q)^2 / T. The last is an explicit sensitivity workload, not an observed business workload.',
        original_results='Original package, source and results are read-only.')
    for filename,obj in [('cases.json',cases),('input_manifest.json',manifest),('protocol.json',protocol)]:
        (ROOT/filename).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf8')
    print('prepared',len(cases),'cases',len(manifest),'inputs',flush=True)

def execute_case(exe, c, target):
    command=[str(exe),str(Path('inputs')/(c['input']+'.bin')),str(c['bits']),str(c['payload_words']),str(c['repetitions']),str(c['d']),str(c['absent_samples']),str(c['rep_start']),str(c['residual_width'])]
    start=time.perf_counter()
    tmp=target.with_suffix('.csv.tmp')
    with tmp.open('w',encoding='utf8',newline='') as f:
        subprocess.run(command,stdout=f,check=True,cwd=ROOT)
    rows=list(csv.DictReader(tmp.open(encoding='utf8')))
    assert len(rows)==14*c['repetitions'],c['id']
    assert len({(r['algorithm'],r['rep']) for r in rows})==len(rows)
    assert all(math.isfinite(float(r[m])) and float(r[m])>=0 for r in rows for m in METRICS)
    u=2**c['bits']
    for r in rows:
        assert math.isclose(float(r['mse']),float(r['K'])/u*float(r['present_mse'])+(1-float(r['K'])/u)*float(r['absent_mse']),rel_tol=2e-12,abs_tol=1e-17)
    tmp.replace(target)
    record=dict(case=c['id'],seconds=time.perf_counter()-start,command=command,sha256=sha(target.read_bytes()),rows=len(rows))
    (ROOT/'validation'/(c['id']+'_run.json')).write_text(json.dumps(record,indent=2),encoding='utf8')
    return record

def regression(exe):
    reports=[]
    for bits in [16,32]:
        source=ORIGINAL/f'data/inputs/ANU_public_prefix_{bits}.bin'
        target=ROOT/'validation'/f'regression_ANU_{bits}.csv'
        local=ROOT/'inputs'/f'regression_ANU_{bits}.bin'
        local.write_bytes(source.read_bytes())
        command=[str(exe),str(Path('inputs')/local.name),str(bits),'1280','1','5','131072','0']
        with target.open('w',encoding='utf8',newline='') as f:subprocess.run(command,stdout=f,check=True,cwd=ROOT)
        got={r['algorithm']:r for r in csv.DictReader(target.open(encoding='utf8'))}
        reference={r['algorithm']:r for r in csv.DictReader((ORIGINAL/f'results/reference/ANU_public_prefix_{bits}_1280.csv').open(encoding='utf8')) if r['rep']=='0'}
        errors=[]
        for alg in reference:
            for field in ['mse','present_mse','absent_mse','query_mc_se']:
                a,b=float(got[alg][field]),float(reference[alg][field])
                assert math.isclose(a,b,rel_tol=2e-11,abs_tol=1e-16),(bits,alg,field,a,b)
                errors.append(abs(a-b))
        reports.append(dict(bits=bits,original_algorithms=len(reference),total_algorithms=len(got),max_absolute_numeric_difference=max(errors),passed=True,command=command))
    (ROOT/'validation/regression.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
    print('original-result regression passed',flush=True)

def summarize():
    cases=json.loads((ROOT/'cases.json').read_text(encoding='utf8'))
    allrows=[]; summaries=[]; missing=[]
    for c in cases:
        p=ROOT/'results'/(c['id']+'.csv')
        if not p.exists():missing.append(c['id']);continue
        rows=list(csv.DictReader(p.open(encoding='utf8')))
        for r in rows:
            allrows.append(dict(case_id=c['id'],group=c['group'],source_name=c['source'],stream_id=c['stream_id'],residual_fraction=c['residual_fraction'],beta=c.get('beta',''),support_bits=c.get('support_bits',''),**r))
        for alg in sorted({r['algorithm'] for r in rows}):
            ar=[r for r in rows if r['algorithm']==alg]
            out=dict(case_id=c['id'],group=c['group'],source_name=c['source'],stream_id=c['stream_id'],bits=c['bits'],T=c['T'],payload_words=c['payload_words'],residual_fraction=c['residual_fraction'],beta=c.get('beta',''),support_bits=c.get('support_bits',''),algorithm=alg,n_hash_repetitions=len(ar))
            for metric in METRICS:
                values=[float(r[metric]) for r in ar]
                out[metric+'_mean']=statistics.mean(values)
                out[metric+'_hash_se']=statistics.stdev(values)/math.sqrt(len(values)) if len(values)>1 else 0
            summaries.append(out)
    if allrows:
        for filename,rows in [('all_results.csv',allrows),('summary_by_configuration.csv',summaries)]:
            with (ROOT/filename).open('w',encoding='utf8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report=dict(expected_cases=len(cases),completed_cases=len(cases)-len(missing),missing=missing,total_rows=len(allrows),original_results_modified=False)
    (ROOT/'validation/completeness.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)

def main():
    for directory in ['inputs','validation','build','results']:
        (ROOT/directory).mkdir(parents=True,exist_ok=True)
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--cxx');ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--group',default='all');ap.add_argument('--limit',type=int);ap.add_argument('--summarize',action='store_true');a=ap.parse_args()
    if a.prepare:prepare()
    if a.cxx:
        exe=ROOT/'build'/('experiment_extension.exe' if os.name=='nt' else 'experiment_extension')
        cmd=([a.cxx,'c++'] if Path(a.cxx).stem=='zig' else [a.cxx])+['-O3','-std=c++17',str(ROOT/'src/experiment_extension.cpp'),'-o',str(exe)]
        subprocess.run(cmd,check=True)
        regression(exe)
        cases=json.loads((ROOT/'cases.json').read_text(encoding='utf8'))
        chosen=[c for c in cases if a.group=='all' or c['group']==a.group]
        if a.limit:chosen=chosen[:a.limit]
        chosen=[c for c in chosen if not (ROOT/'results'/(c['id']+'.csv')).exists() or not (ROOT/'validation'/(c['id']+'_run.json')).exists()]
        started=time.perf_counter();records=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
            futures={pool.submit(execute_case,exe,c,ROOT/'results'/(c['id']+'.csv')):c for c in chosen}
            for fut in concurrent.futures.as_completed(futures):
                result=fut.result();records.append(result);print(result['case'],'complete',round(result['seconds'],3),'s',flush=True)
        envpath=ROOT/'run_environment.json'
        old=json.loads(envpath.read_text(encoding='utf8')) if envpath.exists() else dict(runs=[])
        old.update(platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,working_directory=str(ROOT),compiler=subprocess.check_output([a.cxx,'version'] if Path(a.cxx).stem=='zig' else [a.cxx,'--version'],text=True).splitlines()[0],build_command=cmd,source_sha256=sha((ROOT/'src/experiment_extension.cpp').read_bytes()),executable_sha256=sha(exe.read_bytes()),last_elapsed_seconds=time.perf_counter()-started,warning='Case wall times are combined evaluator times, not per-method throughput.')
        old['runs']+=records;envpath.write_text(json.dumps(old,indent=2),encoding='utf8')
        summarize()
    elif a.summarize:summarize()

if __name__=='__main__':main()
