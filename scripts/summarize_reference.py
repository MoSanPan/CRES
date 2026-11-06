"""Recompute equal-configuration mean reductions from archived per-run results."""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def reductions(rows, fields, case_key):
    samples = defaultdict(list)
    for row in rows:
        for metric in fields:
            samples[(row[case_key], row['algorithm'], metric)].append(float(row[metric]))
    means = {key: statistics.mean(values) for key, values in samples.items()}
    cases = sorted({key[0] for key in means})
    algorithms = sorted({key[1] for key in means} - {'proposed_projected'})
    output = []
    for metric in fields:
        for baseline in algorithms:
            values = []
            for case in cases:
                a = means[(case, 'proposed_projected', metric)]
                b = means[(case, baseline, metric)]
                values.append(None if b == 0 else 100 * (1 - a / b))
            undefined = [case for case, value in zip(cases, values) if value is None]
            output.append(dict(metric=metric, baseline=baseline,
                mean_relative_reduction_percent=None if undefined else statistics.mean(values),
                undefined_configurations=undefined))
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'reports')
    args = parser.parse_args()
    core = []
    configs = json.loads((ROOT/'core/experiments/config/cases.json').read_text())
    for case in configs:
        if case['kind'] != 'public':
            continue
        with (ROOT/'core/results/reference'/(case['id']+'.csv')).open(newline='') as handle:
            for row in csv.DictReader(handle):
                row['case_id'] = case['id']
                core.append(row)
    with (ROOT/'reference_results/extension/all_results.csv').open(newline='') as handle:
        extension = [r for r in csv.DictReader(handle) if r['group']=='public_blocks']
    result = dict(
        definition='Average MSE within each configuration, compute 100*(1-CRES/baseline), then average configurations equally. A zero baseline denominator leaves the whole-collection mean undefined.',
        core=reductions(core, ['mse'], 'case_id'),
        stream_blocks=reductions(extension, ['mse','present_mse','frequency_weighted_mse'], 'case_id'))
    # The paper compares per-configuration risk ratios, not ratios of pooled MSE.
    other_blocks = [r for r in extension if not (
        r['source_name'] == 'IBM_Belem' and r['bits'] == '32' and r['stream_id'] == '3'
    )]
    workloads = ['present_mse', 'frequency_weighted_mse']
    def cmm_reductions(summary):
        return {row['metric']: row['mean_relative_reduction_percent'] for row in summary
                if row['metric'] in workloads and row['baseline'] == 'CMM_mean'}

    full = cmm_reductions(result['stream_blocks'])
    sensitivity = cmm_reductions(reductions(other_blocks, workloads, 'case_id'))
    result['cmm_workloads'] = {
        'all_configuration_count': len({r['case_id'] for r in extension}),
        'sensitivity_configuration_count': len({r['case_id'] for r in other_blocks}),
        'sensitivity_exclusion': 'IBM Belem, 32-bit encoding, fourth block (index 3), both payloads',
        'mean_cres_to_cmm_mse_ratio': {
            metric: None if full[metric] is None else 1 - full[metric] / 100
            for metric in workloads
        },
        'sensitivity_mean_reduction_percent': sensitivity,
    }
    with (ROOT/'reference_results/throughput/timings.csv').open(newline='') as handle:
        timings = [r for r in csv.DictReader(handle) if r['warmup']=='0']
    groups = defaultdict(list)
    for row in timings:
        groups[(row['payload_words'],row['algorithm'])].append(row)
    result['throughput'] = []
    for (words,algorithm), rows in sorted(groups.items()):
        entry = dict(payload_words=int(words),algorithm=algorithm)
        for label,time_col,n_col in [('update','update_seconds','T'),
                ('present_query','present_query_seconds','queries'),
                ('uniform_query','uniform_query_seconds','queries')]:
            entry[label+'_mean_mops'] = statistics.mean(float(r[n_col])/float(r[time_col])/1e6 for r in rows)
        result['throughput'].append(entry)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'reference_means.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    for section in ['core','stream_blocks']:
        print(section)
        for row in result[section]:
            if row['baseline'] in ['CS_mean_plus','CS_shrink','CMS_shrink','constant','CMM_mean']:
                print(row['metric'],row['baseline'],row['mean_relative_reduction_percent'])
    print('CMM-mean workload comparison:', json.dumps(result['cmm_workloads'], indent=2))
    print('Wrote', args.out / 'reference_means.json')


if __name__ == '__main__':
    main()
