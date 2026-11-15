"""Container entrypoint: make a local CA and a server certificate once, then serve over HTTPS.

The CA certificate is written to ``$SIM_CERT_DIR/ca.pem`` (a Docker volume) so Future Mirror can
trust the simulator through ``FM_D365_CA_BUNDLE`` without turning off TLS verification.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import os
from pathlib import Path

import uvicorn

CERT_DIR = Path(os.environ.get("SIM_CERT_DIR", "/certs"))
HOSTS = ["d365fo-sim", "localhost"]


def ensure_certificates(cert_dir: Path = CERT_DIR) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    cert_dir.mkdir(parents=True, exist_ok=True)
    ca_pem, crt, key = cert_dir / "ca.pem", cert_dir / "server.pem", cert_dir / "server.key"
    if ca_pem.exists() and crt.exists() and key.exists():
        return crt, key
    now = dt.datetime.now(dt.UTC)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Future Mirror D365 simulator local CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5))
          .not_valid_after(now + dt.timedelta(days=3650))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                       data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                       crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
          .sign(ca_key, hashes.SHA256()))
    srv_key = ec.generate_private_key(ec.SECP256R1())
    sans = [x509.DNSName(h) for h in HOSTS] + [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    srv = (x509.CertificateBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOSTS[0])])).issuer_name(ca_name)
           .public_key(srv_key.public_key()).serial_number(x509.random_serial_number())
           .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=825))
           .add_extension(x509.SubjectAlternativeName(sans), critical=False)
           .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
           .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
           .add_extension(x509.SubjectKeyIdentifier.from_public_key(srv_key.public_key()), critical=False)
           .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
           .sign(ca_key, hashes.SHA256()))
    key.write_bytes(srv_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    key.chmod(0o600)
    crt.write_bytes(srv.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM))
    ca_pem.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    ca_pem.chmod(0o644)  # read by the Future Mirror backend (another user) through the shared volume
    return crt, key


def main() -> None:
    crt, key = ensure_certificates()
    uvicorn.run("d365fo_sim.server:create_app", factory=True, host="0.0.0.0", port=int(os.environ.get("SIM_PORT", 8443)),
                ssl_certfile=str(crt), ssl_keyfile=str(key), log_level="info")


if __name__ == "__main__":
    main()
