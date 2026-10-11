#!/usr/bin/env python3
"""Measure tenant Pod source IPs on an external LAN receiver, then remove test Pods."""
import argparse
import http.server
import json
import secrets
import subprocess
import threading
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kubeconfig', required=True)
parser.add_argument('--listen', required=True, help='Reachable LAN IP of this operator host')
parser.add_argument('--port', type=int, default=18765)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--namespace-map', type=Path, help='Optional JSON mapping tenant to an existing test namespace')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
gateways = json.loads((root / 'config/egress-gateways.json').read_text())
tenants = {p.stem: json.loads(p.read_text()) for p in (root / 'tenants').glob('*.json')}
namespace_map = json.loads(args.namespace_map.read_text()) if args.namespace_map else {}
run_id = secrets.token_hex(6)
endpoint = '/afi-egress-' + run_id
kube = ['kubectl', '--kubeconfig=' + args.kubeconfig, '--request-timeout=20s']


def kubectl(command, obj=None):
    process = subprocess.run(kube + command, input=json.dumps(obj) if obj else None,
                             text=True, capture_output=True, timeout=30)
    if process.returncode:
        raise RuntimeError('Kubernetes test operation failed: ' + ' '.join(command[:3]))
    return process.stdout


class Receiver(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != endpoint:
            self.send_error(404)
            return
        payload = (self.client_address[0] + '\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


server = http.server.ThreadingHTTPServer((args.listen, args.port), Receiver)
threading.Thread(target=server.serve_forever, daemon=True).start()
created, results = [], []
try:
    for tenant, declaration in sorted(tenants.items()):
        namespace = namespace_map.get(tenant, tenant + '-' + declaration['environments'][0])
        for worker, expected in sorted(declaration['egress_ips'].items()):
            name = 'afi-egress-' + worker + '-' + run_id
            pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {
                'name': name, 'namespace': namespace, 'labels': {'app': 'afi-egress-probe'}},
                'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                    'nodeSelector': {'kubernetes.io/hostname': gateways[worker]['node']},
                    'containers': [{'name': 'probe', 'image': 'docker.io/library/busybox:1.36',
                        'command': ['sh', '-c', '''sleep 15
for n in $(seq 1 30); do
  source=$(wget -T 3 -qO- "$URL") || source=unreachable
  echo "$source"
  [ "$source" = "$EXPECTED" ] && exit 0
  sleep 3
done
exit 1
'''], 'env': [{'name': 'URL', 'value': f'http://{args.listen}:{args.port}{endpoint}'},
                              {'name': 'EXPECTED', 'value': expected}],
                        'securityContext': {'allowPrivilegeEscalation': False,
                            'capabilities': {'drop': ['ALL']}, 'runAsUser': 1000,
                            'runAsNonRoot': True, 'readOnlyRootFilesystem': True},
                        'resources': {'requests': {'cpu': '10m', 'memory': '8Mi'},
                                      'limits': {'cpu': '100m', 'memory': '32Mi'}}}]}}
            kubectl(['create', '-f', '-'], pod)
            created.append((namespace, name, tenant, worker, expected))
    pending = list(created)
    deadline = time.monotonic() + 240
    while pending and time.monotonic() < deadline:
        for namespace, name, tenant, worker, expected in list(pending):
            pod = json.loads(kubectl(['get', 'pod', name, '-n', namespace, '-o', 'json']))
            statuses = pod.get('status', {}).get('containerStatuses', [])
            end = statuses[0].get('state', {}).get('terminated') if statuses else None
            if not end:
                continue
            observed = kubectl(['logs', name, '-n', namespace]).splitlines()
            assert end['exitCode'] == 0 and observed[-1] == expected, (
                tenant, worker, expected, observed)
            result = {'tenant': tenant, 'worker': worker, 'node': pod['spec']['nodeName'],
                      'expected': expected, 'observed': observed[-1], 'passed': True}
            results.append(result)
            print(json.dumps(result), flush=True)
            pending.remove((namespace, name, tenant, worker, expected))
        if pending:
            time.sleep(3)
    assert not pending, 'Egress test timed out'
finally:
    for namespace, name, *_ in created:
        kubectl(['delete', 'pod', name, '-n', namespace, '--ignore-not-found', '--wait=false'])
    server.shutdown()
    server.server_close()
args.output.write_text(json.dumps({'results': results, 'probePodsRemoved': True,
                                   'receiverStopped': True}, indent=2) + '\n')
