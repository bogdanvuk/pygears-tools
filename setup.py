from setuptools import setup, find_packages


setup(
    name='pygears-tools',
    version='0.1',
    description='Helper scripts for installing pygears related tools',

    # The project's main homepage.
    url='https://github.com/bogdanvuk/pygears-tools',

    # Author details
    author='Bogdan Vukobratovic',
    author_email='bogdan.vukobratovic@gmail.com',

    # Choose your license
    license='MIT',

    packages=find_packages(exclude=['examples*', 'docs']),
    package_data={'': ['*.json', '.spacemacs']},
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'pygears-tools-install = pygears_tools.install:main'
        ],
    }
)
