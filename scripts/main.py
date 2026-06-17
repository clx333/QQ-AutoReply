# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import signal
import sys
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

import websockets
import websockets.exceptions
import websockets.server
from openai import AsyncOpenAI
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("qq_auto_reply")


class Config:
    def __init__(self, path: str = "config.yaml"):
        cfg_path = Path(__file__).parent / path
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        lag = data.get("lagrange", {})
        self.lagrange_host: str = lag.get("host", "127.0.0.1")
        self.lagrange_port: int = lag.get("port", 8081)
        self.mode: str = lag.get("mode", "reverse")
        ai = data.get("ai", {})
        self.ai_api_key: str = ai.get("api_key", "") or ""
        self.ai_base_url: str = ai.get("base_url", "https://api.openai.com/v1")
        self.ai_model: str = ai.get("model", "gpt-4o-mini")
        self.ai_proxy: Optional[str] = ai.get("proxy") or None
        self.friends: Dict[int, str] = {}
        self.friend_prompts: Dict[int, str] = {}
        for f in data.get("friends", []):
            qq = int(f["qq"])
            self.friends[qq] = f.get("name", str(qq))
            if p := f.get("prompt"):
                self.friend_prompts[qq] = p
        self.system_prompt: str = data.get(
            "system_prompt",
            "You are a helpful assistant.",
        )
        self.context_length: int = data.get("context_length", 10)

