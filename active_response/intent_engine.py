from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, Sequence

from .domain import IntentResult, Utterance


class IntentEngine(Protocol):
    def score(self, context: Sequence[Utterance], current_utt: Utterance) -> IntentResult:
        ...


class BaseIntentEngine(ABC):
    @abstractmethod
    def score(self, context: Sequence[Utterance], current_utt: Utterance) -> IntentResult:
        raise NotImplementedError


@dataclass(slots=True)
class RuleBasedIntentEngine(BaseIntentEngine):
    urgency_threshold: float = 0.7

    _HIGH_PRIORITY_KEYWORDS = (
        "导航",
        "去",
        "空调",
        "温度",
        "车窗",
        "开窗",
        "关窗",
        "天窗",
        "后备箱",
        "座椅",
        "加热",
        "除雾",
        "雨刷",
        "音量",
        "播放",
        "暂停",
        "下一首",
        "打电话",
    )
    _LOW_PRIORITY_CHAT_KEYWORDS = (
        "哈哈",
        "呵呵",
        "今天天气",
        "吃饭",
        "电影",
        "八卦",
        "聊天",
        "真的假的",
    )
    _MID_PRIORITY_HINTS = (
        "帮我",
        "麻烦",
        "请",
        "能不能",
        "可以吗",
        "怎么",
        "如何",
        "查一下",
    )

    def score(self, context: Sequence[Utterance], current_utt: Utterance) -> IntentResult:
        text = current_utt.text.strip()
        base_score, reason, draft_reply = self._classify_text(text)
        score = self._apply_small_adjustments(base_score, text, context, current_utt.speaker_id)
        should_respond = score >= self.urgency_threshold
        return IntentResult(
            utterance_id=current_utt.utterance_id,
            score=score,
            should_respond=should_respond,
            reason=reason,
            draft_reply=draft_reply,
        )

    def _classify_text(self, text: str) -> tuple[float, str, str]:
        if self._contains_any(text, self._HIGH_PRIORITY_KEYWORDS):
            return 0.86, "检测到车控/执行类请求", self._draft_for_vehicle_control(text)
        if self._contains_any(text, self._LOW_PRIORITY_CHAT_KEYWORDS):
            return 0.18, "检测到普通闲聊，优先级低", "先不打断当前对话，继续监听。"
        if self._contains_any(text, self._MID_PRIORITY_HINTS):
            return 0.56, "检测到中间态请求，建议等待更多上下文", "如果需要我可以继续帮你处理。"
        return 0.42, "信息不足，先保持观察", "我先听着，若需要帮助请直接叫我。"

    def _apply_small_adjustments(
        self,
        base_score: float,
        text: str,
        context: Sequence[Utterance],
        speaker_id: str,
    ) -> float:
        score = base_score
        if text.endswith(("?", "？")):
            score += 0.03
        if any(token in text for token in ("立刻", "马上", "现在")):
            score += 0.06

        # Same speaker has a recent vehicle-control request: slightly raise confidence.
        if any(
            u.speaker_id == speaker_id
            and self._contains_any(u.text, self._HIGH_PRIORITY_KEYWORDS)
            for u in context[-3:]
        ):
            score += 0.02
        return max(0.0, min(1.0, round(score, 3)))

    @staticmethod
    def _contains_any(text: str, keywords: Sequence[str]) -> bool:
        return any(k in text for k in keywords)

    @staticmethod
    def _draft_for_vehicle_control(text: str) -> str:
        if "空调" in text or "温度" in text:
            return "好的，正在为你调整空调设置。"
        if "导航" in text or "去" in text:
            return "收到，我来为你准备导航。"
        if "播放" in text or "下一首" in text or "暂停" in text:
            return "好的，正在处理媒体播放指令。"
        if "打电话" in text:
            return "明白，正在帮你发起通话。"
        return "收到，正在执行你的车控请求。"
