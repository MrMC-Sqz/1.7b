from dataclasses import dataclass


@dataclass(slots=True)
class V1Config:
    urgency_threshold: float = 0.7
    wait_ms: int = 800
    context_window_ms: int = 10000
    max_pending_per_speaker: int = 3
    use_qwen_intent_engine: bool = True
    use_score_head_intent_engine: bool = False
    score_head_model_path: str = ""
    intent_model_name: str = "Qwen/Qwen3-1.7B"
    intent_device_map: str = "auto"
    intent_max_new_tokens: int = 96
    intent_inference_timeout_sec: float = 20.0
    intent_disable_thinking: bool = True
    event_log_path: str | None = None
