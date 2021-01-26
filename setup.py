from setuptools import setup

import versioneer


setup(
    name="chimedb.dataflag",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages=["chimedb.dataflag"],
    zip_safe=False,
    python_requires=">=3.7",
    install_requires=[
        "chimedb @ git+https://github.com/chime-experiment/chimedb.git",
        "peewee >= 3.10",
        "numpy",
        "Click",
        "ansimarkup",
        "tabulate",
        "PyYAML",
        "arrow",
    ],
    extras_require={
        "vote": ["ch_util @ git+https://github.com/chime-experiment/ch_util.git"],
    },
    entry_points="""
        [console_scripts]
        cdf=chimedb.dataflag.client:cli
    """,
    author="CHIME collaboration",
    author_email="richard@phas.ubc.ca",
    description="CHIME data flag tools",
    license="MIT",
    url="https://github.org/chime-experiment/chimedb_dataflag",
)
