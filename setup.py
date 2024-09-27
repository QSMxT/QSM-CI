from setuptools import setup, find_packages

setup(
    name="qsm-ci",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'qsm-ci=qsm_ci.run:main',
        ],
    },
    install_requires=[
        'docker'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
