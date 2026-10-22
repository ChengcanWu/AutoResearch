# -*- coding: utf-8 -*-
"""HCI 第四轮：成绩单那句移出对话开场；新号今日页不摆四步条；研读/今日顶上「继续上次」。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_round4_copy_and_continue_card():
    app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    chat = (ROOT / "web" / "js" / "chat.js").read_text(encoding="utf-8")
    onb = (ROOT / "server" / "onboarding.py").read_text(encoding="utf-8")
    for s in ("function rememberTutor(", "function lastTutor(", "function continueCard(", "继续上次：", "接着答",
              "if (field || talked) wrap.appendChild(loopStrip(", "rg_last_tutor_"):
        assert s in app, s
    assert "可选：粘贴成绩单" in chat and "也可以粘贴成绩单…" not in chat
    assert "说说你的院系和年级，我才知道从哪开始" in chat
    welcome = onb.split("WELCOME_MESSAGE = (", 1)[1].split("\n)", 1)[0]
    assert "树洞" not in welcome and "成绩单" not in welcome
