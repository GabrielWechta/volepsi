# create directory
CERT_DIR=certs
mkdir -p "$CERT_DIR"

# ===== CA =====
openssl genrsa -out "$CERT_DIR/ca.key.pem" 2048

openssl req -x509 -new -nodes \
  -key "$CERT_DIR/ca.key.pem" \
  -sha256 -days 3650 \
  -out "$CERT_DIR/ca.cert.pem" \
  -subj "/C=PL/ST=Test/L=Test/O=PSI-CA/CN=PSI-CA"

# ===== RECEIVER (CLIENT) =====
openssl genrsa -out "$CERT_DIR/receiver.key.pem" 2048

openssl req -new \
  -key "$CERT_DIR/receiver.key.pem" \
  -out "$CERT_DIR/receiver.csr.pem" \
  -subj "/C=PL/ST=Test/L=Test/O=PSI/CN=localhost"

openssl x509 -req \
  -in "$CERT_DIR/receiver.csr.pem" \
  -CA "$CERT_DIR/ca.cert.pem" \
  -CAkey "$CERT_DIR/ca.key.pem" \
  -CAcreateserial \
  -out "$CERT_DIR/receiver.cert.pem" \
  -days 365 -sha256

# ===== SENDER (SERVER) =====
openssl genrsa -out "$CERT_DIR/sender.key.pem" 2048

openssl req -new \
  -key "$CERT_DIR/sender.key.pem" \
  -out "$CERT_DIR/sender.csr.pem" \
  -subj "/C=PL/ST=Test/L=Test/O=PSI/CN=sender"

openssl x509 -req \
  -in "$CERT_DIR/sender.csr.pem" \
  -CA "$CERT_DIR/ca.cert.pem" \
  -CAkey "$CERT_DIR/ca.key.pem" \
  -CAcreateserial \
  -out "$CERT_DIR/sender.cert.pem" \
  -days 365 -sha256

# ===== CLEANUP =====
rm "$CERT_DIR"/*.csr.pem
