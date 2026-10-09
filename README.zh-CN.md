# ColorOS PcTool 备份解密

**中文** | [English](README.md)

针对 **OPPO / 一加 / realme 的 ColorOS「备份与恢复」电脑端（PcTool）备份** 的非官方
解密工具与格式说明。这类备份由桌面助手 `coloros-assist`（配合手机端插件）写成
`5AA5` 容器。

## 格式

```
+--------+------------------+--------------------+--------------------------+
| "5AA5" | 8 位 ASCII 十进制 | 明文 JSON 头        | 加密载荷                  |
| 4 字节 | = JSON 头长度     | (J 字节)            | (长度 == 明文长度)        |
+--------+------------------+--------------------+--------------------------+
```

* **算法**：`AES-128-ECB`，**无 IV**。
* **密钥**：用户备份密码的 SHA-256 十六进制串的**前 16 个字符**，取其 **ASCII 字节**：
  ```python
  key = hashlib.sha256(password.encode()).hexdigest()[:16].encode()
  # 例：密码 "123456" -> b"8d969eef6ecad3c2"
  ```
* **校验**：JSON 头里的 `md5` 字段**不是 MD5**，而是**明文的 SHA-256**，可用来逐文件校验。

JSON 头字段：`uuid, cmdId, createTime, needAck, sendTimes, fileType, length, md5(实为 sha256),
name, path, userId, lastModifyTime, isBaseApk, zipInfo, originPath …`

## 快速开始

```bash
python3 decrypt_backup.py --src /备份目录 --out ./restored --pw '<你的备份密码>'
```

单文件解密：

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
    assert hashlib.sha256(pt).hexdigest() == meta['md5'], '密码错误或文件损坏'
    return meta, pt
```

已实测覆盖各类数据：照片（JPG/PNG/HEIC/DNG）、视频（MP4）、音频（FLAC）、文档
（PDF/ZIP/…）、短信（`sms.vmsg` / `bmx_messages.xml` / `*.pdu`）、通话
（`callrecord_backup.xml`）、日历（`.vcs`）、相册元数据（JSON）。

## 原理 / 逆向记录

容器封装与加密都在桌面助手的原生模块里：

* `SocketConnect.dll` → `DataCenterManager` → `FileTransfer::Encode` / `FileTransfer::Decode`
  负责读写 `5AA5` 容器：`"5AA5"`(4B) + `snprintf("%08d", len)` + JSON + 载荷。
* 两者都调用 `Utils.dll` 的 `AesImpl::aesEncrypt/aesDecrypt(buf, key, mode, iv)`。其中
  `AesMode` 索引 `0` 经静态模式表映射到 OpenSSL `EVP_CIPHER`：`nid=418`, `block=16`,
  `key_len=16`, `iv_len=0` → 即 **AES-128-ECB**。
* 密钥是 `FileTransfer` 对象的一个成员，由
  `DataCenterManager::SetBackupPasswordAndTip(name, password, tip)` 写入，并被截断/补齐到
  16 字节。密码到达原生层前已被前端 JS 做过 `sha256`：
  `setBackupPassword(pw) → l = sha256(pw) → De.SetBackupPasswordAndTip(name, l, tip)`。
* `EVP_EncryptUpdate` 之后**没有调用 `EVP_EncryptFinal`**，所以非整块的尾部没被处理
  → 保持明文。

用 Ghidra headless（`tools/DecompAll.java`）可复现整个分析，详见 `docs/`。

## 安全说明

这套备份加密**实际上等于没加密**：

* 无盐、无 KDF 迭代、不绑定设备——密钥是**密码的纯函数**。
* 因此**相同明文 ⇒ 相同密文**（跨备份一致），密钥空间 = 密码空间；6 位数字密码
  可**秒级暴力**（每次只需解密 1 个块判断）。
* 采用 **AES-ECB**，还会泄露块内结构。

如果你依赖这些备份做保密，请当作**未加密**处理。

## 免责声明

* 仅用于恢复**你本人**的备份。
* 与 OPPO、一加、realme、ColorOS 无任何关联。
* 不包含任何个人数据、密钥或样本备份。
* 出于研究/学习目的发布；请仅对自己有权访问的数据使用。

## 许可证

Apache-2.0。

## 致谢

* [ChidcGithub/Dog3Decryption](https://github.com/ChidcGithub/Dog3Decryption) —— 同类技术参考。
* [bkerler/oppo_decrypt](https://github.com/bkerler/oppo_decrypt) —— OPPO OZIP 固件工具。
