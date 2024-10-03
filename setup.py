from setuptools import setup, find_packages

setup(
    name="qsm-ci",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'qsm-ci=qsm_ci.main:main',
        ],
    },
    install_requires=[
        'docker',
        'scikit-learn',
        'scikit-image',
        'scipy',
        'nibabel'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)

