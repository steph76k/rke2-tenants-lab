#!/usr/bin/env python3
"""Lab operator runner: resolve existing credentials in memory and run the shared tenant administration state.
Requires kubectl, OpenBao CLI, Python requests, existing admin access, and the
TLS-verified OpenSearch tunnel described in docs/operations.md. Not a tenant CLI.
"""
import argparse,json,os,re,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['init','plan','apply','validate','fmt','output','state','show','providers','version','import']);p.add_argument('arguments',nargs=argparse.REMAINDER);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
os.umask(0o077);env=dict(os.environ,BAO_ADDR=os.environ.get('BAO_ADDR','https://openbao.berger.ph'),BAO_NAMESPACE='',VAULT_NAMESPACE='')
for k in list(env):
 if k.startswith('TF_LOG'):env.pop(k)
def read(args):
 r=subprocess.run(args,env=env,text=True,capture_output=True)
 if r.returncode:raise RuntimeError('Credential lookup failed; output suppressed: '+args[0])
 return json.loads(r.stdout)
def kv(path):return read([env.get('BAO_BIN','/home/tanzu/.local/bin/bao'),'kv','get','-format=json','secret/platform/'+path])['data']['data']
creds=kv('terraform-state/tenants')
env.update(AWS_ACCESS_KEY_ID=creds['access_key'],AWS_SECRET_ACCESS_KEY=creds['secret_key'],AWS_SSE_CUSTOMER_KEY=creds['sse_customer_key'],AWS_CA_BUNDLE=str(root/'config/opensearch-ca.crt'),AWS_EC2_METADATA_DISABLED='true',TF_VAR_opensearch_password=kv('opensearch/admin')['password'],TF_VAR_opensearch_ca_file=str(root/'config/opensearch-ca.crt'))
if not env.get('RANCHER_TOKEN_KEY'):
 k=read(['kubectl','config','view','--raw','--minify','--context=rancher','-o','json']);env['RANCHER_TOKEN_KEY']=k['users'][0]['user']['token']
if not env.get('KEYCLOAK_PASSWORD'):
 k=read(['kubectl','--context=rke2-cluster1','get','sts','keycloak','-n','keycloak','-o','json']);e={x['name']:x.get('value') for x in k['spec']['template']['spec']['containers'][0]['env']};env['KEYCLOAK_USER']=e['KC_BOOTSTRAP_ADMIN_USERNAME'];env['KEYCLOAK_PASSWORD']=e['KC_BOOTSTRAP_ADMIN_PASSWORD']
env.setdefault('HARBOR_USERNAME','admin');env.setdefault('HARBOR_PASSWORD',kv('harbor/credentials')['admin-password'])
if not env.get('VAULT_TOKEN'):env['VAULT_TOKEN']=(Path.home()/'.vault-token').read_text().strip()
with tempfile.TemporaryDirectory(prefix='afi-terraform-ca-') as d:
 ca=Path(d)/'ca.pem';ca.write_text(Path('/etc/ssl/certs/ca-certificates.crt').read_text()+(root/'config/opensearch-ca.crt').read_text());env['SSL_CERT_FILE']=str(ca)
 cmd=['python3',str(root/'scripts/terraform-admin.py'),a.command,*a.arguments]
 r=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 output=r.stdout
 for k in ['AWS_SECRET_ACCESS_KEY','AWS_SSE_CUSTOMER_KEY','RANCHER_TOKEN_KEY','KEYCLOAK_PASSWORD','HARBOR_PASSWORD','VAULT_TOKEN','TF_VAR_opensearch_password']:
  output=output.replace(env[k],'[REDACTED]')
 print(output,end='');raise SystemExit(r.returncode)
