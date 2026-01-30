from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="schedulingArena",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A unified experimental platform for wireless scheduling algorithms",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/schedulingArena",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.7",
    install_requires=[
        "numpy>=1.19.0",
        "gym>=0.18.0",
    ],
    entry_points={
        "console_scripts": [
            "scheduling-arena=schedulingArena.cli:main",
        ],
    },
)
