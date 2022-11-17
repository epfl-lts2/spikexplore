from setuptools import setup

setup(
    name="spikexplore",
    version="0.0.12",
    description="Graph exploration using inhomogeneous filtered diffusion",
    url="https://github.com/epfl-lts2/spikexplore",
    author="Nicolas Aspert, Benjamin Ricaud",
    author_email="nicolas.aspert@epfl.ch, benjamin.ricaud@epfl.ch",
    license="Apache license",
    packages=["spikexplore", "spikexplore.backends"],
    scripts=[],
    install_requires=["pandas", "numpy", "networkx", "tqdm", "twython", "wikipedia-api", "python-louvain", "TwitterAPI"],
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.6",
    ],
)
