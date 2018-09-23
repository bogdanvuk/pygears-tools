from setuptools import setup


setup(
    name='pygears',
    version='0.1',
    description='Framework for functional hardware design approach',

    # The project's main homepage.
    url='https://github.com/bogdanvuk/pygears-tools',
    # download_url = '',

    # Author details
    author='Bogdan Vukobratovic',
    author_email='bogdan.vukobratovic@gmail.com',

    # Choose your license
    license='MIT',

    package_data={'': ['*.json']},
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'pygears_tools_install = pygears_tools.install:main'
        ],
    }
)
