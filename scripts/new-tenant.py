#!/usr/bin/env python3
"""Create a tenant declaration; does not contact or mutate any platform API."""
import argparse
import fcntl
import ipaddress
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
    # Serialize allocations; persisted declarations keep existing tenant IPs stable.
    with (root / 'tenants' / '.allocation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        used = [ip for declaration in (root / 'tenants').glob('*.json')
                for ip in json.loads(declaration.read_text())['egress_ips'].values()]
        if len(used) != len(set(used)):
            p.error('Existing declarations contain duplicate Egress IP reservations')
        pool = [str(ipaddress.IPv4Address('192.168.1.200') + i) for i in range(21)]
        if any(ip not in pool for ip in used):
            p.error('Existing Egress IP reservation is outside 192.168.1.200–220')
        free = [ip for ip in pool if ip not in used]
        if len(free) < 2:
            p.error('Egress pool exhausted: two free IPs are required per tenant')
        with target.open('x') as f:
            json.dump({'display_name': a.name, 'environments': a.environments,
                       'project_role': a.role, 'harbor_enabled': not a.without_harbor,
                       'harbor_storage_gib': a.harbor_storage_gib,
                       'egress_ips': {'worker1': free[0], 'worker2': free[1]}}, f, indent=2)
            f.write('\n')
except FileExistsError:
    p.error(f'{target.name} already exists; refusing to overwrite it')
print(f'Created {target.relative_to(root)}. Review terraform plan before apply.')
