from setuptools import setup

setup(
    name="clipper",
    version="0.1dev0",
    author="Albertas Agejevas",
    author_email="albertas.agejevas@gmail.com",
    description="Automatically cut videos out of footage",
    license="MIT",
    package_dir={'': 'src'},
    packages=[''],
    install_requires=[
        'moviepy',
        'pytube',
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
    ],
    entry_points={
        'console_scripts': ['clipper = clipper:main']
    },
)
