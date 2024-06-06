import datetime
from os import PathLike
from pathlib import Path
from hypercorn.config import Config
from hypercorn.asyncio import serve
import asyncio
from fused_local.app import app


# TODO: we can't easily serve HTTP/2 over localhost, because it requires HTTPS.
# The browser won't trust our self-signed certificates, which isn't great UX.
# See https://freedium.cfd/https://levelup.gitconnected.com/deploy-fastapi-with-hypercorn-http-2-asgi-8cfc304e9e7a


def generate_certs(key_file: PathLike, cert_file: PathLike):
    # copied from https://cryptography.io/en/latest/x509/tutorial/#creating-a-self-signed-certificate
    # modified to remove passphrase and extend expiry
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes

    # Generate our key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    # Write our key to disk for safe keeping

    with open(key_file, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Various details about who we are. For a self-signed certificate the
    # subject and issuer are always the same.
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "My Company"),
            x509.NameAttribute(NameOID.COMMON_NAME, "mysite.com"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            # Set the certificate to never expire
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=36525)
        )
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
            # Sign our certificate with our private key
        )
        .sign(key, hashes.SHA256())
    )
    # Write our certificate out to disk.
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


# TODO base on path of file we're serving?
# better yet, store in the cache?
key_file = Path.cwd() / "key.pem"
cert_file = Path.cwd() / "cert.pem"

if __name__ == "__main__":
    if not key_file.exists() or not cert_file.exists():
        print(f"Generating self-signed certificate to {key_file} and {cert_file}")
        generate_certs(key_file, cert_file)

    config = Config()
    config.bind = ["localhost:8000"]
    config.accesslog = "-"
    config.errorlog = "-"
    config.keyfile = str(key_file)
    config.certfile = str(cert_file)

    asyncio.run(serve(app, config))  # type: ignore (unclear why)
