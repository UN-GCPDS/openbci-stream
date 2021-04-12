pipreqs --savepath requirements.tmp --force openbci_stream
rm requirements.txt
sed '/kafka==/d' requirements.tmp >> requirements.txt
rm requirements.tmp
sed -i 's/==/>=/' requirements.txt
cat requirements.txt
