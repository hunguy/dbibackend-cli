from setuptools import setup, find_packages

setup(
    name="dbibackend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pyusb>=1.2.1",
        "tqdm>=4.65.0",
    ],
    entry_points={
        'console_scripts': [
            'dbibackend=dbibackend.cli:main',
        ],
    },
    author="Henry",
    description="Nintendo Switch File Transfer CLI Tool",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    keywords="nintendo switch usb transfer dbi",
    python_requires=">=3.8",
)
