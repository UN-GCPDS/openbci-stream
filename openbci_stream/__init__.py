import os
import logging

version = open(os.path.join(os.path.dirname(__file__),
                            '_version.txt'), 'r').read().strip()

if ('a' in version) or ('b' in version):
    logging.warning(f'OpenBCI-Stream v{version}')
    logging.warning(f'This version could be unstable.')
else:
    logging.info(f'OpenBCI-Stream v{version}')

