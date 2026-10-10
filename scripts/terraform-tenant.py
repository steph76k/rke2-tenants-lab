#!/usr/bin/env python3
"""Run Terraform with a separate working directory and state key for one tenant.
Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SSE_CUSTOMER_KEY, AWS_CA_BUNDLE
and provider credentials outside Git. Set TERRAFORM_BIN to select Terraform >=1.10.
"""
import argparse,os,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('tenant');p.add_argument('command',choices=['init','plan','apply','validate','fmt','output','state','show','providers','version'])
p.add_argument('arguments',nargs=argparse.REMAINDER);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
if not re.fullmatch(r'[a-z][a-z0-9-]{1,39}',a.tenant) or not (root/'tenants'/f'{a.tenant}.json').is_file():p.error('Unknown tenant')
os.umask(0o077)
env=dict(os.environ,TF_VAR_tenant_slug=a.tenant,TF_DATA_DIR=str(root/'.terraform'/a.tenant))
args=[os.environ.get('TERRAFORM_BIN','terraform'),f'-chdir={root}/terraform',a.command]
if a.command=='init':
 args += [f'-backend-config={root}/config/backend.s3.hcl',f'-backend-config=key=lab/{a.tenant}/terraform.tfstate',f'-backend-config=workspace_key_prefix=lab/{a.tenant}/workspaces']
args+=a.arguments
raise SystemExit(subprocess.call(args,env=env))
