from openbci_stream.utils import HDF5Reader

filename = 'record-09_11_21-09_46_54.h5'

with HDF5Reader(filename) as reader:
    print(reader, end='\n\n')
    duration = reader.eeg.shape[1] / reader.header['sample_rate']
    print(f'Duration: {duration/60} minutes')

    # # Datos crudos
    # e = reader.eeg  # np.ndarray

    # # Timestamps
    # t = reader.timestamp  # np.ndarray
    # ta = reader.aux_timestamp  # np.ndarray

    # # reader.array_timestamp

    # a = reader.aux

    # ma = reader.markers

    # an = reader.annotations

    # c = reader.classes

    # edf = reader.to_edf('test222.edf')

    # epochs = reader.get_epochs(3, tmin=0)

    # reader.to_edf(filename.replace('.h5', '.edf'))

    reader.to_npy(filename.replace('.h5', ''), tmin=-0.2, tmax=2)



