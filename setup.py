from setuptools import find_packages, setup


setup(
    name='ootr-randobot',
    description='racetime.gg bot for generating OoTR seeds.',
    license='MIT',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    url='https://racetime.gg/ootr',
    project_urls={
        'Source': 'https://github.com/deains/ootr-randobot',
    },
    version='1.0.0',
    install_requires=[
        'racetime_bot>=1.5.0,<2.0',
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'randobot=randobot:main',
        ],
    },
)
