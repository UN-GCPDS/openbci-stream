import os
import logging

version = open(os.path.join(os.path.dirname(__file__),
                            '_version.txt'), 'r').read().strip()

if ('beta' in version) or ('alpha' in version):
    logging.warning(f'OpenBCI - v{version}')
    logging.warning(f'This version could be unstable.')
else:
    logging.info(f'OpenBCI - v{version}')

