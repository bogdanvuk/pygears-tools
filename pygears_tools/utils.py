import configparser
import urllib.request
import tarfile
import io
import sys
import subprocess
import os
import shutil


def os_name():
    with open('/etc/os-release') as f:
        file_content = '[root]\n' + f.read()

    os_cfg = configparser.RawConfigParser()
    os_cfg.read_string(file_content)

    name = os_cfg['root']['NAME'].strip('"').split()[0].lower()

    return name


def get_url_archive_file_name(pkg):
    return os.path.basename(pkg["url"])


def get_url_archive_path(pkg):
    return os.path.join(pkg['install_path'], get_url_archive_file_name(pkg))


def download_source(pkg):
    fn = get_url_archive_file_name(pkg)

    def dlProgress(count, blockSize, totalSize):
        percent = int(count * blockSize * 100 / totalSize)
        sys.stdout.write("\rProgress: %d%%" % percent)
        sys.stdout.flush()

    pkg["logger"].info("Downloading " + pkg["url"])

    if not pkg['dry_run']:
        urllib.request.urlretrieve(pkg["url"], get_url_archive_path(pkg), dlProgress)
        sys.stdout.write("\n")

    return fn


class ProgressFileObject(io.FileIO):
    def __init__(self, path, pkg, *args, **kwargs):
        self._total_size = os.path.getsize(path)
        self._fn = os.path.basename(path)
        self._last_percent = -1
        self._pkg = pkg
        io.FileIO.__init__(self, path, *args, **kwargs)

    def read(self, size):
        percent = int(self.tell() * 100 / self._total_size)
        if percent != self._last_percent:
            self._last_percent = percent
            # sys.stdout.write("\r[" + pkg["name"] + "] Downloading " + self._fn + "... [%d%%]" % percent)
            sys.stdout.write("\rProgress: %d%%" % percent)
            sys.stdout.flush()

        return io.FileIO.read(self, size)


def untar(pkg):
    pkg["logger"].info("Unpacking " + get_url_archive_file_name(pkg))
    if not pkg['dry_run']:
        tar = tarfile.open(fileobj=ProgressFileObject(get_url_archive_path(pkg), pkg))
        tar.extractall(pkg['install_path'])
        tar.close()
        sys.stdout.write("\n")


def download_and_untar(pkg):
    fn = get_url_archive_path(pkg)
    if not os.path.exists(fn):
        download_source(pkg)
    else:
        pkg["logger"].info("Source archive already available and will be reused.")

    src_dir = pkg["src_root_path"]

    unpack = False
    if not os.path.exists(src_dir):
        unpack = True
    else:
        srctime = os.path.getmtime(fn)
        tartime = os.path.getmtime(src_dir)

        if tartime < srctime:
            unpack = True

            if not pkg['dry_run']:
                shutil.rmtree(src_dir)

            pkg["logger"].info("Source older than archive, updating...")

    if unpack:
        untar(pkg)
    else:
        pkg["logger"].info("Sources already present and up to date.")


def list_pkg_deps(pkgs):
    deps = []
    for pkg in pkgs:
        if 'git' in pkg:
            pkg['deps'] = ' '.join([pkg.get('deps', ''), 'git'])

        if 'deps' in pkg:
            deps += pkg['deps'].split()

    resp = [set(deps)]
    if any(pkg.get("flow", '') == "default_cpp" for pkg in pkgs):
        from pygears_tools import default_cpp
        resp.insert(0, [default_cpp.dependencies[os_name()]])

    return resp


def install_deps(pkgs):
    print("Installing dependencies")
    deps = list_pkg_deps(pkgs)

    for d in deps:
        cmd = "sudo apt install -y " + ' '.join(d)
        print(cmd)

        if not pkgs[0]['dry_run']:
            subprocess.run(cmd, shell=True, check=True)


def configure(pkg):
    if not pkg['dry_run']:
        os.chdir(pkg["src_root_path"])

    if "configure" in pkg:
        pkg["logger"].info("Running auto configure. Output redirected to configure.log .")
        if pkg['path']:
            cmd = f"./configure --prefix={pkg['path']} {pkg['configure']} > ../configure.log 2>&1"
        else:
            cmd = f"./configure {pkg['configure']} > ../configure.log 2>&1"

        pkg["logger"].info(f"Command: {cmd}.")

        if not pkg['dry_run']:
            subprocess.check_output(cmd, shell=True)

    if not pkg['dry_run']:
        os.chdir(pkg["install_path"])


