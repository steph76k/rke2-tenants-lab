#!/usr/bin/env python3
"""Terraform address lifecycle; --check is read-only. Requires SSH and sudo Python3.

NetworkManager changes are serialized per gateway. Only addresses owned by this
administrative state may be removed; primary addresses and routes are preserved.
"""
import argparse
import json
import os
import shlex
import subprocess

REMOTE = r'''
import fcntl, ipaddress, json, os, pathlib, socket, subprocess, sys
b, mode = json.loads(sys.argv[1]), sys.argv[2]
ip = str(ipaddress.IPv4Address(b['ip']))
assert ipaddress.IPv4Address('192.168.1.200') <= ipaddress.IPv4Address(ip) <= ipaddress.IPv4Address('192.168.1.220')
assert socket.gethostname().split('.')[0] == b['node'].split('.')[0], 'Wrong gateway host'
def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()
def live():
    return {x['local'] + '/' + str(x['prefixlen']) for dev in json.loads(run('ip','-j','-4','addr','show','dev',b['interface'])) for x in dev['addr_info']}
def persistent():
    return {x.strip() for x in run('nmcli','-g','ipv4.addresses','connection','show',b['connection']).split(',')}
assert b['primary'] in live(), 'Expected primary IP missing'
assert run('nmcli','-g','GENERAL.CONNECTION','device','show',b['interface']) == b['connection'], 'Unexpected connection profile'
directory = pathlib.Path('/var/lib/afi-tenant-egress')
marker = directory / (ip + '.json')
owned = {'ip': ip, 'owner': b['owner'], 'node': b['node']}
cidr = ip + '/32'
if mode == '--check':
    ok = marker.exists() and json.loads(marker.read_text()) == owned and cidr in live() and cidr in persistent()
    print(json.dumps({'node':b['node'], 'ip':ip, 'consistent':ok}))
    sys.exit(0 if ok else 1)
directory.mkdir(mode=0o700, exist_ok=True)
with (directory / '.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    current, stored = live(), persistent()
    if marker.exists():
        assert json.loads(marker.read_text()) == owned, 'Address ownership mismatch'
    elif mode == '--remove':
        if not any(x.split('/')[0] == ip for x in current | stored):
            print(json.dumps({'node':b['node'], 'ip':ip, 'action':mode, 'alreadyAbsent':True}))
            sys.exit(0)
        raise RuntimeError('Refusing to remove address without ownership record')
    else:
        assert not any(x.split('/')[0] == ip for x in current | stored), 'Address already configured outside Terraform ownership'
        run('arping','-D','-I',b['interface'],'-c','3',ip)
        marker.write_text(json.dumps(owned) + '\n')
        marker.chmod(0o600)
    if mode == '--apply':
        if cidr not in current:
            run('arping','-D','-I',b['interface'],'-c','3',ip)
        if cidr not in stored:
            run('nmcli','connection','modify',b['connection'],'+ipv4.addresses',cidr)
        if cidr not in current:
            run('nmcli','device','reapply',b['interface'])
        assert cidr in live() and cidr in persistent(), 'Address not active and persistent'
    else:
        if cidr in stored:
            run('nmcli','connection','modify',b['connection'],'-ipv4.addresses',cidr)
        if cidr in current:
            run('nmcli','device','reapply',b['interface'])
        assert cidr not in live() and cidr not in persistent(), 'Address removal incomplete'
        marker.unlink()
    assert b['primary'] in live(), 'Primary IP changed unexpectedly'
    print(json.dumps({'node':b['node'], 'ip':ip, 'action':mode, 'success':True}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['--apply', '--remove', '--check'])
    # Modes are passed as options by Terraform, rather than arbitrary shell text.
    import sys
    args = parser.parse_args(['--', *sys.argv[1:]])
    binding = json.loads(os.environ['AFI_EGRESS_BINDING'])
    remote = shlex.join(['sudo', '-n', 'python3', '-c', REMOTE,
                         json.dumps(binding), args.mode])
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                             '-o', 'ConnectTimeout=10', '--',
                             binding['user'] + '@' + binding['host'], remote],
                            text=True, capture_output=True, timeout=90)
    if result.returncode:
        # Host script operates exclusively on public network configuration.
        print(result.stderr, file=sys.stderr)
    print(result.stdout, end='')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
