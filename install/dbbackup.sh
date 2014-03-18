#!/bin/bash
echo 'Connect to Database'
pg_dump -U infsek -h localhost -W > dbbackup
date=$(date +%Y%m%d)
echo 'encrypting file'
openssl aes-256-cbc -in dbbackup -out want2hackdb$date.enc
echo 'deleting plaintext'
rm dbbackup
echo 'openssl aes-256-cbc -d -in want2hackdb'$date'.enc dbbackup to decrypt'
echo 'now copy it to your computer'