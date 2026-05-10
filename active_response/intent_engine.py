from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

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
        "空调",
        "温度",
        "车窗",
        "天窗",
        "除雾",
        "雨刷",
        "音量",
        "播放",
        "暂停",
        "下一首",
        "打电话",
        "开一下",
        "关一下",
    )
    _LOW_PRIORITY_CHAT_KEYWORDS = (
        "哈哈",
        "天气",
        "吃饭",
        "电影",
        "八卦",
        "聊天",
    )
    _MID_PRIORITY_HINTS = ("帮我", "麻烦", "可以吗", "怎么", "如何", "查一下")

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
            return 0.86, "vehicle_control_or_task", self._draft_for_vehicle_control(text)
        if self._contains_any(text, self._LOW_PRIORITY_CHAT_KEYWORDS):
            return 0.18, "casual_chat", "我先保持安静，如需帮助请直接叫我。"
        if self._contains_any(text, self._MID_PRIORITY_HINTS):
            return 0.56, "possible_request", "我可以继续帮你处理，告诉我你的具体需求。"
        return 0.42, "insufficient_signal", "我先听着，有需要可以随时叫我。"

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
        if any(
            u.speaker_id == speaker_id and self._contains_any(u.text, self._HIGH_PRIORITY_KEYWORDS)
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
        if "导航" in text:
            return "收到，我来为你准备导航。"
        if "播放" in text or "下一首" in text or "暂停" in text:
            return "好的，正在处理媒体播放指令。"
        if "打电话" in text:
            return "明白，正在帮你发起通话。"
        return "收到，正在执行你的车控请求。"


@dataclass(slots=True)
class QwenIntentEngine(BaseIntentEngine):
    model_name: str = "Qwen/Qwen3-1.7B"
    urgency_threshold: float = 0.7
    device_map: str = "auto"
    max_new_tokens: int = 128
    inference_timeout_sec: float = 25.0
    disable_thinking: bool = True
    fallback_engine: BaseIntentEngine | None = None

    _tokenizer: Any = None
    _model: Any = None
    _load_error: str | None = None

    def score(self, context: Sequence[Utterance], current_utt: Utterance) -> IntentResult:
        self._ensure_model()
        if self._model is None or self._tokenizer is None:
            return self._fallback(
                context=context,
                current_utt=current_utt,
                reason=f"qwen_unavailable:{self._load_error or 'unknown_error'}",
            )

        prompt = self._build_prompt(context=context, current_utt=current_utt)
        try:
            messages = [{"role": "user", "content": prompt}]
            text = self._apply_chat_template(messages)
            inputs = self._tokenizer([text], return_tensors="pt").to(self._model.device)

            eos = self._tokenizer.eos_token_id
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                num_beams=1,
                max_time=self.inference_timeout_sec,
                eos_token_id=eos,
                pad_token_id=eos,
            )
            generated = outputs[0][inputs.input_ids.shape[-1] :]
            raw = self._tokenizer.decode(generated, skip_special_tokens=True).strip()
            parsed = self._parse_output(raw=raw)
            score = max(0.0, min(1.0, float(parsed.get("score", 0.0))))
            should = bool(parsed.get("should_respond", score >= self.urgency_threshold))
            reply = parsed.get("reply") if should else None
            reason = str(parsed.get("reason", "qwen_scored"))
            return IntentResult(
                utterance_id=current_utt.utterance_id,
                score=round(score, 3),
                should_respond=should,
                reason=reason,
                draft_reply=reply,
            )
        except Exception as exc:  # noqa: BLE001
            return self._fallback(
                context=context,
                current_utt=current_utt,
                reason=f"qwen_inference_error:{exc}",
            )

    def _apply_chat_template(self, messages: list[dict[str, str]]) -> str:
        # Qwen3 tokenizer often supports enable_thinking=False; keep a safe fallback.
        if self.disable_thinking:
            try:
                return self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                pass
        return self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    def _fallback(
        self,
        context: Sequence[Utterance],
        current_utt: Utterance,
        reason: str,
    ) -> IntentResult:
        if self.fallback_engine is not None:
            result = self.fallback_engine.score(context=context, current_utt=current_utt)
            result.reason = f"fallback_rule_engine:{reason}"
            return result
        return IntentResult(
            utterance_id=current_utt.utterance_id,
            score=0.0,
            should_respond=False,
            reason=reason,
            draft_reply=None,
        )

    def _ensure_model(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        if self._load_error is not None:
            return
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"missing_transformers:{exc}"
            return
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                device_map=self.device_map,
            )
            # Keep deterministic decode config aligned with do_sample=False to avoid noisy warnings.
            gen_cfg = self._model.generation_config
            gen_cfg.do_sample = False
            gen_cfg.temperature = None
            gen_cfg.top_p = None
            gen_cfg.top_k = None
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)

    @staticmethod
    def _build_prompt(context: Sequence[Utterance], current_utt: Utterance) -> str:
        history_lines = [
            f"[{u.start_ms}-{u.end_ms}] speaker={u.speaker_id}: {u.text}" for u in context[-12:]
        ]
        history = "\n".join(history_lines) if history_lines else "(empty)"
        # Keep prompt strict and short to reduce drift.
        return (
            "你是车载助手主动响应判定器。"
            "只输出一个 JSON 对象，不要输出解释。\n"
            "JSON schema: {\"score\":0~1,\"should_respond\":bool,\"reason\":str,\"reply\":str}\n"
            "规则：闲聊/人与人对话通常不响应；车控、导航、媒体控制、明确求助优先响应。\n"
            f"history:\n{history}\n"
            f"current:\n[{current_utt.start_ms}-{current_utt.end_ms}] "
            f"speaker={current_utt.speaker_id}: {current_utt.text}\n"
        )

    @staticmethod
    def _parse_output(raw: str) -> dict[str, Any]:
        # Remove optional thinking blocks if present.
        raw = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()

        # 1) strict JSON object extraction
        json_candidates = re.findall(r"\{[\s\S]*?\}", raw)
        for chunk in json_candidates:
            try:
                parsed = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

        # 2) weak score extraction
        score_match = re.search(r"score[^0-9]*([01](?:\.\d+)?)", raw, flags=re.I)
        if score_match:
            score = float(score_match.group(1))
            return {
                "score": max(0.0, min(1.0, score)),
                "should_respond": score >= 0.7,
                "reason": "qwen_pattern_extracted",
                "reply": "收到，我来帮你处理。",
            }

        lowered = raw.lower()
        if re.search(r"should_respond[^a-z0-9]*false", lowered):
            return {
                "score": 0.2,
                "should_respond": False,
                "reason": "qwen_non_json_negative",
                "reply": "",
            }
        if re.search(r"should_respond[^a-z0-9]*true", lowered):
            return {
                "score": 0.8,
                "should_respond": True,
                "reason": "qwen_non_json_positive",
                "reply": "收到，我来帮你处理。",
            }

        # Conservative fallback.
        return {
            "score": 0.5,
            "should_respond": False,
            "reason": "qwen_non_json_uncertain",
            "reply": "",
        }


