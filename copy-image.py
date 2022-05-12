#!/usr/bin/python3

# Copyright 2022 RetailNext, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HTTP_PROXY = 'http://127.0.0.1:8080'
MAX_ATTEMPTS = 10
REMAP_ENV_PREFIX = 'REMAP_ENV_'
SSH_DIR = '/root/.ssh'
SSH_ID = SSH_DIR + '/id'


def apply_env_remapping():
    remap_keys = [k for k in os.environ.keys() if k.startswith(REMAP_ENV_PREFIX)]
    for k in remap_keys:
        src_key = os.environ[k]
        dst_key = k[len(REMAP_ENV_PREFIX):]
        os.environ[dst_key] = os.environ[src_key]
        del os.environ[k]
        del os.environ[src_key]
        print(f"remap_env: set {dst_key} to the value of {src_key}")


def get_helper(repo):
    if 'gcr.io' in repo or 'pkg.dev' in repo:
        return 'gcr'
    elif '.dkr.ecr.' in repo:
        return 'ecr-login'
    else:
        sys.exit('unable to determine helper for: {}'.format(repo))


def get_auth(repo):
    helper = f"docker-credential-{get_helper(repo)}"
    result = subprocess.run([helper, "get"],
                            input=f"{repo}\n".encode('utf-8'),
                            capture_output=True)
    if result.returncode != 0:
        sys.exit(f"failed to get credentials for {repo}\nstdout: {result.stdout}\nstderr: {result.stderr}")
    auth = json.loads(result.stdout)
    s = f"{auth['Username']}:{auth['Secret']}"
    encoded = base64.b64encode(s.encode('utf-8'))
    return encoded.decode('utf-8')


def setup_docker(*repos):
    Path('/root/.docker').mkdir(0o700, parents=True, exist_ok=True)
    cfg = {'auths': {}}
    for repo in repos:
        if repo not in cfg['auths']:
            cfg['auths'][repo] = {'auth': get_auth(repo)}
    Path('/root/.docker/config.json').write_text(json.dumps(cfg))
    os.environ['HOME'] = '/root'


def setup_ssh_key():
    if 'SSH_KEY' not in os.environ:
        return False
    ssh_key = os.environ['SSH_KEY']
    del os.environ['SSH_KEY']
    Path(SSH_DIR).mkdir(mode=0o700, parents=True, exist_ok=True)
    Path(SSH_ID).write_text(ssh_key)
    Path(SSH_ID).chmod(0o400)
    return True


def start_tunnel():
    if not setup_ssh_key():
        print('tunnel: disabled because SSH_KEY was not set')
        return None

    user = os.environ['SSH_USER']
    del os.environ['SSH_USER']

    remote_args = []
    for route in [s.strip() for s in os.environ['SSH_HOSTS'].split()]:
        parts = []
        for host in route.split(','):
            host = host.strip()
            if host:
                parts.append('ssh://{}/#{}::{}'.format(host, user, SSH_ID))
        if parts:
            remote_args.append('-r')
            remote_args.append('__'.join(parts))
    if not remote_args:
        sys.exit('No valid SSH_HOSTS chains')
    del os.environ['SSH_HOSTS']

    os.environ['http_proxy'] = HTTP_PROXY
    os.environ['https_proxy'] = HTTP_PROXY

    args = ['/venv/bin/pproxy', '-v', '-d', '-l', HTTP_PROXY] + remote_args
    print(f"pproxy: starting {' '.join(args)}")
    proc = subprocess.Popen(args, stdout=sys.stdout, stderr=sys.stderr)
    time.sleep(1)
    if proc.poll() is None:
        print('pproxy: started')
        return proc
    sys.exit('pproxy: failed to start')


def copy_image(src_image, dest_image, max_attempts):
    attempt = 0
    while attempt < max_attempts:
        args = ['/usr/local/bin/regctl', 'image', 'copy', '-v', 'debug', src_image, dest_image]
        print(f"regctl: starting {' '.join(args)}")
        result = subprocess.run(args, stdout=sys.stdout, stderr=sys.stderr)
        if result.returncode == 0:
            print('regctl: completed')
            return True
        print(f"regctl: failed with return code {result.returncode}")
        attempt += 1
    sys.exit("regctl: giving up after {MAX_ATTEMPTS}")


def copy_images(src_image, *dest_images):
    for dest_image in dest_images:
        # copy_image will crash us out if MAX_ATTEMPTS is exceeded
        copy_image(src_image, dest_image, MAX_ATTEMPTS)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit('usage: src dest [dest...]')

    apply_env_remapping()

    tunnel = start_tunnel()

    setup_docker(*[image.split('/')[0] for image in sys.argv[1:]])
    copy_images(*sys.argv[1:])

    if tunnel:
        print('pproxy: terminating')
        tunnel.terminate()
        print('pproxy: waiting')
        tunnel.wait()
        print('pproxy: done')
