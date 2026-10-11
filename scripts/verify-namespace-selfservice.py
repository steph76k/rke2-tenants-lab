#!/usr/bin/env python3
"""End-to-end namespace self-service check using exact tenant RBAC groups.

Creates four uniquely named namespaces via Kubernetes user/group impersonation,
checks admission and ESO, and runs network/egress/Rancher OIDC/log-routing tests.
Requires platform admin access, adjacent platform repo, kubectl, and Python deps.
Only synthetic KV keys, namespaces and log records created by this run are removed.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--kubeconfig', required=True)
p.add_argument('--listen', required=True)
p.add_argument('--output-dir', type=Path, required=True)
a = p.parse_args()
os.umask(0o077)
root = Path(__file__).resolve().parents[1]
platform = root.parent / 'rke2-platform-lab'
sys.path.insert(0, str(platform / 'scripts/afi-isolation'))
from afi_platform import BAO, CONFIG, command, keycloak

k = ['kubectl', '--kubeconfig=' + a.kubeconfig, '--request-timeout=30s']
a.output_dir.mkdir(parents=True, exist_ok=True)
run_id = secrets.token_hex(5)
projects = {}
created, kv_created, users, checks = [], [], [], []
values = {}
idp_base = CONFIG['keycloak'] + '/admin/realms/' + CONFIG['realm']


def kubectl(args, obj=None, tenant=None, role='developers', check=True):
    identity = [] if not tenant else ['--as=afi-selfservice-' + run_id,
        '--as-group=system:authenticated', '--as-group=keycloakoidc_group://' + tenant + '-' + role]
    r = subprocess.run(k + identity + args, input=json.dumps(obj) if obj else None,
                       capture_output=True, text=True, timeout=120)
    if check and r.returncode:
        raise RuntimeError('Kubernetes verification failed: ' + ' '.join(args[:3]) + '; ' + r.stderr[-600:])
    return r


def get(args):
    return json.loads(kubectl(['get', *args, '-o', 'json']).stdout)


def wait_for(fn, seconds=120):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if fn():
            return
        time.sleep(2)
    raise RuntimeError('Timed out waiting for self-service reconciliation')


def checked_denial(label, args, obj=None, tenant='mandant-a', role='developers'):
    r = kubectl(args, obj, tenant, role, check=False)
    assert r.returncode != 0 and ('denied' in r.stderr or 'forbidden' in r.stderr or 'invalid' in r.stderr), label
    checks.append({'test': label, 'passed': True})


def namespace(name, project):
    return {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {
        'name': name, 'annotations': {'field.cattle.io/projectId': project}}}


def external_secret(ns, name, store):
    return {'apiVersion': 'external-secrets.io/v1', 'kind': 'ExternalSecret',
        'metadata': {'name': name, 'namespace': ns}, 'spec': {
            'refreshInterval': '15s', 'secretStoreRef': {'kind': 'ClusterSecretStore', 'name': store},
            'target': {'name': name}, 'data': [{'secretKey': 'value', 'remoteRef': {
                'key': 'afi-selfservice/' + run_id, 'property': 'value'}}]}}


for tenant in ['mandant-a', 'mandant-b']:
    projects[tenant] = get(['namespace', tenant + '-dev'])['metadata']['annotations']['field.cattle.io/projectId']
    values[tenant] = secrets.token_urlsafe(24)

try:
    for tenant in projects:
        command([BAO, 'kv', 'put', '-namespace=' + tenant, '-cas=0',
                 'secret/afi-selfservice/' + run_id, '-'], json.dumps({'value': values[tenant]}))
        kv_created.append(tenant)
        other = next(t for t in projects if t != tenant)
        for role in ['developers', 'admins']:
            ns = tenant + '-selfservice-' + role + '-' + run_id
            kubectl(['create', '-f', '-'], namespace(ns, projects[tenant]), tenant, role)
            created.append((tenant, role, ns))
            wait_for(lambda: get(['ns', ns])['metadata'].get('labels', {}).get(
                'field.cattle.io/projectId') == projects[tenant].split(':')[1])
            wait_for(lambda: bool(get(['networkpolicy', '-n', ns])['items']))
            checks.append({'test': 'namespace-create', 'group': tenant + '-' + role, 'namespace': ns, 'passed': True})
            for label, obj in [
                ('wrong-prefix', namespace('wrong-' + run_id, projects[tenant])),
                ('foreign-project', namespace(other + '-attempt-' + run_id, projects[other])),
                ('missing-project', {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': tenant + '-attempt-' + run_id}})
            ]:
                checked_denial(label + '-' + tenant + '-' + role, ['create', '-f', '-', '--dry-run=server'], obj, tenant, role)
            for label, patch in [
                ('spoof-project-label', {'metadata': {'labels': {'field.cattle.io/projectId': projects[other].split(':')[1]}}}),
                ('remove-project-label', {'metadata': {'labels': {'field.cattle.io/projectId': None}}}),
                ('move-project', {'metadata': {'annotations': {'field.cattle.io/projectId': projects[other]}}})
            ]:
                checked_denial(label + '-' + tenant + '-' + role, ['patch', 'ns', ns, '--type=merge', '-p', json.dumps(patch), '--dry-run=server'], tenant=tenant, role=role)
            spoof = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'spoof', 'namespace': ns,
                'labels': {'io.cilium.k8s.namespace.labels.field.cattle.io/projectId': projects[other].split(':')[1]}},
                'spec': {'containers': [{'name': 'probe', 'image': 'busybox:1.36'}]}}
            checked_denial('spoof-cilium-identity-' + tenant + '-' + role, ['create', '-f', '-', '--dry-run=server'], spoof, tenant, role)
            # Wait for Rancher's namespaced RBAC reconciliation before testing ESO as the tenant.
            wait_for(lambda: kubectl(['auth', 'can-i', 'create', 'externalsecrets.external-secrets.io', '-n', ns], tenant=tenant, role=role, check=False).returncode == 0)
            kubectl(['create', '-f', '-'], external_secret(ns, 'own-secret', 'openbao-' + tenant), tenant, role)
            wait_for(lambda: any(x['type'] == 'Ready' and x['status'] == 'True' for x in get(['externalsecret', 'own-secret', '-n', ns]).get('status', {}).get('conditions', [])))
            value = get(['secret', 'own-secret', '-n', ns])['data']['value']
            assert base64.b64decode(value).decode() == values[tenant]
            kubectl(['create', '-f', '-'], external_secret(ns, 'foreign-secret', 'openbao-' + other), tenant, role)
            wait_for(lambda: any(x['type'] == 'Ready' and x['status'] == 'False' for x in get(['externalsecret', 'foreign-secret', '-n', ns]).get('status', {}).get('conditions', [])))
            assert kubectl(['get', 'secret', 'foreign-secret', '-n', ns], check=False).returncode != 0
            checks.append({'test': 'eso-own-allowed-foreign-denied', 'group': tenant + '-' + role, 'passed': True})
            print(tenant + ' ' + role + ': namespace, admission and ESO passed', flush=True)

    with tempfile.TemporaryDirectory(prefix='afi-selfservice-tests-') as directory:
        directory = Path(directory)
        direct = {t: ns for t, role, ns in created if role == 'developers'}
        pairs = {t: {('dev' if role == 'developers' else 'test'): ns for tt, role, ns in created if tt == t} for t in projects}
        (directory / 'direct.json').write_text(json.dumps(direct))
        (directory / 'pairs.json').write_text(json.dumps(pairs))
        def test(script, *args):
            result = subprocess.run([sys.executable, str(script), *map(str, args)], cwd=root)
            assert result.returncode == 0, 'Verification script failed: ' + script.name
        test(root / 'scripts/verify-egress.py', '--kubeconfig', a.kubeconfig, '--listen', a.listen,
             '--namespace-map', directory / 'direct.json', '--output', a.output_dir / 'egress.json')
        test(root / 'scripts/verify-project-isolation.py', '--kubeconfig', a.kubeconfig,
             '--namespace-map', directory / 'pairs.json', '--output', a.output_dir / 'network-isolation.json')
        test(root / 'scripts/verify-rancher-access.py', '--output', a.output_dir / 'rancher-oidc.json')
        identities = {}
        for tenant in projects:
            admin_idp = keycloak()
            username = 'afi-selfservice-' + tenant + '-' + run_id
            password = secrets.token_urlsafe(32)
            r = admin_idp.post(idp_base + '/users', json={'username': username, 'enabled': True,
                'email': username + '@example.invalid', 'emailVerified': True, 'firstName': 'AFI', 'lastName': 'Test',
                'credentials': [{'type': 'password', 'value': password, 'temporary': False}]}, timeout=30)
            r.raise_for_status()
            uid = r.headers['Location'].rsplit('/', 1)[1]
            users.append(uid)
            r = admin_idp.get(idp_base + '/groups', params={'search': tenant + '-logs-readers', 'exact': 'true'}, timeout=30)
            r.raise_for_status()
            group = next(x for x in r.json() if x['name'] == tenant + '-logs-readers')
            admin_idp.put(idp_base + '/users/' + uid + '/groups/' + group['id'], timeout=30).raise_for_status()
            identities[tenant] = {'username': username, 'password': password, 'tenant': tenant}
        (directory / 'identities.json').write_text(json.dumps(identities))
        test(platform / 'scripts/afi-isolation/verify-log-routing.py', '--cluster', '2', '--kubeconfig', a.kubeconfig,
             '--namespace-map', directory / 'direct.json', '--identities', directory / 'identities.json',
             '--output', a.output_dir / 'logging-oidc.json')
finally:
    cleanup_errors = []
    for uid in users:
        try:
            admin_idp = keycloak()
            admin_idp.delete(idp_base + '/users/' + uid, timeout=30).raise_for_status()
        except Exception:
            cleanup_errors.append('keycloak test user')
    for tenant, role, ns in created:
        try:
            kubectl(['delete', 'namespace', ns, '--ignore-not-found', '--wait=false'])
        except Exception:
            cleanup_errors.append(ns)
    for tenant in kv_created:
        try:
            command([BAO, 'kv', 'metadata', 'delete', '-namespace=' + tenant, 'secret/afi-selfservice/' + run_id])
        except Exception:
            cleanup_errors.append('synthetic KV ' + tenant)
    (a.output_dir / 'namespace-admission-eso.json').write_text(json.dumps({
        'runId': run_id, 'namespaceCreationMethod': 'Kubernetes impersonation of exact tenant groups',
        'checks': checks, 'cleanupErrors': cleanup_errors,
        'namespaceDeletionRequested': len(created), 'syntheticKVAndUsersRemoved': not cleanup_errors}, indent=2) + '\n')
    assert not cleanup_errors, cleanup_errors
print('Namespace self-service verification passed; temporary namespaces, keys and identities cleaned up.', flush=True)
