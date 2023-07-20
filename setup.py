from setuptools import setup

setup(
    name="spikexplore",
    version="0.1.0",
    description="Graph exploration using inhomogeneous filtered diffusion",
    url="https://github.com/epfl-lts2/spikexplore",
    author="Nicolas Aspert, Benjamin Ricaud",
    author_email="nicolas.aspert@epfl.ch, benjamin.ricaud@epfl.ch",
    license="Apache license",
    packages=["spikexplore", "spikexplore.backends"],
    scripts=[],
    install_requires=["pandas", "numpy", "networkx", "tqdm", "wikipedia-api", "python-louvain"],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.8",
    ],
)
