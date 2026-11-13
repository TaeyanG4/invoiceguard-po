"""Offline budget projection. Does NOT access RunPod or stop any resource."""
from __future__ import annotations
import argparse
import json
from decimal import Decimal, InvalidOperation


def nonnegative(value: str, name: str) -> Decimal:
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name}: expected decimal") from exc
    if not d.is_finite() or d < 0:
        raise ValueError(f"{name}: must be finite and nonnegative")
    return d


def project(*, gpu_rate: str, remaining_gpu_hours: str,
            future_other_usd: str = "1", gpu_spent_usd: str = "0",
            other_spent_usd: str = "0", margin: str = "1.3",
            gpu_cap: str = "7", total_cap: str = "8") -> dict:
    values = locals().copy()
    v = {k: nonnegative(value, k) for k, value in values.items()}
    if v['gpu_rate'] <= 0:
        raise ValueError('gpu_rate must be positive; enter an observed console quote')
    if v['margin'] < 1:
        raise ValueError('margin must be >= 1')
    if v['gpu_cap'] > v['total_cap']:
        raise ValueError('gpu_cap cannot exceed total_cap')
    projected_gpu = (v['gpu_spent_usd'] + v['gpu_rate'] *
                     v['remaining_gpu_hours'] * v['margin'])
    projected_total = projected_gpu + v['other_spent_usd'] + v['future_other_usd']
    allowed_by_math = projected_gpu <= v['gpu_cap'] and projected_total <= v['total_cap']
    return {
        'mode': 'offline_projection_not_authorization_or_shutdown_control',
        'gpu_total_projected_usd': str(projected_gpu),
        'project_total_projected_usd': str(projected_total),
        'within_planned_caps': allowed_by_math,
        'remaining_total_headroom_usd': str(v['total_cap'] - projected_total),
        'note': 'No account, price, availability, billing or resource state was queried. '
                'Deployment requires explicit user approval of an actual console quote. '
                'Stopping a Python process does not stop a billed Pod.',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in [('gpu-rate', None), ('remaining-gpu-hours', None),
                          ('future-other-usd', '1'), ('gpu-spent-usd', '0'),
                          ('other-spent-usd', '0'), ('margin', '1.3'),
                          ('gpu-cap', '7'), ('total-cap', '8')]:
        parser.add_argument('--' + name, required=default is None, default=default)
    args = parser.parse_args()
    try:
        result = project(**vars(args))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['within_planned_caps'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
