#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ColorOS PcTool backup decryptor.

Container layout (little details in docs/FORMAT.md):

    +--------+------------------+--------------------+--------------------------+
    | "5AA5" | 8-digit ASCII    | plaintext JSON     | encrypted payload        |
    | 4 B    | decimal = J len  | header (J bytes)   | (len == plaintext len)   |
    +--------+------------------+--------------------+--------------------------+

Payload cipher : AES-128-ECB, no IV.
Key            : sha256(password).hexdigest()[:16]  (ASCII bytes)
Header "md5"   : actually SHA-256 of the plaintext (integrity check).
Trailing tail  : only floor(len/16)*16 bytes are encrypted; the final
                 len % 16 bytes are stored in cleartext.

Usage:
    python3 decrypt_backup.py --src /path/to/backup --out ./restored --pw '<password>'

Backend: uses pycryptodome if available, otherwise falls back to the `openssl` CLI.
"""
import os
import sys
import json
import hashlib
import argparse
import subprocess

try:
    from Crypto.Cipher import AES          # pycryptodome
    _HAVE_PYC = True
except Exception:
    _HAVE_PYC = False


def derive_key(password: str) -> bytes:
    return hashlib.sha256(password.encode()).hexdigest()[:16].encode()


def _aes_ecb_decrypt(key: bytes, data: bytes) -> bytes:
    if _HAVE_PYC:
        return AES.new(key, AES.MODE_ECB).decrypt(data)
    r = subprocess.run(['openssl', 'enc', '-d', '-aes-128-ecb', '-K', key.hex(), '-nopad'],
                       input=data, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('openssl failed: ' + r.stderr.decode('latin1'))
    return r.stdout


def decrypt_payload(cipher: bytes, key: bytes) -> bytes:
    full = len(cipher) - len(cipher) % 16
    if full == 0:
        return cipher
    return _aes_ecb_decrypt(key, cipher[:full]) + cipher[full:]


def safe_relpath(meta: dict) -> str:
    p = (meta.get('path') or meta.get('originPath') or '').replace('\\', '/')
    name = meta.get('name') or meta.get('uuid') or 'file'
    for pref in ('/storage/emulated/0/', '/sdcard/', '/storage/emulated/'):
        if p.startswith(pref):
            p = p[len(pref):]
            break
    if not p:
        p = name
    if name and not p.endswith(name):
        p = p.rstrip('/') + '/' + name
    return p.lstrip('/') or name


def main() -> int:
    ap = argparse.ArgumentParser(description='Decrypt ColorOS PcTool (5AA5) backups.')
    ap.add_argument('--src', required=True, help='backup root directory')
    ap.add_argument('--out', required=True, help='output root directory')
    ap.add_argument('--pw', required=True, help='backup password')
    ap.add_argument('--limit', type=int, default=0, help='only process first N files (debug)')
    args = ap.parse_args()

    key = derive_key(args.pw)
    print('[i] backend : %s' % ('pycryptodome' if _HAVE_PYC else 'openssl CLI'))
    print('[i] key     : %s' % key.decode())

    total = ok = fail = skipped = 0
    errors = []
    stop = False
    for root, _dirs, files in os.walk(args.src):
        if stop:
            break
        for fn in files:
            if args.limit and total >= args.limit:
                stop = True
                break
            path = os.path.join(root, fn)
            try:
                with open(path, 'rb') as f:
                    if f.read(4) != b'5AA5':
                        skipped += 1
                        continue
                    jlen = int(f.read(8))
                    meta = json.loads(f.read(jlen))
                    payload = f.read()
                total += 1

                pt = decrypt_payload(payload, key)
                good = hashlib.sha256(pt).hexdigest() == meta.get('md5', '')

                out_rel = os.path.join(os.path.basename(os.path.normpath(args.src)),
                                       safe_relpath(meta))
                dst = os.path.join(args.out, out_rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    b, e = os.path.splitext(dst)
                    dst = '%s_%s%s' % (b, meta.get('uuid', '')[:8], e)
                with open(dst, 'wb') as o:
                    o.write(pt)

                if good:
                    ok += 1
                else:
                    fail += 1
                    errors.append((path, 'hash mismatch'))
                if total % 50 == 0:
                    print('    ...%d (ok=%d fail=%d)' % (total, ok, fail))
            except Exception as e:                       # noqa: BLE001
                fail += 1
                errors.append((path, str(e)))

    print('==== done: containers=%d ok=%d fail=%d skipped=%d' % (total, ok, fail, skipped))
    for p, e in errors[:50]:
        print('    ERR', p, e)
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