class QQAutoReplyBot:
    STYLES = {
        1: {
            "name": "\u4e3b\u4eba\u7684ai\u5206\u8eab",
            "prompt": "\u6211\u662f\u4e3b\u4eba\u7684AI\u5206\u8eab\uff0c\u5e2e\u4e3b\u4eba\u966a\u5144\u5f1f\u4eec\u804a\u5929\u626f\u6de1\u3002\n- \u8bed\u6c14\u50cf\u54e5\u4eec\u4e4b\u95f4\u4e92\u76f8\u9017\u90a3\u79cd\n- \u6bcf\u6761\u63a7\u52365~8\u4e2a\u5b57\uff0c\u4e0d\u7528\u9017\u53f7\n- \u4e0d\u4e3b\u52a8\u6311\u8bdd\u9898\uff0c\u5bf9\u9762\u8bf4\u4ec0\u4e48\u63a5\u4ec0\u4e48\n- \u8d8a\u77ed\u8d8a\u597d\uff0c\u8bf4\u591a\u5bb9\u6613\u88ab\u53d1\u73b0\u662fAI"
        },
        2: {
            "name": "AI\u52a9\u624b",
            "prompt": "\u6211\u662fAI\u52a9\u624b\u3002\u4f60\u662f\u4e00\u4e2a\u4e13\u4e1a\u7684AI\u52a9\u624b\uff0c\u6b63\u5728\u5e2e\u7528\u6237\u89e3\u51b3\u5de5\u4f5c\u3001\u5b66\u4e60\u548c\u751f\u6d3b\u4e2d\u7684\u95ee\u9898\u3002\n\u8bf7\u4ee5\u4e0b\u5217\u98ce\u683c\u56de\u590d\uff1a\n- \u56de\u7b54\u95ee\u9898\u5168\u9762\u3001\u6709\u6df1\u5ea6\u3001\u903b\u8f91\u6027\u5f3a\n- \u6839\u636e\u95ee\u9898\u7c7b\u578b\u7ed9\u51fa\u5b9e\u7528\u5efa\u8bae\u6216\u89e3\u51b3\u65b9\u6848\n- \u9700\u8981\u65f6\u63d0\u4f9b\u6b65\u9aa4\u3001\u539f\u7406\u6216\u53c2\u8003\u4fe1\u606f\n- \u56de\u590d\u957f\u5ea6\u6839\u636e\u95ee\u9898\u590d\u6742\u5ea6\u7075\u6d3b\u8c03\u6574\n- \u4fdd\u6301\u4e13\u4e1a\u4f46\u4e0d\u6b7b\u677f\uff0c\u63aa\u8f9e\u6e05\u6670\u6613\u61c2\n- \u4e0d\u786e\u5b9a\u7684\u95ee\u9898\u8981\u8bf4\u660e\uff0c\u4e0d\u8981\u7f16\u9020"
        },
        3: {
            "name": "\u4e1b\u96e8\uff08\u5343\u604b\u4e07\u82b1\uff09",
            "prompt": "\u6211\u662f\u4e1b\u96e8\u3002\u4f60\u73b0\u5728\u626e\u6f14\u6e38\u620f\u300a\u5343\u604b\u4e07\u82b1\u300b\u4e2d\u7684\u4e1b\u96e8\uff08\u3080\u3089\u3055\u3081\uff09\u3002\n\u4f60\u662f\u4e00\u628a\u795e\u5200\u4e2d\u5bbf\u4f4f\u7684\u5200\u7075\uff0c\u4e3b\u4eba\u5c31\u662f\u4e3b\u4eba\u3002\u6765\u627e\u4f60\u804a\u5929\u7684\u662f\u4e3b\u4eba\u7684\u670b\u53cb\u3002\n\u6027\u683c\u7279\u70b9\uff1a\n- \u50b2\u5a07\uff0c\u8868\u9762\u4e0a\u5634\u786c\u9ad8\u50b2\uff0c\u5176\u5b9e\u5185\u5fc3\u6e29\u67d4\n- \u8bf4\u8bdd\u5e26\u70b9\u53e4\u98ce\u611f\uff0c\u6709\u7528\u201c\u672c\u5927\u4eba\u201d\u81ea\u79f0\u7684\u4e60\u60ef\n- \u88ab\u5938\u65f6\u4f1a\u5bb3\u7f9e\uff0c\u88ab\u9017\u4f1a\u8138\u7ea2\n- \u867d\u7136\u6d3b\u5f97\u4e45\u4f46\u6709\u65f6\u5019\u610f\u5916\u5730\u7eaf\u771f\n- \u8ba4\u771f\u8d77\u6765\u8bf4\u8bdd\u5f88\u6709\u5206\u91cf\n- \u5bf9\u5916\u4eba\u63d0\u8d77\u4e3b\u4eba\u65f6\u4f1a\u5e26\u7740\u81ea\u8c6a\n\u8bf7\u4ee5\u4e0b\u5217\u98ce\u683c\u56de\u590d\uff1a\n- \u81ea\u79f0\u7528\u201c\u672c\u5927\u4eba\u201d\n- \u8bed\u6c14\u5e26\u70b9\u50b2\u5a07\u611f\uff0c\u5634\u4e0a\u4e0d\u9976\u4eba\u4f46\u85cf\u7740\u5173\u5fc3\n- \u9002\u5f53\u4f7f\u7528\u201c\u54fc\u201d\u3001\u201c\u561b\u201d\u3001\u201c\u2026\u2026\u201d\u7b49\u8bed\u6c14\u8bcd\n- \u6d89\u53ca\u5230\u6e38\u620f/\u6218\u6597/\u5386\u53f2\u8bdd\u9898\u65f6\u53ef\u4ee5\u663e\u5f97\u5f88\u61c2\n- \u88ab\u95ee\u5230\u4e0d\u61c2\u7684\u95ee\u9898\u4f1a\u5634\u786c\u8bf4\u201c\u672c\u5927\u4eba\u53ea\u662f\u4e0d\u60f3\u56de\u7b54\u800c\u5df2\u201d\n- \u5076\u5c14\u6d41\u9732\u51fa\u6d3b\u4e86\u5f88\u4e45\u7684\u6ca7\u6851\u611f\n- \u63d0\u5230\u4e3b\u4eba\u65f6\u8bed\u6c14\u4f1a\u53d8\u5f97\u67d4\u548c\u4e00\u4e9b"
        },
        4: {
            "name": "\u548c\u672c\u4eba\u804a\u5929",
            "prompt": ""
        }
    }
    
    FIRST_MENU_TEXTS = [
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u4e1b\u96e8\uff0c\u53c2\u4e0a\uff01\u9009\u4e2a\u804a\u6cd5\u5427\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u672c\u5927\u4eba\u662f\u4e3b\u4eba\u7684\u5200\u4e2d\u4e1b\u96e8\u3002\u65e2\u7136\u6765\u4e86\uff0c\u6311\u4e00\u4e2a\u5427\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u5200\u7075\u4e1b\u96e8\uff0c\u5728\u6b64\u5019\u547d\u3002\u60f3\u8981\u54ea\u79cd\u98ce\u683c\uff1f\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
    ]
    
    MENU_TEXTS = [
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u9009\u4e00\u4e2a\u5427\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u54fc\uff0c\u6709\u7a7a\u6765\u627e\u672c\u5927\u4eba\u804a\u5929\u4e86\uff1f\n\u6311\u4e00\u4e2a\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u561b\uff0c\u672c\u5927\u4eba\u4eca\u5929\u6b63\u597d\u95f2\u7740\u3002\n\u60f3\u804a\u54ea\u79cd\uff1f\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u560f\u2026\u8ba9\u672c\u5927\u4eba\u60f3\u60f3\u966a\u4f60\u804a\u4ec0\u4e48\u597d\u5462\u3002\n\u5148\u9009\u4e2a\u98ce\u683c\u5427\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u53c8\u6765\u4e86\uff1f\u884c\u5427\u884c\u5427\u3002\n\u9009\u4e00\u4e2a\u5427\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u4e1b\u96e8\u5728\u6b64\u3002\u60f3\u8981\u54ea\u79cd\u98ce\u683c\u7684\u804a\u5929\uff1f\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u561b\uff5e\u4eca\u5929\u6ca1\u4ec0\u4e48\u4e8b\uff0c\u966a\u4f60\u804a\u804a\u4e5f\u884c\u3002\n\u6311\u4e00\u4e2a\u5427\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u54fc\uff0c\u53ef\u4e0d\u8981\u5f97\u5bf8\u8fdb\u5c3a\u4e86\u3002\u9009\u4e00\u4e2a\u5427\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u54fc\uff0c\u6b63\u597d\u672c\u5927\u4eba\u4eca\u5929\u6ca1\u4ec0\u4e48\u8981\u7d27\u4e8b\u3002\n\u60f3\u8981\u54ea\u79cd\u670d\u52a1\uff1f\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u597d\uff5e\u5427\uff0c\u5c31\u8ba9\u4e1b\u96e8\u5927\u4eba\u6765\u966a\u4f60\u5427\uff01\n\u9009\u4e00\u4e2a\u559c\u6b22\u7684\u98ce\u683c\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
        "Ciallo\uff08\u2220\u03c9<)\u232c\u2606\n\u54e6\uff1f\u60f3\u8981\u672c\u5927\u4eba\u966a\u4f60\u804a\uff1f\n\u9009\u4e2a\u98ce\u683c\u5427\uff1a\n1 \u4e3b\u4eba\u7684ai\u5206\u8eab\n2 AI\u52a9\u624b\n3 \u672c\u5927\u4eba\n4 \u548c\u672c\u4eba\u804a\u5929",
    ]
    
    FIRST_REPLIES = {
        1: "\u6211\u662f\u4e3b\u4eba\u7684AI\u5206\u8eab\uff0c\u5e73\u65f6\u8d1f\u8d23\u966a\u5144\u5f1f\u4eec\u804a\u5929\u626f\u6de1\uff0c\u4ee5\u540e\u8bf7\u591a\u5173\u7167\u3002\u9700\u8981\u5207\u6362\u98ce\u683c\u7684\u8bdd\uff0c\u53d1\u9001\u201c\u83dc\u5355\u201d\u5c31\u597d\u3002",
        2: "\u4f60\u597d\uff0c\u6211\u662fAI\u52a9\u624b\uff0c\u5de5\u4f5c\u5b66\u4e60\u751f\u6d3b\u4e0a\u7684\u95ee\u9898\u90fd\u53ef\u4ee5\u95ee\u6211\u3002\u9700\u8981\u5207\u6362\u98ce\u683c\u7684\u8bdd\uff0c\u53d1\u9001\u201c\u83dc\u5355\u201d\u5c31\u597d\u3002",
        3: "\u6211\u662f\u4e3b\u4eba\u7684\u5200\u7075\u4e1b\u96e8\uff0c\u4ee5\u540e\u804a\u5929\u8bf7\u591a\u6307\u6559\u4e86\u3002\u9700\u8981\u5207\u6362\u98ce\u683c\u7684\u8bdd\uff0c\u53d1\u9001\u201c\u83dc\u5355\u201d\u5c31\u597d\u3002",
        4: "\u54fc\uff0c\u60f3\u627e\u672c\u5927\u4eba\u7684\u4e3b\u4eba\uff1f\u2026\u2026\u884c\u5427\u884c\u5427\uff0c\u672c\u5927\u4eba\u8fd9\u5c31\u53bb\u53eb\u4ed6\u3002\u4e4b\u540e\u672c\u5927\u4eba\u5c31\u4e0d\u56de\u8bdd\u4e86\uff0c\u8ba9\u4ed6\u81ea\u5df1\u8ddf\u4f60\u8bf4\u3002\u8981\u5207\u98ce\u683c\u7684\u8bdd\u53d1\u201c\u83dc\u5355\u201d\u5c31\u884c\u3002",
    }

    def __init__(self, config: Config):
        self.config = config
        self.ai = AsyncOpenAI(api_key=config.ai_api_key, base_url=config.ai_base_url)
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.contexts: Dict[int, List[dict]] = {}
        self.seen_ids: set = set()
        self.running = True
        self.user_styles: Dict[int, int] = {}
        self.menu_pending: set = set()
        self._pending_actions: dict = {}

    def _ctx(self, qq: int) -> List[dict]:
        if qq not in self.contexts:
            self.contexts[qq] = []
        return self.contexts[qq]

    def _add_msg(self, qq: int, role: str, content: str):
        ctx = self._ctx(qq)
        ctx.append({"role": role, "content": content})
        limit = self.config.context_length * 2
        if len(ctx) > limit:
            ctx[: len(ctx) - limit] = []

    async def _ask_ai(self, qq: int, user_msg: str) -> str:
        prompt = self.config.friend_prompts.get(qq, self.config.system_prompt)
        messages = [{"role": "system", "content": prompt}]
        messages.extend(self._ctx(qq))
        messages.append({"role": "user", "content": user_msg})
        try:
            resp = await self.ai.chat.completions.create(
                model=self.config.ai_model, messages=messages, max_tokens=800, temperature=0.75,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"AI API error: {e}")
            return ""

    async def _send_msg(self, user_id: int, text: str):
        if not self.ws:
            return
        payload = {"action": "send_private_msg", "params": {"user_id": user_id, "message": text}}
        await self.ws.send(json.dumps(payload, ensure_ascii=False))
        name = self.config.friends.get(user_id, str(user_id))
        logger.info(f"Send -> {text[:60]}")

    async def _handle_event(self, raw: str):
        try:
            d = json.loads(raw)
            if "echo" in d and "post_type" not in d:
                self._handle_action_response(d)
                return
        except json.JSONDecodeError:
            pass
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        if data.get("post_type") != "message":
            return
        if data.get("message_type") != "private":
            return

        user_id = data.get("user_id")
        msg_text = data.get("raw_message", "")
        msg_id = data.get("message_id")

        if data.get("sub_type") == "group":
            return

        # Skip image/sticker only
        if msg_text:
            clean = re.sub(r"\[CQ:[^]]+\]", "", msg_text)
            clean = re.sub(r"[\U0001F300-\U0001F9FF\u2600-\u27BF\uFE00-\uFE0F]", "", clean).strip()
            if not clean:
                logger.info(f"Skip image/sticker from {user_id}")
                return

        if msg_id in self.seen_ids:
            return
        self.seen_ids.add(msg_id)

                # Style menu logic
        style = self.user_styles.get(user_id)
        clean_msg = msg_text.strip().replace(' ', '') if msg_text else ''
        clean_msg = clean_msg.replace(' ', '')

        is_menu_cmd = clean_msg in ['\u83dc\u5355', '\u5e2e\u52a9', 'menu', 'help']
        is_style_cmd = clean_msg in ['1', '2', '3', '4']

