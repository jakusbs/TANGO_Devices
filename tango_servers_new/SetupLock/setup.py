from setuptools import setup

setup(
    name='tangods-SetupLock',
    version='2.0.0',
    py_modules=['SetupLock', 'lease_store'],
    entry_points={'console_scripts': ['SetupLock = SetupLock:main']},
)
