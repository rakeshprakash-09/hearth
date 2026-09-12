"""Generates an SVG QR code for a URL -- makes the CA-trust landing page
scannable from a phone camera. Not part of the running app; a one-time
deploy-time tool, run again only if the URL changes.

Run with: backend/.venv/bin/python deploy/generate_ca_qr.py <url> <output.svg>
"""

import sys

import qrcode
from qrcode.image.svg import SvgPathImage


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: generate_ca_qr.py <url> <output.svg>")
        raise SystemExit(1)
    url, out_path = sys.argv[1], sys.argv[2]
    qrcode.make(url, image_factory=SvgPathImage).save(out_path)
    print(f"QR code for {url} written to {out_path}")


if __name__ == "__main__":
    main()
