import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
   README = readme.read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))
version_str = open(os.path.join(
   'openbci_stream', '_version.txt'), 'r').read().strip()

setup(
    name='openbci-stream',
    version=version_str,
    packages=['openbci_stream', 'openbci_stream.acquisition',
              'openbci_stream.daemons', 'openbci_stream.utils'],

    author='Yeison Cardona',
    author_email='yencardonaal@unal.edu.co',
    maintainer='Yeison Cardona',
    maintainer_email='yencardonaal@unal.edu.co',

    download_url='https://github.com/UN-GCPDS/openbci_stream',

    install_requires=['pyserial',
                      'scipy',
                      'numpy',
                      'psutil',
                      'mne',
                      'requests',
                      'colorama',
                      'rawutil',
                      'plumbum',
                      'pyedflib',

                      'crc32c',
                      'kafka-python',
                      'rpyc',
                      'tables',
                      'systemd_service',
                      ],

    extras_require={
        'utils': ['nmap',
                  'systemd_service',
                  'netifaces',
                  'python-nmap',
                  ],
    },

    scripts=[
       "cmd/openbci_cli",
       "cmd/stream_rpyc",
       "cmd/stream_eeg",
       "cmd/stream_configure_kafka.sh",
       "cmd/stream_access_point.sh",
    ],

    include_package_data=True,
    license='BSD-2-Clause',
    description="High level Python module for EEG/EMG/ECG acquisition and distributed streaming for OpenBCI Cyton board.",

    long_description=README,
    long_description_content_type='text/markdown',

    python_requires='>=3.8',

    classifiers=[
       'Development Status :: 4 - Beta',
       'Intended Audience :: Developers',
       'Intended Audience :: Education',
       'Intended Audience :: Healthcare Industry',
       'Intended Audience :: Science/Research',
       'License :: OSI Approved :: BSD License',
       'Programming Language :: Python :: 3.8',
       'Topic :: Scientific/Engineering',
       'Topic :: Scientific/Engineering :: Human Machine Interfaces',
       'Topic :: Scientific/Engineering :: Medical Science Apps.',
       'Topic :: Software Development :: Embedded Systems',
       'Topic :: Software Development :: Libraries',
       'Topic :: Software Development :: Libraries :: Application Frameworks',
       'Topic :: Software Development :: Libraries :: Python Modules',
       'Topic :: System :: Hardware :: Hardware Drivers',
    ],

)
