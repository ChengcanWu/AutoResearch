# -*- coding: utf-8 -*-
"""发登录验证码邮件。

任何支持 SMTP 的邮箱都行：QQ / 163 邮箱在设置里开 SMTP、拿授权码就能用（每天几百封够起步）；
量大了换阿里云邮件推送（要一个自己的域名做发信地址）。
环境变量（也可写在 .env）：SMTP_HOST、SMTP_PORT（默认 465，SSL；填 587 走 STARTTLS）、
SMTP_USER、SMTP_PASSWORD（授权码，不是邮箱登录密码）、SMTP_FROM（默认同 SMTP_USER）。
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

TIMEOUT = 15  # 每一步（连接、登录、发送）最多等这么久


def configured() -> bool:
    return all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))


def send_code(to: str, code: str, minutes: int) -> None:
    """发不出去就抛异常（smtplib.SMTPException / OSError），调用方决定怎么告诉用户。"""
    user = os.environ["SMTP_USER"]
    msg = EmailMessage()
    msg["Subject"] = f"启研登录验证码 {code}"
    msg["From"] = formataddr(("启研", os.environ.get("SMTP_FROM") or user))
    msg["To"] = to
    msg.set_content(
        f"你的启研登录验证码是 {code}，{minutes} 分钟内有效。\n\n"
        "不是你本人在登录的话，忽略这封邮件就好：没有这个验证码，别人登不进你的账号。\n"
    )
    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT") or 465)
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=ctx) as s:
            s.login(user, os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=TIMEOUT) as s:
            s.starttls(context=ctx)
            s.login(user, os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
