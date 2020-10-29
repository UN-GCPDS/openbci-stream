"""
================
Autokill process
================

Some scripts with Threading or Subprocessing calls could ends without terminate
all the process, this script make sure you finish the current process and the
previous process generated too.
"""

import os
import logging
import atexit
import signal
from pathlib import Path


# ----------------------------------------------------------------------
def autokill_process(name: str = '') -> None:
    """Make sure you finish the current process.

    In addition to kill the current process, it will looks for the previous
    process and kill them before the start.

    Parameters
    ----------
    name
        Name used for the PID file.
    """

    pid = os.getpid()
    logging.info(f"Running with PID: {pid}")

    PID_FILE = os.path.join(Path.home(), f".openbci.{name}.pid")
    logging.info(f"PID file created in: {PID_FILE}")

    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as file:
            oldpid = file.read()
            if oldpid.isdigit():
                oldpid = int(oldpid)
                if oldpid != pid:
                    try:
                        os.kill(oldpid, signal.SIGKILL)
                    except:
                        pass

    with open(PID_FILE, 'w') as file:
        file.write(str(pid))

    # ----------------------------------------------------------------------
    @atexit.register
    def _() -> None:
        logging.info(f"Killing PID: {pid}")
        try:
            os.kill(-pid, signal.SIGKILL)
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except:
            pass
