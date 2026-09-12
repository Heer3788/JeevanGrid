"""Start both local services after installation. Works on Windows and Linux."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
PYTHON=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
env=os.environ.copy()
env['PATH']=str(PYTHON.parent)+os.pathsep+env.get('PATH','')
npm=shutil.which('npm',path=env['PATH'])
if not PYTHON.exists() or not npm:
    sys.exit('Install the virtual environment and Node.js first; see README.md.')
processes=[]
try:
    processes.append(subprocess.Popen([str(PYTHON),'manage.py','runserver','127.0.0.1:8000','--noreload'],cwd=ROOT/'backend',env=env))
    local_node=PYTHON.parent/'node'
    vite=ROOT/'frontend'/'node_modules'/'vite'/'bin'/'vite.js'
    # nodejs-wheel entry-point shebangs retain an old absolute path when a
    # ready demo folder is moved. This invocation remains valid after a move.
    if os.name!='nt' and local_node.exists() and vite.exists():
        command=[str(PYTHON),str(local_node),str(vite),'--host','127.0.0.1']
    else:
        command=[npm,'run','dev']
        if os.name=='nt': command=['cmd','/c',*command]
    processes.append(subprocess.Popen(command,cwd=ROOT/'frontend',env=env))
    print('JeevanGrid: http://127.0.0.1:5173  |  Ctrl+C stops both services.',flush=True)
    while all(p.poll() is None for p in processes):time.sleep(.5)
except KeyboardInterrupt:
    pass
finally:
    for p in processes:
        if p.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
            else:p.terminate()
    for p in processes:
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill()
