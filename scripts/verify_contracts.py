"""Audit inherited technical planning contracts and artificial fixtures, NOT an ML/application run."""
from __future__ import annotations
import ast
import copy
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator
from budget_plan import project

ROOT = Path(__file__).resolve().parents[1]
checks: list[dict] = []

def check(name: str, value: bool, detail: str = '') -> None:
    checks.append({'check': name, 'status': 'pass' if value else 'failed', 'detail': detail})

def js(p: str):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))

cfg = yaml.safe_load((ROOT/'configs/project.yaml').read_text(encoding="utf-8"))
check('package_version4', cfg['project']['document_version'] == '4.0')
check('actual_quote_unknown', cfg['hardware']['actual_console_gpu_rate_usd_per_hour'] is None)
check('single_paid_pod', cfg['hardware']['max_simultaneous_paid_pods'] == 1)
check('full_ssh_gate', cfg['hardware']['full_ssh_required'] is True)
check('seven_one_two_budget', cfg['hardware']['gpu_compute_budget_usd'] + cfg['hardware']['storage_and_shutdown_budget_usd'] + cfg['hardware']['reserve_usd'] == 10)
check('gpu_training_unrun', cfg['audit']['gpu_status'] == 'not_run')
check('public_not_raw_gt', cfg['data']['english_invoice_ocr']['source_transcription_labels_available'] is False)
check('default_train_steps_match', cfg['training']['max_optimizer_steps'] == cfg['profiles']['standard']['max_optimizer_steps'])
for name in ['standard','mini']:
    p = cfg['profiles'][name]
    check(f'{name}_profile_positive_int', all(isinstance(x,int) and x>0 for x in p.values()))
    check(f'{name}_dev_stress_within_dev', p['public_dev_stress_bases']<=p['public_dev'])
for key in cfg['profiles']['standard']:
    check('mini_not_larger:'+key, cfg['profiles']['mini'][key]<=cfg['profiles']['standard'][key])
check('synthetic_profile_consistent', all(cfg['data']['synthetic']['counts'][a] == cfg['profiles']['standard'][b] for a,b in [('train','trade_train'),('validation','trade_dev'),('test','trade_test')]))

schema=js('schemas/public_extraction.schema.json'); val=Draft202012Validator(schema)
example=js('examples/public_canonical.json')
check('canonical_valid_fixture', val.is_valid(example))
bad=copy.deepcopy(example);bad['items'][0]['unit_price']=2.5
check('canonical_reject_json_number', not val.is_valid(bad))
bad=copy.deepcopy(example);bad['items'][0]['unit_price']='1,200.00'
check('canonical_reject_grouping', not val.is_valid(bad))
bad=copy.deepcopy(example);bad['items'][0]['sku_raw']='000125'
check('canonical_reject_unlabelled_sku', not val.is_valid(bad))
bad=copy.deepcopy(example);bad['items'][0]['unit_price']=None
check('canonical_null_abstention_allowed', val.is_valid(bad))
check('numeric_format_equivalence_fixture', Decimal('2.5')==Decimal('2.50'))
check('numeric_reading_error_fixture', Decimal('2.5')!=Decimal('25.00'))
check('sku_leading_zero_fixture', '000125'!='125')

codes=set(js('schemas/findings.schema.json')['properties']['findings']['items']['properties']['code']['enum'])
for code in ['QTY_DIFF','AMBIGUOUS_QUANTITY','PO_LINE_NOT_FOUND','UNKNOWN_SKU','DUPLICATE_SKU']:
    check('authoritative_reason_enum:'+code, code in codes)
expected=js('examples/expected_findings.json')
check('expected_fixture_enums', all(f['code'] in codes for f in expected['findings']))
for case in js('examples/test_cases.json')['cases']:
    for field in ['expect','not_expect']:
        if isinstance(case.get(field),list):
            check(f'fixture_enum:{case["id"]}:{field}', set(case[field])<=codes)

r=project(gpu_rate='.89',remaining_gpu_hours='6')
check('budget_arithmetic_example_within', r['within_planned_caps'] and Decimal(r['project_total_projected_usd'])==Decimal('7.942'))
r=project(gpu_rate='.89',remaining_gpu_hours='18')
check('budget_reject_18h_high_price', not r['within_planned_caps'])
for field,value in [('gpu_rate','NaN'),('remaining_gpu_hours','-1'),('margin','.9'),('gpu_rate','0')]:
    args={'gpu_rate':'.34','remaining_gpu_hours':'6',field:value}
    try:
        project(**args)
        rejected=False
    except ValueError:
        rejected=True
    check(f'budget_bad_input:{field}:{value}', rejected)
check('budget_script_no_api', 'import requests' not in (ROOT/'scripts/budget_plan.py').read_text(encoding="utf-8"))
for script in (ROOT/'scripts').glob('*.py'):
    try: ast.parse(script.read_text(encoding="utf-8")); valid=True
    except SyntaxError: valid=False
    check('python_syntax:'+script.name,valid)

plan=(ROOT/'docs/08_48H_EXECUTION.md').read_text(encoding="utf-8")
check('final_matrix_both_models', 'for model in base adapter' in plan)
check('final_matrix_all_splits', 'public_iid_final public_ood_final trade_final' in plan)
check('runtime_evidence_not_faked', all(v is None for v in js('reports/RESULTS_TEMPLATE.json')['metrics'].values()))
for rel in ['docs/14_FINAL_AUDIT.md','docs/15_LABEL_AND_METRIC_CONTRACT.md','docs/16_RUNTIME_RELEASE_GATES.md']:
    check('new_required_doc:'+rel,(ROOT/rel).exists())
check('no_font_files',not any(p.suffix.lower() in {'.ttf','.otf','.woff','.woff2'} for p in ROOT.rglob('*') if p.is_file()))

report={'scope':'inherited_technical_contracts_and_artificial_fixtures_only',
 'checked_at_utc':datetime.now(timezone.utc).isoformat(),
 'status':'pass' if all(c['status']=='pass' for c in checks) else 'failed',
 'checks':checks,
 'not_performed':['full_data_download','image_label_audit','RunPod_quote_or_account_access','VLM_inference','QLoRA','live_GPU_API','application_concurrency_tests']}
(ROOT/'reports/CONTRACT_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f"{report['status']}: {len(checks)} technical contract/fixture checks")
for c in checks:
    if c['status']!='pass': print(c)
raise SystemExit(0 if report['status']=='pass' else 1)
