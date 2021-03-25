pipreqs --savepath requirements.tmp --force openbci_stream
rm requirements.txt
sed '/kafka==/d' requirements.tmp >> requirements.txt
rm requirements.tmp
cat requirements.txt