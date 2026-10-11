#!/usr/bin/env python3
"""Verify Rancher project ingress isolation across namespaces and both workers."""
import argparse
import concurrent.futures
import datetime
import json
import secrets
import subprocess
import time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--kubeconfig', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
k = ['kubectl', '--kubeconfig=' + a.kubeconfig, '--request-timeout=30s']
root = Path(__file__).resolve().parents[1]
gateways = json.loads((root / 'config/egress-gateways.json').read_text())
run_id = secrets.token_hex(5)
created, clients, servers, results = [], [], [], []


def kubectl(args, obj=None, check=True):
    r = subprocess.run(k + args, input=json.dumps(obj) if obj else None,
                       capture_output=True, text=True, timeout=45)
    if check and r.returncode:
        raise RuntimeError('Kubernetes operation failed: ' + ' '.join(args[:4]))
    return r


def probe(client, server):
    command = ['exec', client['name'], '-n', client['namespace'], '--',
               'wget', '-T', '3', '-qO-', 'http://' + server['ip'] + ':8080/']
    r = kubectl(command, check=False)
    # A denied flow must fail in wget, not in the Kubernetes exec transport.
    connected = r.returncode == 0 and r.stdout.strip() == run_id
    denied = r.returncode != 0 and 'wget:' in r.stderr and 'command terminated with exit code' in r.stderr
    expected = client['tenant'] == server['tenant']
    return {'source': client, 'destination': server,
            'expected': 'allowed' if expected else 'denied',
            'observed': 'allowed' if connected else ('denied' if denied else 'test-error'),
            'passed': connected if expected else denied}


try:
    for tenant in ['mandant-a', 'mandant-b']:
        for worker, gateway in sorted(gateways.items()):
            for role, environment in [('server', 'dev'), ('client', 'test')]:
                name = 'afi-isolation-' + worker + '-' + run_id
                ns = tenant + '-' + environment
                shell = ('mkdir -p /tmp/www; echo ' + run_id +
                         ' > /tmp/www/index.html; exec httpd -f -p 8080 -h /tmp/www'
                         if role == 'server' else 'sleep 600')
                obj = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {
                    'name': name, 'namespace': ns, 'labels': {'app': 'afi-isolation-probe'}},
                    'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                        'nodeSelector': {'kubernetes.io/hostname': gateway['node']},
                        'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000,
                                            'fsGroup': 1000},
                        'volumes': [{'name': 'tmp', 'emptyDir': {'sizeLimit': '1Mi'}}],
                        'containers': [{'name': 'probe', 'image': 'docker.io/library/busybox:1.36',
                            'command': ['sh', '-c', shell],
                            'volumeMounts': [{'name': 'tmp', 'mountPath': '/tmp'}],
                            'securityContext': {'allowPrivilegeEscalation': False,
                                'capabilities': {'drop': ['ALL']}, 'readOnlyRootFilesystem': True},
                            'resources': {'requests': {'cpu': '10m', 'memory': '8Mi'},
                                          'limits': {'cpu': '100m', 'memory': '32Mi'}}}]}}
                kubectl(['create', '-f', '-'], obj)
                item = {'tenant': tenant, 'namespace': ns, 'name': name, 'worker': worker}
                created.append(item)
                (servers if role == 'server' else clients).append(item)
    for item in created:
        kubectl(['wait', '--for=condition=Ready', 'pod/' + item['name'],
                 '-n', item['namespace'], '--timeout=30s'])
    for item in servers:
        pod = json.loads(kubectl(['get', 'pod', item['name'], '-n', item['namespace'], '-o', 'json']).stdout)
        item['ip'] = pod['status']['podIP']
    time.sleep(15)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(probe, client, server) for client in clients for server in servers]
        results = [future.result() for future in futures]
    for result in results:
        print(json.dumps(result), flush=True)
finally:
    for item in created:
        kubectl(['delete', 'pod', item['name'], '-n', item['namespace'], '--ignore-not-found', '--wait=false'])
    a.output.write_text(json.dumps({'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'results': results, 'probePodsRemoved': True}, indent=2) + '\n')
assert len(results) == 16 and all(r['passed'] for r in results), 'Project isolation verification failed'
