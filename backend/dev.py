"""Start the API, simulator worker and frontend. Works on Windows and Linux."""
from pathlib import Path
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

BACKEND=Path(__file__).resolve().parent
ROOT=BACKEND.parent
PYTHON=BACKEND/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
env=os.environ.copy()
env['PATH']=str(PYTHON.parent)+os.pathsep+env.get('PATH','')
node=shutil.which('node')
local_node=ROOT/'frontend'/'.tools'/('node.exe' if os.name=='nt' else 'node')
if not node and local_node.exists(): node=str(local_node)
if not PYTHON.exists() or not node:
    sys.exit('Install backend/.venv and Node.js for the React build tools; see backend/README.md.')
processes=[]
def port_in_use(port):
    with socket.socket() as connection:
        connection.settimeout(.3)
        return connection.connect_ex(('127.0.0.1',port)) == 0

occupied=[port for port in (8000,5173) if port_in_use(port)]
if occupied:
    sys.exit(f'JeevanGrid cannot start: port(s) {", ".join(map(str,occupied))} already in use. '
             'Stop the previous JeevanGrid servers in their terminals, then run python3 backend/dev.py again. '
             'No new services were started.')

def launch(command,cwd):
    process=subprocess.Popen(command,cwd=cwd,env=env,start_new_session=os.name!='nt')
    processes.append(process)
    return process

try:
    launch([str(PYTHON),'-m','uvicorn','config.asgi:application','--host','127.0.0.1','--port','8000'],ROOT/'backend')
    launch([str(PYTHON),'manage.py','run_live_worker'],ROOT/'backend')
    launch([str(PYTHON),'manage.py','run_assistant_worker'],ROOT/'backend')
    vite=ROOT/'frontend'/'node_modules'/'vite'/'bin'/'vite.js'
    command=[node,str(vite),'--host','127.0.0.1']
    launch(command,ROOT/'frontend')
    deadline=time.monotonic()+20
    while all(p.poll() is None for p in processes) and not all(port_in_use(port) for port in (8000,5173)) and time.monotonic()<deadline:
        time.sleep(.2)
    if any(p.poll() is not None for p in processes) or not all(port_in_use(port) for port in (8000,5173)):
        raise RuntimeError('A JeevanGrid service did not start. Check the error above.')
    print('JeevanGrid ready: http://127.0.0.1:5173  |  Ctrl+C stops all four services.',flush=True)
    while all(p.poll() is None for p in processes):time.sleep(.5)
except KeyboardInterrupt:
    pass
finally:
    for p in processes:
        if os.name=='nt':
            if p.poll() is None:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
        else:
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
    for p in processes:
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill()
