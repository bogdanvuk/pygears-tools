#!/usr/bin/env python3

import os
import sys
import logging
import json
import shutil
import glob
import errno
import argparse
import configparser
from pygears_tools.utils import (shell_source, custom_run, download_and_untar, list_pkg_deps,
                                 clone_git, install_deps, set_env, os_name, install_deps, pip_install)
from pygears_tools import default_cpp


def create_logger(pkg):
    logger = logging.getLogger(pkg["name"])
    logger.setLevel(logging.INFO)
    # create file handler which logs even debug messages

    # log_file = os.path.join(pkg["install_path"], "custom_cmd.log")
    # fh = logging.FileHandler(log_file, mode='w')
    # fh.setLevel(logging.INFO)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s [%(name)-12s]: %(message)s', datefmt='%H:%M:%S')
    # fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    # logger.addHandler(fh)
    logger.addHandler(ch)
    pkg["logger"] = logger


def os_install_cmd():
    name = os_name()
    if name == "ubuntu":
        return "sudo apt install -y"
    elif name == "opensuse":
        return "sudo zypper --non-interactive install"
    else:
        raise "Unsupported OS"


def filter_deps_by_os(pkgs):
    name = os_name()
    for pkg in pkgs:
        if ('deps' in pkg) and name in pkg['deps']:
            pkg['deps'] = pkg['deps'][name]


def copyanything(src, dst):
    try:
        shutil.copytree(src, dst)
    except OSError as exc:  # python >2.5
        if exc.errno == errno.ENOTDIR:
            shutil.copy(src, dst)
        else:
            raise


def get_pkg_classes(pkgs):
    classes = set()

    for pkg in pkgs:
        if 'class' in pkg:
            classes.update(pkg['class'])

    return classes


def print_pkg_deps_install(lines):
    for l in lines:
        print('{} {}'.format(os_install_cmd(), ' '.join(l)))


