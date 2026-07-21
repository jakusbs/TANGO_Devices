from setuptools import setup, find_packages

setup(
    name='tangods-RTV40',
    version='1.0.0',
    description='Kentech RTV40/RTV30 pulse generator Tango device server',
    packages=['RTV40'],
    entry_points={
        'console_scripts': [
            'RTV40 = RTV40:main',
        ],
    },
    install_requires=[
        'pytango',
        'pyserial',
    ],
)
