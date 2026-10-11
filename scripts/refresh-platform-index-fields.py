#!/usr/bin/env python3
"""Initialize Dashboards' computed field cache for Terraform-owned global views.
The provider deliberately excludes this cache from state; Discover needs the
timestamp field available before its first histogram query. No log data is read.
"""
import json
import os
import subprocess
from pathlib import Path

import requests

root = Path(__file__).resolve().parents[1]
env = dict(os.environ, BAO_ADDR='https://openbao.berger.ph', BAO_NAMESPACE='')
r = subprocess.run([env.get('BAO_BIN','/home/tanzu/.local/bin/bao'), 'kv', 'get',
    '-format=json', 'secret/platform/opensearch/admin'], env=env, capture_output=True, text=True)
if r.returncode:
    raise RuntimeError('OpenBao credential lookup failed; sensitive output suppressed')
password = json.loads(r.stdout)['data']['data']['password']
s = requests.Session()
s.verify = str(root/'config/opensearch-ca.crt')
s.headers.update({'osd-xsrf':'terraform-platform-views','securitytenant':''})
base = 'https://opensearch.berger.ph'
r = s.post(base+'/auth/login',json={'username':'admin','password':password},timeout=30)
r.raise_for_status()
for name,pattern in [('logs','logs-*'),('all','*')]:
    path = base+'/api/saved_objects/index-pattern/afi-platform-'+name
    r=s.get(path,timeout=30);r.raise_for_status();assert r.json()['attributes']['title']==pattern
    r=s.get(base+'/api/index_patterns/_fields_for_wildcard',params={
        'pattern':pattern,'meta_fields':['_source','_id','_type','_index','_score']},timeout=60)
    r.raise_for_status();fields=r.json()['fields']
    if name=='logs':assert any(f['name']=='@timestamp' and f['type']=='date' for f in fields)
    r=s.put(path,json={'attributes':{'fields':json.dumps(fields)}},timeout=30)
    r.raise_for_status()
    print('Global index field cache initialized:',pattern,len(fields),'fields')
