# -*- coding: utf-8 -*-
"""公众号消息接口：验签、解析、被动回复。微信登录的流程在 auth.py。

为什么走公众号消息而不是「微信扫码登录」：网站扫码登录要微信开放平台的企业认证和备案域名，
公众号网页授权要认证服务号，个人都拿不到；个人订阅号可以开「服务器配置」收用户发来的消息，
消息里带发信人的 openid（只对这个公众号有效的编号），够我们认出是谁。

公众号后台：设置与开发 → 基本配置 → 服务器配置。URL 填 <接口地址>/api/wechat，Token 填 WECHAT_TOKEN，
消息加解密方式选「明文模式」，然后启用。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

MAX_BODY = 16 * 1024   # 文本消息几百字节；再大就不是微信发来的
MAX_SKEW = 300         # 时间戳差五分钟以上的当作重放


def token() -> str:
    return (os.environ.get("WECHAT_TOKEN") or "").strip()


def configured() -> bool:
    return bool(token())


def check_signature(signature: str, timestamp: str, nonce: str) -> bool:
    """微信的签名：token、timestamp、nonce 三个字符串排序后拼起来取 SHA1。另外拒绝太旧的时间戳。"""
    tok = token()
    if not tok or not signature or not timestamp.isdigit():
        return False
    if abs(time.time() - int(timestamp)) > MAX_SKEW:
        return False
    expect = hashlib.sha1("".join(sorted([tok, timestamp, nonce])).encode()).hexdigest()
    return hmac.compare_digest(expect, signature)


def parse(body: bytes) -> dict[str, str]:
    """明文模式的消息 XML → {ToUserName, FromUserName, MsgType, Content, Event, MsgId…}。
    带 DOCTYPE / ENTITY 的一律不解析（防实体展开）；解析失败抛 ValueError。"""
    if len(body) > MAX_BODY or b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise ValueError("不像微信的消息")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError("XML 解析失败") from exc
    return {child.tag: (child.text or "") for child in root}


def reply_text(msg: dict[str, str], content: str) -> str:
    """被动回复一条文本：收发人对调。"""
    def cdata(s: str) -> str:
        return "<![CDATA[" + s.replace("]]>", "]]]]><![CDATA[>") + "]]>"
    return ("<xml>"
            f"<ToUserName>{cdata(msg.get('FromUserName', ''))}</ToUserName>"
            f"<FromUserName>{cdata(msg.get('ToUserName', ''))}</FromUserName>"
            f"<CreateTime>{int(time.time())}</CreateTime>"
            f"<MsgType>{cdata('text')}</MsgType>"
            f"<Content>{cdata(content)}</Content>"
            "</xml>")


def qr_url() -> str:
    """关注公众号的二维码。WECHAT_QR_URL 直接给图片地址；或者只给原始 ID（gh_ 开头），用微信的公开二维码地址。"""
    url = (os.environ.get("WECHAT_QR_URL") or "").strip()
    if url:
        return url
    gh = (os.environ.get("WECHAT_ACCOUNT_ID") or "").strip()
    return f"https://open.weixin.qq.com/qr/code?username={escape(gh)}" if gh else ""


def account_name() -> str:
    return (os.environ.get("WECHAT_ACCOUNT_NAME") or "").strip()
