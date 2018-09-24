from .utils import configure, make

dependencies = 'build-essential'


def flow(pkg):
    configure(pkg)
    make(pkg)

    return True
