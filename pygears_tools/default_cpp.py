from .utils import configure, make

dependencies = {
    'ubuntu': 'build-essential',
    'opensuse': '-t pattern devel_C_C++'
}


def flow(pkg):
    configure(pkg)
    make(pkg)

    return True
