rm requirements.txt
pipreqs --savepath requirements.txt --force openbci_stream
sed -i '/kafka==/d' requirements.txt
sed -i '/pyEDFlib==/d' requirements.txt
sed -i 's/==.*//' requirements.txt
python -c "[print(f'\'{line[:-1]}\',') for line in open('requirements.txt').readlines()]"