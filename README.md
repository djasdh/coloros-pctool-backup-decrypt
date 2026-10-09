# ColorOS PcTool Backup Decrypt

[中文](README.zh-CN.md) | **English**

Unofficial decryptor and format notes for **OPPO / OnePlus / Realme ColorOS "备份与恢复"
PC tool (PcTool) backups** — the `5AA5` containers written by the desktop assistant
`coloros-assist` (together with its on-device plugin).

## Format

```
+--------+------------------+--------------------+--------------------------+
| "5AA5" | 8-digit ASCII    | plaintext JSON     | encrypted payload        |
| 4 B    | decimal = J len  | header (J bytes)   | (len == plaintext len)   |
+--------+------------------+--------------------+--------------------------+
```

* **Cipher:** `AES-128-ECB`, **no IV**.
* **Key:** the first 16 characters of the hex SHA-256 of the backup password, taken as
  **ASCII bytes**:
  ```python
  key = hashlib.sha256(password.encode()).hexdigest()[:16].encode()
  # "123456" -> b"8d969eef6ecad3c2"
  ```
* **Integrity:** the header field `md5` is **not** MD5 — it is the **SHA-256 of the plaintext**,
  so every decrypted file can be verified.

JSON header fields: `uuid, cmdId, createTime, needAck, sendTimes, fileType, length,
md5 (sha256), name, path, userId, lastModifyTime, isBaseApk, zipInfo, originPath …`

## Quick start

```bash
python3 decrypt_backup.py --src /path/to/backup --out ./restored --pw '<password>'
```

Minimal single-file decrypt:

```python
import hashlib, json
from Crypto.Cipher import AES        # pip install pycryptodome

def decrypt_container(path, password):
    with open(path, 'rb') as f:
        assert f.read(4) == b'5AA5'
        jlen = int(f.read(8))
        meta = json.loads(f.read(jlen))
        payload = f.read()
    key = hashlib.sha256(password.encode()).hexdigest()[:16].encode()
    full = len(payload) - len(payload) % 16
    pt = AES.new(key, AES.MODE_ECB).decrypt(payload[:full]) + payload[full:] if full else payload
    assert hashlib.sha256(pt).hexdigest() == meta['md5'], 'wrong password or corrupt file'
    return meta, pt
```

Tested on photos (JPG/PNG/HEIC/DNG), video (MP4), audio (FLAC), documents (PDF/ZIP/…),
SMS (`sms.vmsg`, `bmx_messages.xml`, `*.pdu`), call log (`callrecord_backup.xml`),
calendar (`.vcs`) and gallery metadata (JSON).

## How it works (reverse-engineering notes)

* `SocketConnect.dll` → `DataCenterManager` → `FileTransfer::Encode` / `Decode` read/write the
  container: `"5AA5"` + `snprintf("%08d", len)` + JSON + payload.
* Both call `Utils.dll` → `AesImpl::aesEncrypt/aesDecrypt(buf, key, mode, iv)`. `AesMode` index
  `0` resolves (via a static cipher map) to the OpenSSL `EVP_CIPHER` with `nid=418`, `block=16`,
  `key_len=16`, `iv_len=0` → **AES-128-ECB**.
* The key is a `FileTransfer` member set by
  `DataCenterManager::SetBackupPasswordAndTip(name, password, tip)`, trimmed/padded to 16 bytes.
  The password reaches native code already `sha256`-hashed by the Electron JS:
  `setBackupPassword(pw) → l = sha256(pw) → De.SetBackupPasswordAndTip(name, l, tip)`.
* `EVP_EncryptUpdate` is used without `EVP_EncryptFinal`, so the non-block-aligned tail is left
  untransformed → stored in cleartext.

Reproduce the analysis with Ghidra headless (`tools/DecompAll.java`). See `docs/`.

## Security note

The backup encryption is **effectively unkeyed**: no salt, no KDF iterations, no device
binding — the key is a pure function of the password. Hence identical plaintext ⇒ identical
ciphertext across backups, and the key space equals the password space (a 6-digit PIN is
brute-forced in seconds, one block per attempt). AES-ECB additionally leaks intra-block
structure. Treat these backups as **not encrypted**.

## Disclaimer

* For recovering **your own** backups only.
* Not affiliated with OPPO, OnePlus, Realme or ColorOS.
* No personal data, keys or sample backups are included.
* Published for research/educational purposes; use only on data you are authorised to access.

## License

Apache-2.0.

## Credits

* [ChidcGithub/Dog3Decryption](https://github.com/ChidcGithub/Dog3Decryption) — related technique (ColorOS logs).
* [bkerler/oppo_decrypt](https://github.com/bkerler/oppo_decrypt) — OPPO OZIP firmware tooling.
