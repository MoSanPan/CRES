"""Compile all C++ programs and check selected runs against archived results."""
import argparse
import csv
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cxx',default=os.environ.get('CXX','g++'))
    args=ap.parse_args()
    prefix=[args.cxx,'c++'] if Path(args.cxx).stem=='zig' else [args.cxx]
    report={'builds':[], 'accuracy_checks':[]}
    with tempfile.TemporaryDirectory(prefix='cres_check_') as temporary:
        work=Path(temporary)
        for label,source in [('core','core/experiments/src/experiment.cpp'),
                ('extension','extension/src/experiment_extension.cpp'),
                ('throughput','throughput/benchmark.cpp')]:
            exe=work/(label+('.exe' if os.name=='nt' else ''))
            subprocess.run(prefix+['-O3','-std=c++17',source,'-o',str(exe)],cwd=ROOT,check=True)
            report['builds'].append(label)
            print('Built',label,flush=True)
            if label=='throughput':
                output=subprocess.check_output([str(exe),'--check'],text=True,cwd=ROOT)
                report['throughput_check']=output.strip()
                print(output.strip(),flush=True)
                continue
            for bits in [16,32]:
                name=f'ANU_public_prefix_{bits}_1280'
                command=[str(exe),f'core/data/inputs/ANU_public_prefix_{bits}.bin',str(bits),'1280','1','5','131072','0']
                rows=list(csv.DictReader(io.StringIO(subprocess.check_output(command,text=True,cwd=ROOT))))
                expected_rows=13 if label=='core' else 14
                assert len(rows)==expected_rows,(label,bits,len(rows))
                got={r['algorithm']:r for r in rows}
                with (ROOT/f'core/results/reference/{name}.csv').open() as handle:
                    reference={r['algorithm']:r for r in csv.DictReader(handle) if r['rep']=='0'}
                for algorithm,r in reference.items():
                    for field in ['mse','present_mse','absent_mse','query_mc_se']:
                        x,y=float(got[algorithm][field]),float(r[field])
                        assert math.isclose(x,y,rel_tol=2e-11,abs_tol=1e-16),(label,bits,algorithm,field,x,y)
                if label=='extension':
                    assert all(math.isfinite(float(r['frequency_weighted_mse'])) and float(r['frequency_weighted_mse'])>=0 for r in rows)
                report['accuracy_checks'].append(dict(program=label,bits=bits,reference_algorithms=len(reference),passed=True))
                print(label,bits,'reference comparison passed',flush=True)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
