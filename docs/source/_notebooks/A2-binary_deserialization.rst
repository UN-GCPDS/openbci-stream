Appendix 2 - Binary deserialization
===================================

This appendix describes the process of convert validated RAW data into
EEG data packages, according to the `official
guide <https://docs.openbci.com/docs/02Cyton/CytonDataFormat>`__.

.. code:: ipython3

    from matplotlib import pyplot as plt
    import numpy as np

.. code:: ipython3

    data = np.loadtxt('raw.validated', delimiter=',')
    # data = data.reshape(-1, 33)





.. parsed-literal::

    [<matplotlib.lines.Line2D at 0x7f4e1d5a7a90>]




.. image:: A2-binary_deserialization_files/A2-binary_deserialization_3_1.png

