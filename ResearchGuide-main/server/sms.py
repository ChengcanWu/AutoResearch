# -*- coding: utf-8 -*-
"""手机验证码：阿里云号码认证服务的「短信认证」（Dypnsapi SendSmsVerifyCode / CheckSmsVerifyCode）。

为什么是它：普通短信服务的签名只批企业名或注册商标；短信认证给个人实名账号用平台赠送的签名和模板，
验证码由阿里云生成、核验，我们的库里不存验证码。按条计费，发送失败不收费，核验免费。

开通：阿里云账号个人实名 → 号码认证服务控制台开通「短信认证」→ 记下赠送的签名名称和模板编号
→ 建一个只有号码认证权限的 RAM 用户拿 AccessKey（函数计算上也可以给函数挂角色，平台会注入临时密钥）。
环境变量：ALIBABA_CLOUD_ACCESS_KEY_ID、ALIBABA_CLOUD_ACCESS_KEY_SECRET（挂角色时还有
ALIBABA_CLOUD_SECURITY_TOKEN）、SMS_SIGN_NAME、SMS_TEMPLATE_CODE。

不用官方 SDK：两个接口、一种签名（RPC 风格 HMAC-SHA1），标准库就够，部署包里少一串依赖。
请求走 limits.fetch，有总时限和字节上限。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

from limits import fetch

ENDPOINT = "https://dypnsapi.aliyuncs.com/"
VERSION = "2017-05-25"
TIMEOUT = 10
MAX_BYTES = 64 * 1024


class SmsError(Exception):
    """阿里云回了错误。code 是去掉前缀的错误码（如 BUSINESS_LIMIT_CONTROL），调用方据此决定怎么告诉用户。"""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _env(*names: str) -> str:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v.strip()
    return ""


def configured() -> bool:
    return bool(_env("ALIBABA_CLOUD_ACCESS_KEY_ID") and _env("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
                and _env("SMS_SIGN_NAME") and _env("SMS_TEMPLATE_CODE"))


def _pe(s: str) -> str:
    """阿里云 RPC 签名要的百分号编码：RFC 3986，只留 字母数字 - _ . ~。"""
    return urllib.parse.quote(s, safe="-_.~")


def sign(params: dict[str, str], secret: str, method: str = "GET") -> str:
    canonical = "&".join(f"{_pe(k)}={_pe(v)}" for k, v in sorted(params.items()))
    to_sign = f"{method}&{_pe('/')}&{_pe(canonical)}"
    digest = hmac.new(f"{secret}&".encode(), to_sign.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _call(action: str, params: dict[str, str]) -> dict:
    q = {
        "Action": action, "Version": VERSION, "Format": "JSON",
        "AccessKeyId": _env("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        "SignatureMethod": "HMAC-SHA1", "SignatureVersion": "1.0", "SignatureNonce": uuid.uuid4().hex,
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **params,
    }
    token = _env("ALIBABA_CLOUD_SECURITY_TOKEN")
    if token:
        q["SecurityToken"] = token
    q["Signature"] = sign(q, _env("ALIBABA_CLOUD_ACCESS_KEY_SECRET"))
    req = urllib.request.Request(ENDPOINT + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote))
    try:
        raw = fetch(req, timeout=TIMEOUT, max_bytes=MAX_BYTES)
    except urllib.error.HTTPError as exc:  # 参数错、限流、没开通都是 4xx，正文里有错误码
        raw = exc.read(MAX_BYTES)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SmsError("BAD_RESPONSE", raw[:200].decode("utf-8", "replace")) from exc
    if data.get("Code") != "OK":
        code = str(data.get("Code") or "UNKNOWN").rsplit(".", 1)[-1]  # isv.BUSINESS_LIMIT_CONTROL → BUSINESS_LIMIT_CONTROL
        raise SmsError(code, str(data.get("Message") or ""))
    return data


def send(phone: str, minutes: int) -> None:
    """让阿里云生成一个 6 位数字验证码发到这个号码。网络错误抛 OSError，接口错误抛 SmsError。"""
    _call("SendSmsVerifyCode", {
        "PhoneNumber": phone, "CountryCode": "86",
        "SignName": _env("SMS_SIGN_NAME"), "TemplateCode": _env("SMS_TEMPLATE_CODE"),
        "TemplateParam": json.dumps({"code": "##code##", "min": str(minutes)}),
        "CodeLength": "6", "CodeType": "1", "ValidTime": str(minutes * 60),
        "Interval": "60", "DuplicatePolicy": "1", "ReturnVerifyCode": "false",
    })


def check(phone: str, code: str) -> bool:
    """Code=OK 只说明请求成功；验证码对不对看 Model.VerifyResult 是不是 PASS。"""
    data = _call("CheckSmsVerifyCode", {"PhoneNumber": phone, "CountryCode": "86", "VerifyCode": code})
    return (data.get("Model") or {}).get("VerifyResult") == "PASS"