def expand_path(path):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def install(pkgs_fn, pkg_names, tools_path, home_path, do_install_deps, list_deps, dry_run):
    # print("Please enter sudo password:")
    # subprocess.run('sudo echo "Current install directory"; pwd', shell=True)

    cfg = {
        "home_path": expand_path(home_path),
        "tools_path": expand_path(tools_path) if tools_path else None,
        "tools_install_path": expand_path(tools_path) if tools_path else '~/.pygears/tools',
        "install_script_path": expand_path(os.path.dirname(__file__)),
        "tools_sh_path": expand_path(os.path.join(tools_path, "tools.sh")) if tools_path else None,
        "pkgs_fn": expand_path(pkgs_fn),
        'dry_run': dry_run
    }

    if not list_deps:
        if cfg["tools_path"]:
            print(f'Installing to: {cfg["tools_path"]}')
        else:
            print(f'Installing system-wide')

    with open(cfg["pkgs_fn"]) as json_data:
        pkgs = json.load(json_data)

    if pkg_names:
        pkgs = [
            p for p in pkgs
            if (p['name'] in pkg_names or any(cls in pkg_names for cls in p['class']))
        ]

    filter_deps_by_os(pkgs)

    if list_deps:
        deps = list_pkg_deps(pkgs)
        print_pkg_deps_install(deps)
        return 0

    if not cfg['dry_run']:
        os.makedirs(cfg["home_path"], exist_ok=True)

        os.makedirs(cfg["tools_install_path"], exist_ok=True)
        os.chdir(cfg["tools_install_path"])

    if cfg["tools_sh_path"] and not os.path.exists(cfg["tools_sh_path"]):
        with open(cfg["tools_sh_path"], "w") as text_file:
            print("#!/bin/bash", file=text_file)
            print("# Script for setting up the environment for all the tools", file=text_file)
            print("# Tools installed relative to: {}".format(cfg["tools_path"]), file=text_file)
            print("", file=text_file)

            print("# Setting new home directory:", file=text_file)

            print("export HOME={}".format(cfg["home_path"]), file=text_file)

    if not cfg['dry_run']:
        shell_source(cfg["tools_sh_path"])

    pyenv = False
    for i in range(len(pkgs)):
        if pkgs[i]['name'] == 'pyenv':
            if not cfg['tools_path']:
                del pkgs[i]
            else:
                pyenv = True

            break

    for pkg in pkgs:
        pkg.update(cfg)

        if pkg['tools_path']:
            pkg["path"] = expand_path(os.path.join(pkg["tools_install_path"], pkg["name"]))
        else:
            pkg["path"] = None

        pkg["install_path"] = expand_path(
            os.path.join(pkg["tools_install_path"], pkg["name"], "_install"))

        if not cfg['dry_run']:
            os.chdir(pkg["tools_install_path"])
            os.makedirs(pkg["name"], exist_ok=True)
            os.makedirs(pkg["install_path"], exist_ok=True)

        if "src_root_path" in pkg:
            pkg["src_root_path"] = pkg["src_root_path"].format(**pkg)

        create_logger(pkg)

    if do_install_deps:
        install_deps(pkgs)

    for pkg in pkgs:

        pkg["logger"].info("Installation started.")
        os.chdir(pkg["install_script_path"])

        if "copy" in pkg:
            pkg["logger"].info("Copying package files...")
            for cmd in pkg["copy"]:
                for fn in glob.glob(cmd[0].format(**pkg)):
                    pkg["logger"].info("Copying {} to {}".format(fn, cmd[1].format(**pkg)))

                    if not pkg['dry_run']:
                        copyanything(fn, os.path.join(cmd[1].format(**pkg), os.path.basename(fn)))

        if not pkg['dry_run']:
            os.chdir(pkg["install_path"])

        if "url" in pkg:
            download_and_untar(pkg)

        if "git" in pkg:
            clone_git(pkg)

        custom_run(pkg, "pre_custom_run")

        if pkg['path']:
            custom_run(pkg, "pre_custom_runl")

        if "flow" in pkg:
            pkg["logger"].info("Using {} flow.".format(pkg["flow"]))
            if pkg["flow"] == "default_cpp":
                default_cpp.flow(pkg)

        if "pip" in pkg:
            pip_install(pkg, pyenv)

        if not pkg['dry_run']:
            os.chdir(pkg["install_path"])

        if pkg['tools_path']:
            set_env(pkg)

        custom_run(pkg, "post_custom_run")
        if pkg['path']:
            custom_run(pkg, "post_custom_runl")

        pkg["logger"].info("Installation finished successfully!")

    print('Installation finished, before invoking tools, source {}'.format(cfg["tools_sh_path"]))


def get_argparser():
    parser = argparse.ArgumentParser(prog="PyGears tools installer")

    parser.add_argument('-p',
                        dest='pkgs_fn',
                        default=os.path.join(os.path.dirname(__file__), 'pkgs.json'),
                        help="Path to packages description file")

    parser.add_argument('-o',
                        dest='tools_path',
                        default=None,
                        help="Directory to install tools to. Default will install system-wide")

    parser.add_argument('-w',
                        dest='home_path',
                        default=os.path.expanduser("~"),
                        help="Directory to setup home in")

    parser.add_argument('-l',
                        dest='list_deps',
                        action='store_true',
                        help="Only list the package dependencies and exit")

    parser.add_argument('-d',
                        dest='install_deps',
                        action='store_true',
                        help="Automatically install system dependencies. Will require sudo.")

    parser.add_argument('-r', dest='dry_run', action='store_true', help="Dry run")

    parser.add_argument(
        'pkg_names',
        metavar='pkg_names',
        nargs='*',
        default=['gui'],
        help=
        'Names of packages to install. Can be one of: emacs, spacemacs, gtkwave, verilator, systemc, scv, pyenv, python, ripgrep, spacemacs_python, pygears'
    )

    return parser


def main(argv=sys.argv):
    parser = get_argparser()
    args = parser.parse_args(argv[1:])

    install(args.pkgs_fn, args.pkg_names, args.tools_path, args.home_path, args.install_deps,
            args.list_deps, args.dry_run)


# main([
#     '', '-d'
# ])
# main(['', '-dr'])
# main(['', '-dr'])
