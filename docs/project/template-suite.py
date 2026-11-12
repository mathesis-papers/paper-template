"""Run the upstream's example-dependent suite, then restore the empty-template selection."""
from pathlib import Path
import subprocess,sys
site=Path('site.toml');original=site.read_bytes()
try:
 site.write_bytes(original.replace(b'hide = ["example-*"]',b'hide = []'))
 result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tools/tests'])
finally:
 site.write_bytes(original)
sys.exit(result.returncode)
