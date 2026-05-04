# Build #
python3 build.py -DVOLE_PSI_ENABLE_OPENSSL=true -DVOLE_PSI_ENABLE_BOOST=true

# Generate inputs #
python3 generate_psi_inputs.py -n 20 -i 1000

# PSI with TLS #
./out/build/linux/frontend/frontend -r 1 \
  -in dune_unique.csv \
  -csv \
  -tls \
  -CA certs/ca.cert.pem \
  -pk certs/receiver.cert.pem \
  -sk certs/receiver.key.pem \
  -v

./out/build/linux/frontend/frontend -r 0 \
  -in lotr_unique.csv \
  -csv \
  -tls \
  -CA certs/ca.cert.pem \
  -pk certs/sender.cert.pem \
  -sk certs/sender.key.pem \
  -v

# PSI Vanila #
./out/build/linux/frontend/frontend -r 1 -server 1 \
  -in receiver.csv \
  -out receiver.csv.out \
  -v

./out/build/linux/frontend/frontend -r 0 \
  -in sender.csv \
  -out sender.csv.out \
  -v
