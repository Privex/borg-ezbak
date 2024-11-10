"""
Main app file for borg-ezbak
"""
from pathlib import Path
from os import getenv as env, makedirs
from os.path import join, dirname, abspath
from privex.helpers import empty, DictObject, env_bool, is_true
from privex.loghelper import LogHelper
from datetime import datetime
from rich import print as rprint
from rich.prompt import Prompt, Confirm
import yaml
import os
import sys
import subprocess

_lh = LogHelper("ezbak", handler_level="DEBUG")
_lh.add_console_handler()

log = _lh.get_logger()

cf = {}
BASE_DIR = Path(__file__).resolve().parent.parent

cfgfile = BASE_DIR / "config.yml"
DRY = env_bool('DRY', env_bool('DRY_RUN', False))

repo_defaults = dict(
    compress="lz4",
    stats=True,
    prune=dict(hourly=1, daily=7, monthly=3, yearly=1),
    password="",
    exclude=['*.log', '*.log.*'],
    path="/backups"
)

def load_config(filepath = cfgfile) -> dict:
    filepath = Path(filepath)
    _cf = {}
    if filepath.exists():
        log.debug(f"Loading config file at {filepath}")
        with open(str(filepath), "r") as f:
            _cf = yaml.safe_load(f)
    log.debug(f"Config file contains: {_cf}")
    if 'repos' not in _cf:
        log.debug("'repos' not in config, adding empty repos field")
        _cf['repos'] = {}
    return _cf

cf = load_config()

def gen_reponame(rep: dict) -> str:
    repname = socket.gethostname() if empty(rep.get('name')) else rep.name
    date_format = rep.get('date_format', '%Y-%m-%d-%H%M')
    repo_format = rep.get('repo_format', '{name}-{date}')
    formatted = datetime.utcnow().strftime(date_format)
    xfmt = repo_format.format(name=repname, date=formatted)
    log.debug(f"Generated repo name {xfmt} from date_format '{date_format}' and repo_format '{repo_format}'")
    return xfmt


def gen_args(rep: dict) -> list:
    rep = DictObject(rep)
    log.debug(f"Generating arguments for borg create for repo '{rep.name}'")
    if empty(rep.get('path', None)):
        raise Exception("Must have 'path' in repo config")
    if empty(rep.get('backup', None)):
        raise Exception("Must have 'backup' in repo config")

    zargs = []
    if 'compression' in rep:
        rep['compress'] = rep.compression
    if 'compress' in rep:
        zargs += ["--compression", "lz4" if empty(rep.compress) else rep.compress]
    if 'exclude' in rep:
        for x in rep.exclude:
            zargs += ['-e', x]
    if 'create_flags' in rep:
        zargs += list(rep.create_flags)
    if is_true(rep.get('stats', True)):
        zargs += ['--stats']

    repo_name = gen_reponame(rep)
    zargs += [f"{rep['path']}::{repo_name}"]
    zargs += list(rep.backup)
    
    return zargs

def run_borg_create(rep: dict):
    rep = DictObject(rep)
    # BORG_PASSPHRASE = rep.get('password', env('BORG_PASSPHRASE', None))
    my_env = os.environ.copy()
    my_env['BORG_PASSPHRASE'] = rep.get('password', env('BORG_PASSPHRASE', None))
    b_args = gen_args(rep)
    log.info("Running borg with arguments:", b_args)
    if not DRY:
        p = subprocess.Popen(["borg", "create"] + b_args, env=my_env)


def init_repo(rep: dict = None):
    rpath = Prompt.ask("[yellow]Please enter the repo path you'd like to initialise[/]")

    rprint(
        "[cyan]Now you'll need to select the type of encryption you'd like to use for the repo, "
        "the default recommended option is [b]'repokey'[/] which involves you simply specifying a password "
        "which will be used to encrypt your backups.\n"
        "You can also use [b]'keyfile'[/] if you'd prefer to have a file that you use as a key instead.\n"
        "If you really don't want encryption, you can select [b]'none'[/b] to disable encryption.[/]\n"
    )
    rprint(
        "[blue]All encryption options:[/]\n\n"
        " - repokey (DEFAULT)\n"
        " - keyfile\n"
        " - none\n"
        " - repokey-blake2\n"
        " - keyfile-blake2\n"
        " - authenticated\n"
        " - authenticated-blake2\n\n"
    )

    rencrypt = Prompt.ask(
        "[yellow]Please select the encryption method you'd like to use[/]",
        choices=[
            "none", "repokey", "keyfile", "repokey-blake2", "keyfile-blake2",
            "authenticated", "authenticated-blake2"
        ], default="repokey"
    )
   
    rprint(f"[yellow]Path:[/] {rpath}")
    rprint(f"[yellow]Encryption:[/] {rencrypt}")
    
    if Confirm.ask("Do you want to continue creating this repo?"):
        subprocess.run(['borg', 'init', '-e', rencrypt, rpath])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        return init_repo()
    for name, confz in cf['repos'].items():
        if 'name' not in confz:
            confz['name'] = name
        run_borg_create(confz)

if __name__ == '__main__':
    main()

