from setuptools import setup, find_packages
import mdtpy

setup( 
    name = 'mdtpy',
    version = mdtpy.__version__,
    description = 'MDT client for Python',
    author = 'Kang-Woo Lee',
    author_email = 'kwlee@etri.re.kr',
    url = 'https://github.com/kwlee0220/mdtpy',
	entry_points={ },
    install_requires = [
        'requests',
        'requests-toolbelt',
        'dataclasses-json',
    ],
    packages = find_packages(),
    package_dir={'conf': 'conf'},
    package_data = {
        'conf': ['logger.yaml']
    },
    python_requires = '>=3.10',
    zip_safe = False
)