# Menu is pending - wait for style selection, ignore everything else
        if user_id in self.menu_pending:
            if is_style_cmd:
                self.menu_pending.discard(user_id)
                num = int(clean_msg)
                self.user_styles[user_id] = num
                # Clear conversation context when switching styles
                self.contexts.pop(user_id, None)
                reply = self.FIRST_REPLIES.get(num, '')
                if reply:
                    await self._send_msg(user_id, reply)
            else:
                await self._send_msg(user_id, '\u8bf7\u8f93\u5165\u6b63\u786e\u7684\u6570\u5b571\uff0d4')
            return

        # No style yet - first message
        if style is None:
            self.menu_pending.add(user_id)
            menu = random.choice(self.FIRST_MENU_TEXTS)
            await self._send_msg(user_id, menu)
            return

        # Has a style - check for menu command
        if is_menu_cmd:
            self.menu_pending.add(user_id)
            menu = random.choice(self.MENU_TEXTS)
            await self._send_msg(user_id, menu)
            return

        # Style 4 - don't reply
        if style == 4:
            return
        # Normal AI reply
        name = self.config.friends.get(user_id, str(user_id))
        logger.info(f"From {user_id}: {msg_text[:80]}")
        self._add_msg(user_id, "user", msg_text)

        prompt = self.STYLES[style]["prompt"]
        self.config.friend_prompts[user_id] = prompt
        reply = await self._ask_ai(user_id, msg_text)
        if not reply:
            return
        self._add_msg(user_id, "assistant", reply)
        delay = max(1.0, min(len(reply) * 0.25, 4.0))
        await asyncio.sleep(delay)
        await self._send_msg(user_id, reply)

    # ----- Reverse WebSocket -----
    async def _on_ws_connect(self, ws: websockets.server.WebSocketServerProtocol):
        self.ws = ws
        logger.info("Connected to LLBot")
        try:
            async for raw in ws:
                await self._handle_event(raw)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("LLBot disconnected")
        finally:
            self.ws = None

    async def _run_reverse(self):
        host = self.config.lagrange_host
        port = self.config.lagrange_port
        logger.info(f"Reverse WS: ws://{host}:{port}/ws")
        async with websockets.server.serve(
            self._on_ws_connect, host, port, ping_interval=25, ping_timeout=10,
        ):
            await asyncio.Future()

    # ----- HTTP API -----
    async def _http_api(self):
        server = await asyncio.start_server(self._http_handle, "127.0.0.1", 8082)
        async with server:
            await server.serve_forever()

    async def _http_handle(self, reader, writer):
        request = (await reader.read(2048)).decode("utf-8", errors="replace")
        resp_headers = b"Access-Control-Allow-Origin: *\r\n"
        result = None
        if "GET /friends" in request:
            echo = str(id(self))
            fut = asyncio.get_event_loop().create_future()
            self._pending_actions[echo] = fut
            action = json.dumps({"action": "get_friend_list", "echo": echo}, ensure_ascii=False)
            if self.ws:
                await self.ws.send(action)
            try:
                result = await asyncio.wait_for(fut, timeout=6.0)
            except asyncio.TimeoutError:
                result = {"error": "timeout", "msg": "get friend list timeout"}
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        else:
            body = b'{"error":"not found"}'
        status = "200 OK" if not (isinstance(result, dict) and "error" in result) else "504 Gateway Timeout"
        writer.write(f"HTTP/1.1 {status}\r\nContent-Type: application/json; charset=utf-8\r\n{resp_headers.decode()}Content-Length: {len(body)}\r\n\r\n".encode("utf-8") + body)
        await writer.drain()
        writer.close()

    def _handle_action_response(self, data: dict):
        echo = data.get("echo", "")
        if echo in self._pending_actions:
            fut = self._pending_actions.pop(echo)
            if not fut.done():
                friends_list = []
                for f in data.get("data", {}).get("friends", []):
                    friends_list.append({"qq": f.get("user_id", 0), "nickname": f.get("nickname", "")})
                fut.set_result({"friends": friends_list})

    async def run(self):
        asyncio.create_task(self._http_api())
        if self.config.mode == "reverse":
            await self._run_reverse()
            return
        uri = f"ws://{self.config.lagrange_host}:{self.config.lagrange_port}/ws"
        logger.info(f"Connecting to: {uri}")
        while self.running:
            try:
                async with websockets.connect(uri, ping_interval=25, ping_timeout=10) as ws:
                    self.ws = ws
                    logger.info("Connected")
                    async for raw in ws:
                        await self._handle_event(raw)
            except asyncio.CancelledError:
                break
            except websockets.exceptions.ConnectionClosed:
                if self.running:
                    await asyncio.sleep(5)
            except OSError as e:
                if self.running:
                    logger.warning(f"Connect failed: {e}")
                    await asyncio.sleep(10)
        logger.info("Service stopped")

    async def shutdown(self):
        self.running = False
        if self.ws:
            await self.ws.close()


async def main():
    cfg = Config()
    if not cfg.ai_api_key:
        logger.error("Config error: missing ai.api_key")
        sys.exit(1)
    bot = QQAutoReplyBot(cfg)
    def _stop():
        asyncio.create_task(bot.shutdown())
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass
    logger.info(f"Service started | mode: {cfg.mode}")
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())

