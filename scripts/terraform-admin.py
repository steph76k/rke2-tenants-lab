#!/usr/bin/env python3
"""Run the shared administrative Terraform state for all declared tenants.
Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SSE_CUSTOMER_KEY, AWS_CA_BUNDLE
and provider credentials outside Git. Set TERRAFORM_BIN to select Terraform >=1.10.
"""
import argparse,os,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('command',choices=['init','plan','apply','validate','fmt','output','state','show','providers','version'])
p.add_argument('arguments',nargs=argparse.REMAINDER);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
os.umask(0o077)
env=dict(os.environ,TF_DATA_DIR=str(root/'.terraform'/'tenants'))
env.pop('TF_VAR_tenant_slug',None)
if env.get('TF_WORKSPACE','default') != 'default':p.error('Only the shared default workspace is supported')
args=[os.environ.get('TERRAFORM_BIN','terraform'),f'-chdir={root}/terraform',a.command]
if a.command=='init':
 args += [f'-backend-config={root}/config/backend.s3.hcl',f'-backend-config=key=lab/tenants/terraform.tfstate',f'-backend-config=workspace_key_prefix=lab/tenants/workspaces']
args+=a.arguments
raise SystemExit(subprocess.call(args,env=env))
