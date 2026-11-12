#!/usr/bin/env python3
"""Record a local validation command and its exact result; never use credentials."""
from pathlib import Path
import datetime,json,os,subprocess,sys
root=Path(__file__).resolve().parents[2]
label,*cmd=sys.argv[1:]
env=os.environ.copy()
for key in list(env):
 if any(word in key.upper() for word in ('TOKEN','SECRET','PASSWORD','API_KEY')): env.pop(key)
env.update(PYTHONPATH=str(root/'tools'),TRURETURING_DIR='/Users/lexa/Desktop/lexa/omega/trureturing',TMPDIR=os.environ.get('MATHESIS_TASK_TMP', '/var/folders/jd/5x6vvk8d4yzcmtmp7mjw_9nw0000gn/T/mathesis-chen-chen.YqWUyy'),XDG_CACHE_HOME=str(root/'.cache'),TECTONIC='/opt/homebrew/bin/tectonic',PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1',npm_config_cache=str(root/'.cache/npm'),GIT_TERMINAL_PROMPT='0',PW_CHROMIUM_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
out=root/'docs/project/validation';out.mkdir(parents=True,exist_ok=True)
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (out/(label+'.txt')).open('w') as f:
 p=subprocess.Popen(cmd,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 for line in p.stdout: f.write(line);f.flush();print(line,end='',flush=True)
 rc=p.wait()
record={'command':cmd,'exit_code':rc,'started_at':start,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'log':label+'.txt'}
with (out/'commands.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
print('Recorded exit:',rc)
sys.exit(rc)
