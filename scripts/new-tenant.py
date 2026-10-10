#!/usr/bin/env python3
"""Create a tenant declaration; does not contact or mutate any platform API."""
import argparse
import json
from pathlib import Path
import re

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('slug', help='e.g. mandant-b')
p.add_argument('--name', required=True, help='Rancher project display name')
p.add_argument('--environments', nargs='+', default=['dev', 'test', 'prod'])
p.add_argument('--role', choices=['project-member', 'read-only', 'project-owner'], default='project-member')
p.add_argument('--harbor-storage-gib', type=int, default=10)
p.add_argument('--without-harbor', action='store_true')
a = p.parse_args()
if not re.fullmatch(r'[a-z][a-z0-9-]{1,39}', a.slug):
    p.error('slug must have 2-40 lowercase letters, digits or hyphens, starting with a letter')
if len(set(a.environments)) != len(a.environments) or any(not re.fullmatch(r'[a-z][a-z0-9-]{0,14}', e) for e in a.environments):
    p.error('environment names must be unique and have 1-15 lowercase letters, digits or hyphens')
if a.harbor_storage_gib < 1:
    p.error('Harbor storage quota must be positive')
root = Path(__file__).resolve().parents[1]
target = root / 'tenants' / (a.slug + '.json')
try:
    with target.open('x') as f:
        json.dump({'display_name': a.name, 'environments': a.environments,
                   'project_role': a.role, 'harbor_enabled': not a.without_harbor,
                   'harbor_storage_gib': a.harbor_storage_gib}, f, indent=2)
        f.write('\n')
except FileExistsError:
    p.error(f'{target.name} already exists; refusing to overwrite it')
print(f'Created {target.relative_to(root)}. Review terraform plan before apply.')
