import os
import logging

version = open(os.path.join(os.path.dirname(__file__),
                            '_version.txt'), 'r').read().strip()

logger = logging.getLogger()
logger.setLevel(logging.WARNING)
logging.root.name = "OpenBCI-Stream"

if ('a' in version) or ('b' in version):
    logging.warning(f'v{version}')
    logging.warning(f'This version could be unstable.')
else:
    logging.info(f'v{version}')


