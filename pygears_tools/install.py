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
from pygears_tools.utils import (shell_source, custom_run, download_and_untar,
                                 clone_git, install_deps, set_env)
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
    formatter = logging.Formatter(
        '%(asctime)s [%(name)-12s]: %(message)s', datefmt='%H:%M:%S')
    # fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    # logger.addHandler(fh)
    logger.addHandler(ch)
    pkg["logger"] = logger


def os_name():
    with open('/etc/os-release') as f:
        file_content = '[root]\n' + f.read()

    os_cfg = configparser.RawConfigParser()
    os_cfg.read_string(file_content)

    name = os_cfg['root']['NAME'].strip('"').split()[0].lower()

    return name


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


def list_pkg_deps(pkgs):
    deps = []
    for pkg in pkgs:
        if 'git' in pkg:
            pkg['deps'] = ' '.join([pkg.get('deps', ''), 'git'])

        if 'deps' in pkg:
            deps += pkg['deps'].split()

    if any(pkg.get("flow", '') == "default_cpp" for pkg in pkgs):
        print('{} {}'.format(os_install_cmd(),
                             default_cpp.dependencies[os_name()]))

    print('{} {}'.format(os_install_cmd(), ' '.join(set(deps))))


def expand_path(path):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def install(pkgs_fn, pkg_names, tools_path, home_path, do_install_deps,
            list_deps):
    # print("Please enter sudo password:")
    # subprocess.run('sudo echo "Current install directory"; pwd', shell=True)

    cfg = {
        "home_path": expand_path(home_path),
        "tools_path": expand_path(tools_path),
        "install_script_path": expand_path(os.path.dirname(__file__)),
        "tools_sh_path": expand_path(os.path.join(tools_path, "tools.sh")),
        "pkgs_fn": expand_path(pkgs_fn)
    }

    if not list_deps:
        print('Installing to: {}'.format(cfg["tools_path"]))

    with open(cfg["pkgs_fn"]) as json_data:
        pkgs = json.load(json_data)

    if pkg_names:
        pkgs = [p for p in pkgs if p['name'] in pkg_names]

    filter_deps_by_os(pkgs)

    if list_deps:
        list_pkg_deps(pkgs)
        return 0

    os.makedirs(cfg["tools_path"], exist_ok=True)
    os.makedirs(cfg["home_path"], exist_ok=True)

    os.chdir(cfg["tools_path"])

    if not os.path.exists(cfg["tools_sh_path"]):
        with open(cfg["tools_sh_path"], "w") as text_file:
            print("#!/bin/bash", file=text_file)
            print(
                "# Script for setting up the environment for all the tools",
                file=text_file)
            print(
                "# Tools installed relative to: {}".format(cfg["tools_path"]),
                file=text_file)
            print("", file=text_file)

            print("# Setting new home directory:", file=text_file)

            print("export HOME={}".format(cfg["home_path"]), file=text_file)

    shell_source(cfg["tools_sh_path"])

    for pkg in pkgs:
        pkg.update(cfg)
        pkg["path"] = expand_path(os.path.join(pkg["tools_path"], pkg["name"]))
        pkg["install_path"] = expand_path(
            os.path.join(pkg["path"], "_install"))

        os.chdir(pkg["tools_path"])
        os.makedirs(pkg["name"], exist_ok=True)
        os.makedirs(pkg["install_path"], exist_ok=True)
        if "src_root_path" in pkg:
            pkg["src_root_path"] = pkg["src_root_path"].format(**pkg)

        create_logger(pkg)

    if do_install_deps:
        for pkg in pkgs:
            if pkg.get("flow", '') == "default_cpp":
                pkg['deps'] = ' '.join(
                    [pkg.get('deps', ''), default_cpp.dependencies])

            if 'git' in pkg:
                pkg['deps'] = ' '.join([pkg.get('deps', ''), 'git'])

            install_deps(pkg)

    for pkg in pkgs:

        pkg["logger"].info("Installation started.")
        os.chdir(pkg["install_script_path"])

        if "copy" in pkg:
            pkg["logger"].info("Copying package files...")
            for cmd in pkg["copy"]:
                for fn in glob.glob(cmd[0].format(**pkg)):
                    pkg["logger"].info("Copying {} to {}".format(
                        fn, cmd[1].format(**pkg)))
                    copyanything(
                        fn,
                        os.path.join(cmd[1].format(**pkg),
                                     os.path.basename(fn)))

        if os.path.exists(pkg['path']):
            os.chdir(pkg["path"])

        if "url" in pkg:
            download_and_untar(pkg)

        if "git" in pkg:
            clone_git(pkg)

        custom_run(pkg, "pre_custom_run")

        if "flow" in pkg:
            pkg["logger"].info("Using {} flow.".format(pkg["flow"]))
            if pkg["flow"] == "default_cpp":
                default_cpp.flow(pkg)

        if os.path.exists(pkg['path']):
            os.chdir(pkg["path"])

        set_env(pkg)
        custom_run(pkg, "post_custom_run")

        pkg["logger"].info("Installation finished successfully!")

    print('Installation finished, before invoking tools, source {}'.format(
        cfg["tools_sh_path"]))


def get_argparser():
    parser = argparse.ArgumentParser(prog="PyGears tools installer")

    parser.add_argument(
        '-p',
        dest='pkgs_fn',
        default=os.path.join(os.path.dirname(__file__), 'pkgs.json'),
        help="Path to packages description file")

    parser.add_argument(
        '-o',
        dest='tools_path',
        default=os.path.expanduser('~/.pygears/tools'),
        help="Directory to install tools to")

    parser.add_argument(
        '-w', dest='home_path', default="~", help="Directory to setup home in")

    parser.add_argument(
        '-l',
        dest='list_deps',
        action='store_true',
        help="Only list the package dependencies and exit")

    parser.add_argument(
        '-d',
        dest='install_deps',
        action='store_true',
        help="Automatically install system dependencies. Will require sudo.")

    parser.add_argument(
        'pkg_names',
        metavar='pkg_names',
        nargs='*',
        help=
        'Names of packages to install. Can be one of: emacs, spacemacs, gtkwave, verilator, systemc, scv, pyenv, python, ripgrep, spacemacs_python, pygears'
    )

    return parser


def main(argv=sys.argv):
    parser = get_argparser()
    args = parser.parse_args(argv[1:])

    install(args.pkgs_fn, args.pkg_names, args.tools_path, args.home_path,
            args.install_deps, args.list_deps)


# main([
#     '', '-o', '/tools/home/work/pygears_tools_test', '-w',
#     '/tools/home/work/pygears_tools_test/home', '-d'
# ])
# main(['', '-l'])
