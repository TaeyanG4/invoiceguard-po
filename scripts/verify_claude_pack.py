"""Static Claude Code migration checks. Not CLI, permission, cloud or app tests."""
from __future__ import annotations
import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
checks: list[dict] = []
# Git-ignored local folders (virtualenvs, raw data, weights) are never in the repository or release, as in verify_pack.py.
LOCAL_DIRS = {'.git', '.venv', '.venv-ml', 'data', 'artifacts', 'models', 'node_modules'}
# Logs that name the external reviewer's CLI as history, not as an instruction to use another agent.
HISTORY_LOGS = {'handoff.md'}


def repo_files():
    for p in ROOT.rglob('*'):
        if p.is_file() and p.relative_to(ROOT).parts[0] not in LOCAL_DIRS:
            yield p

def record(name: str, valid: bool, detail: str = '') -> None:
    checks.append({'check': name, 'status': 'pass' if valid else 'failed', 'detail': detail})

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')

required = [
    'CLAUDE.md', '.claude/settings.json', '.claude/README.md', 'README.md',
    'prompts/CLAUDE_START.md', 'prompts/CLAUDE_RESUME.md',
    'prompts/CLAUDE_RUNPOD_APPROVAL_CHECK.md', 'prompts/CLAUDE_MODEL_AND_RELEASE.md',
    'docs/17_CLAUDE_CODE_WORKFLOW.md', 'docs/18_PACKAGE_MIGRATION.md',
    'reports/SESSION_HANDOFF.md', 'reports/TASK_BOARD.md', 'reports/RUNPOD_APPROVAL.md',
    'scripts/verify_checksums.py', 'requirements-pack.txt',
]
for relative in required:
    record('required:' + relative, (ROOT / relative).is_file())
for p in repo_files():
    if p.suffix.lower() in {'.md', '.json', '.yaml', '.txt', '.py'}:
        try:
            p.read_text(encoding='utf-8')
            valid = True
        except UnicodeError:
            valid = False
        record('utf8:' + p.relative_to(ROOT).as_posix(), valid)

cfg = yaml.safe_load(read('configs/project.yaml'))
record('v4_package', cfg['project']['document_version'] == '4.0')
record('claude_entrypoint', cfg['agent']['tool'] == 'claude_code' and cfg['agent']['entrypoint'] == 'CLAUDE.md')
record('retained_technical_baseline', cfg['project']['technical_baseline'] == 'v3_audited_contracts_unchanged')
record('no_rival_root_instruction', not (ROOT / ('AG' + 'ENTS.md')).exists())
record('compact_root_instruction', len(read('CLAUDE.md').splitlines()) < 200)
record('remote_credential_boundary', cfg['agent']['agent_login_location'] == 'local_workstation_not_runpod')
settings = json.loads(read('.claude/settings.json'))
permissions = settings['permissions']
record('manual_permission_mode', permissions['defaultMode'] == 'default')
record('no_wide_allowlist', not permissions.get('allow'))
record('no_automatic_hooks', not settings.get('hooks'))
record('no_forced_agent_model', 'model' not in settings)
record('no_provider_or_key_config', 'env' not in settings and 'mcpServers' not in settings)
record('secret_read_rules', all(x in permissions['deny'] for x in ['Read(./.env)', 'Read(./secrets/**)']))
# 2026-11-14 user decision: no permission prompts at all ("실행권한 전부 허용할테니 제발 나한테 묻지마");
# remote safety comes from the written RunPod approval + budget, not from per-command ask rules.
record('no_prompting_ask_rules', not permissions.get('ask'))
record('local_settings_gitignored', '.claude/settings.local.json' in read('.gitignore'))
record('secrets_gitignored', 'secrets/' in read('.gitignore'))
_approval = read('reports/RUNPOD_APPROVAL.md')
record('approval_explicit', 'approved: false' in _approval
       or ('approved: true' in _approval and 'user_approved_at: 2026' in _approval and '사용자 채팅' in _approval))
record('runtime_unrun', cfg['audit']['gpu_status'] == 'not_run')
record('result_metrics_unrun', all(v is None for v in json.loads(read('reports/RESULTS_TEMPLATE.json'))['metrics'].values()))
for task in range(10):
    record('task_board:' + f'T{task:02d}', f'T{task:02d}' in read('reports/TASK_BOARD.md'))
for key in ['start_prompt','resume_prompt','workflow','handoff_file','task_board']:
    record('config_path:'+key, (ROOT / cfg['agent'][key]).is_file())
# Limit to active content; historical audit labels v2/v3 are intentional.
legacy_tokens = ['CODE' + 'X', 'Co' + 'dex', 'AG' + 'ENTS.md', 'verify_' + 'v3.py']
for p in repo_files():
    if p.suffix in {'.md','.yaml'} and p.relative_to(ROOT).as_posix() not in HISTORY_LOGS:
        text = p.read_text(encoding='utf-8')
        bad = [token for token in legacy_tokens if token in text]
        record('active_refs:' + p.relative_to(ROOT).as_posix(), not bad, ','.join(bad))
for p in (ROOT / 'scripts').glob('*.py'):
    try:
        ast.parse(p.read_text(encoding='utf-8'))
        valid = True
    except SyntaxError:
        valid = False
    record('python_syntax:' + p.name, valid)
for suffix in ['.pem','.key','.ttf','.otf','.woff','.woff2','.safetensors','.pt']:
    record('no_asset:' + suffix, not any(p.suffix.lower() == suffix for p in repo_files()))

report = {
    'scope': 'static_claude_code_package_migration_only',
    'checked_at_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'pass' if all(c['status']=='pass' for c in checks) else 'failed',
    'checks': checks,
    'not_performed': ['Claude_Code_CLI','permission_runtime_enforcement','RunPod_login_or_billing',
                      'full_dataset_download','VLM_inference','QLoRA_training','application_tests'],
}
(ROOT / 'reports/CLAUDE_PACK_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f"{report['status']}: {len(checks)} static Claude Code package checks")
for c in checks:
    if c['status'] != 'pass': print(c)
raise SystemExit(0 if report['status']=='pass' else 1)
