#!/usr/bin/env python3
"""Lab E2E: temporary OIDC users must only access their own Rancher project and pods."""
import argparse
import base64
import hashlib
import json
import secrets
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import requests

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent / 'rke2-platform-lab/scripts/afi-isolation'))
from afi_platform import keycloak, CONFIG

rancher = 'https://rancher.berger.ph'
cluster = 'c-44q9v'
admin = keycloak()
base = CONFIG['keycloak'] + '/admin/realms/' + CONFIG['realm']
results = []


def kubectl(args):
    r = subprocess.run(['kubectl', '--context=rancher', '--request-timeout=30s', *args],
                       text=True, capture_output=True, timeout=40)
    if r.returncode:
        raise RuntimeError('Rancher management operation failed')
    return r.stdout


class Form(HTMLParser):
    action = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form' and attrs.get('id') == 'kc-form-login':
            self.action = attrs['action']


projects = json.loads(kubectl(['get', 'projects.management.cattle.io', '-n', cluster, '-o', 'json']))
ids = {}
for tenant in ['mandant-a', 'mandant-b']:
    expected = json.loads((root / 'tenants' / (tenant + '.json')).read_text())['display_name']
    matching = [x for x in projects['items'] if x['spec']['displayName'] == expected]
    assert len(matching) == 1
    ids[tenant] = cluster + ':' + matching[0]['metadata']['name']

for tenant, group in [('mandant-a', 'mandant-a-developers'),
                      ('mandant-b', 'mandant-b-developers'), ('mandant-a', 'mandant-a')]:
    uid = rid = None
    name = 'afi-rancher-probe-' + secrets.token_hex(8)
    password = secrets.token_urlsafe(32)
    try:
        r = admin.post(base + '/users', json={'username': name, 'enabled': True,
            'email': name + '@example.invalid', 'emailVerified': True,
            'firstName': 'AFI', 'lastName': 'Validation',
            'credentials': [{'type': 'password', 'value': password, 'temporary': False}]}, timeout=30)
        r.raise_for_status()
        uid = r.headers['Location'].rsplit('/', 1)[1]
        r = admin.get(base + '/groups', params={'search': group, 'exact': 'true'}, timeout=30)
        r.raise_for_status()
        groups = [x for x in r.json() if x['name'] == group]
        assert len(groups) == 1
        admin.put(base + '/users/' + uid + '/groups/' + groups[0]['id'], timeout=30).raise_for_status()
        browser = requests.Session()
        r = browser.get(rancher + '/v3-public/keyCloakOIDCProviders/keycloakoidc', timeout=20)
        r.raise_for_status()
        redirect = r.json()['redirectUrl']
        assert redirect == rancher + '/v1-oidc/keycloakoidc'
        state = secrets.token_urlsafe(20)
        r = browser.get(redirect, params={'state': state, 'scope': 'openid profile email'},
                        allow_redirects=False, timeout=20)
        assert r.status_code == 302
        location = r.headers['Location']
        assert urlparse(location).netloc == urlparse(CONFIG['keycloak']).netloc
        q = parse_qs(urlparse(location).query)
        assert q['code_challenge_method'] == ['S256']
        verifier = next(c.value for c in browser.cookies if c.name == 'R_PKCE_VERIFIER')
        assert q['code_challenge'] == [base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')]
        r = browser.get(location, timeout=20)
        r.raise_for_status()
        form = Form()
        form.feed(r.text)
        assert form.action and urlparse(form.action).netloc == urlparse(CONFIG['keycloak']).netloc
        r = browser.post(form.action, data={'username': name, 'password': password},
                         allow_redirects=False, timeout=20)
        assert r.status_code == 302
        q = parse_qs(urlparse(r.headers['Location']).query)
        assert q['state'] == [state]
        r = browser.post(rancher + '/v3-public/keyCloakOIDCProviders/keycloakoidc?action=login',
                         json={'code': q['code'][0], 'responseType': 'json', 'ttl': 600000}, timeout=30)
        r.raise_for_status()
        rid = r.json().get('userId')
        browser.headers['Authorization'] = 'Bearer ' + r.json()['token']
        r = browser.get(rancher + '/v3/users?me=true', timeout=20)
        r.raise_for_status()
        user = r.json()['data'][0]
        rid = user['id']
        assert 'keycloakoidc_user://' + uid in user['principalIds']
        for attempt in range(12):
            allowed = browser.get(rancher + '/v3/projects/' + ids[tenant], timeout=20)
            if allowed.status_code == 200:
                break
            time.sleep(5)
        other = 'mandant-b' if tenant == 'mandant-a' else 'mandant-a'
        denied = browser.get(rancher + '/v3/projects/' + ids[other], timeout=20)
        assert allowed.status_code == 200 and denied.status_code in [403, 404]
        checks = []
        for environment in ['dev', 'test', 'prod']:
            for target in [tenant, other]:
                r = browser.get(rancher + '/k8s/clusters/' + cluster + '/api/v1/namespaces/' +
                                target + '-' + environment + '/pods', timeout=30)
                assert r.status_code == (200 if target == tenant else 403)
                checks.append({'namespace': target + '-' + environment, 'http': r.status_code})
        result = {'group': group, 'projectAllowedHttp': allowed.status_code,
                  'foreignProjectHttp': denied.status_code, 'kubernetes': checks,
                  'pkce': 'S256', 'passed': True}
        results.append(result)
        print(json.dumps(result), flush=True)
    finally:
        if uid:
            admin.delete(base + '/users/' + uid, timeout=30).raise_for_status()
        if rid:
            kubectl(['delete', 'users.management.cattle.io', rid, '--ignore-not-found'])
a.output.write_text(json.dumps({'results': results, 'temporaryIdentitiesRemoved': True}, indent=2) + '\n')