def cmake(pkg):
    if not pkg['dry_run']:
        os.chdir(pkg["src_root_path"])
        if os.path.exists("build"):
            shutil.rmtree("build")

        os.mkdir("build")
        os.chdir("build")

    if "cmake_cfg" not in pkg:
        pkg["cmake_cfg"] = ""

    pkg["logger"].info("Running CMake. Output redirected to cmake.log .")

    if pkg['path']:
        cmd = (f"cmake -DCMAKE_INSTALL_PREFIX:PATH={pkg['path']} {pkg['cmake_cfg']}"
               " .. > ../../cmake.log 2>&1")
    else:
        cmd = (f"cmake {pkg['cmake_cfg']} .. > ../../cmake.log 2>&1")

    pkg["logger"].info(f"Command: {cmd}.")

    if not pkg['dry_run']:
        subprocess.check_output(cmd, shell=True)

    pkg["src_root_path"] = os.getcwd()

    if not pkg['dry_run']:
        os.chdir(pkg["src_root_path"])


def make(pkg):
    if not pkg['dry_run']:
        os.chdir(pkg["src_root_path"])

    pkg["logger"].info("Running make. Output redirected to make.log .")
    cmd = f"make -j4 > ../make.log 2>&1"
    pkg["logger"].info(f"Command: {cmd}.")

    if not pkg['dry_run']:
        try:
            subprocess.check_output(cmd, shell=True)
        except subprocess.CalledProcessError:
            pkg["logger"].error("Make finished with error, please check the log.")

    pkg["logger"].info("Running make install. Output redirected to make_install.log .")
    if pkg['path']:
        cmd = "make install > ../make_install.log 2>&1"
    else:
        cmd = "sudo make install > ../make_install.log 2>&1"

    pkg["logger"].info(f"Command: {cmd}.")

    if not pkg['dry_run']:
        try:
            subprocess.check_output(cmd, shell=True)
        except subprocess.CalledProcessError:
            pkg["logger"].error("Make install finished with error, please check the log.")

    if not pkg['dry_run']:
        os.chdir(pkg["src_root_path"])


def clone_git(pkg):
    clone_dir = pkg["src_root_path"]
    if not os.path.exists(clone_dir):
        pkg["logger"].info("Cloning git repo. Output redirected to git_clone.log .")
        cmd = f"git clone {pkg['git']} {clone_dir} > git_clone.log 2>&1"
        pkg["logger"].info(f"Command: {cmd}.")

        if not pkg['dry_run']:
            subprocess.check_output(cmd, shell=True)
    else:
        pkg["logger"].info("Source git repo already available and will be reused.")


def shell_source(script):
    """Sometime you want to emulate the action of "source" in bash,
    settings some environment variables. Here is a way to do it."""

    pipe = subprocess.Popen(". %s; env" % script,
                            stdout=subprocess.PIPE,
                            shell=True,
                            executable="/bin/bash" if os_name() == 'ubuntu' else None)
    output = pipe.communicate()[0].decode()
    env = {}
    for line in output.splitlines():
        try:
            keyval = line.split("=", 1)
            env[keyval[0]] = keyval[1]
        except:
            pass

    os.environ.update(env)


def set_env(pkg):
    if "env" not in pkg:
        return True

    pkg["logger"].info("Exporting the environment variables.")
    if not pkg['dry_run']:
        with open(pkg["tools_sh_path"], "a") as text_file:
            print("", file=text_file)
            print("# Environment for {}".format(pkg["name"]), file=text_file)
            for cmd in pkg["env"]:
                print(cmd.format(**pkg), file=text_file)

        shell_source(pkg["tools_sh_path"])


def custom_run(pkg, cmd_set):
    if cmd_set not in pkg:
        return True

    pkg["logger"].info("Running custom package commands. Output redirected to custom_cmd.log .")

    log_file = os.path.join(pkg["install_path"], "custom_cmd.log")
    for cmd in pkg[cmd_set]:
        cmd = cmd.format(**pkg)
        pkg["logger"].info('Command: "{}"'.format(cmd))

        if not pkg['dry_run']:
            subprocess.check_output("{} > {} 2>&1".format(cmd, log_file), shell=True)

def pip_install(pkg, pyenv):
    if pyenv:
        cmd = f'pip3 install -U {pkg["pip"]}'
    else:
        cmd = f'sudo pip3 install -U {pkg["pip"]}'

    log_file = os.path.join(pkg["install_path"], "pip.log")
    pkg["logger"].info('Command: "{}"'.format(cmd))
    if not pkg['dry_run']:
        subprocess.check_output(f"{cmd} > {log_file} 2>&1", shell=True)