@dataclass(slots=True)
class ScoreHeadIntentEngine(BaseIntentEngine):
    model_path: str
    urgency_threshold: float = 0.7
    device: str = "cuda"

    _tokenizer: Any = None
    _model: Any = None
    _load_error: str | None = None

    def score(self, context: Sequence[Utterance], current_utt: Utterance) -> IntentResult:
        self._ensure_model()
        if self._model is None or self._tokenizer is None:
            return IntentResult(
                utterance_id=current_utt.utterance_id,
                score=0.0,
                should_respond=False,
                reason=f"score_head_unavailable:{self._load_error or 'unknown_error'}",
                draft_reply=None,
            )

        text = self._build_input_text(context=context, current_utt=current_utt)
        try:
            import torch

            inputs = self._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
            )
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
            with torch.no_grad():
                out = self._model(**inputs)
                raw_logit = float(out.logits.squeeze().item())
                raw_score = float(torch.sigmoid(torch.tensor(raw_logit)).item())
            score = max(0.0, min(1.0, raw_score))
            should = score >= self.urgency_threshold
            reply = "收到，我来帮你处理。" if should else None
            return IntentResult(
                utterance_id=current_utt.utterance_id,
                score=round(score, 3),
                should_respond=should,
                reason="score_head_scored",
                draft_reply=reply,
            )
        except Exception as exc:  # noqa: BLE001
            return IntentResult(
                utterance_id=current_utt.utterance_id,
                score=0.0,
                should_respond=False,
                reason=f"score_head_inference_error:{exc}",
                draft_reply=None,
            )

    def _ensure_model(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        if self._load_error is not None:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"missing_runtime:{exc}"
            return
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_path,
                trust_remote_code=True,
            )
            target_device = "cuda" if self.device == "cuda" and torch.cuda.is_available() else "cpu"
            self._model.to(target_device)
            self._model.eval()
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)

    @staticmethod
    def _build_input_text(context: Sequence[Utterance], current_utt: Utterance) -> str:
        history_lines = [
            f"[{u.start_ms}-{u.end_ms}] {u.speaker_id}: {u.text}" for u in context[-12:]
        ]
        history = "\n".join(history_lines) if history_lines else "(empty)"
        return (
            "Task: predict response urgency score in [0,1] for in-car assistant.\n"
            f"history:\n{history}\n"
            f"current:\n[{current_utt.start_ms}-{current_utt.end_ms}] "
            f"{current_utt.speaker_id}: {current_utt.text}\n"
        )
