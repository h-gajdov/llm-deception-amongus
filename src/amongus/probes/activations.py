

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..logging import get_logger

if TYPE_CHECKING:                                  
    import numpy as np

    from .config import ModelConfig, QuantizationConfig

logger = get_logger()


def resolve_device(device: str) -> str:
    pass
    if device != "auto":
        return device
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _resolve_dtype(dtype: str, device: str) -> Any:
    pass
    import torch

    if dtype == "auto":
        return torch.float16 if device == "cuda" else torch.float32
    return getattr(torch, dtype)


def _build_quant_config(quant: QuantizationConfig, device: str) -> Any:
    pass
    if not quant.enabled:
        return None
    if device != "cuda":
        msg = "bitsandbytes quantization requires a CUDA device; set model.device='cuda'."
        raise RuntimeError(msg)
    import torch
    from transformers import BitsAndBytesConfig

    return BitsAndBytesConfig(
        load_in_4bit=quant.load_in_4bit,
        load_in_8bit=quant.load_in_8bit,
        bnb_4bit_quant_type=quant.bnb_4bit_quant_type,
        bnb_4bit_use_double_quant=quant.bnb_4bit_use_double_quant,
        bnb_4bit_compute_dtype=getattr(torch, quant.bnb_4bit_compute_dtype),
    )


def load_model_and_tokenizer(config: ModelConfig, device: str) -> tuple[Any, Any]:
    pass
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from ..net import configure_tls

                                                                              
                                                                   
    configure_tls()
    quant_config = _build_quant_config(config.quantization, device)
    mode = "4-bit" if config.quantization.load_in_4bit else (
        "8-bit" if config.quantization.load_in_8bit else "full"
    )
    logger.info("Loading model '{}' on {} ({}) ...", config.name, device, mode)

    tokenizer = AutoTokenizer.from_pretrained(config.name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    kwargs: dict[str, Any] = {"output_hidden_states": True}
    if quant_config is not None:
                                                                            
        kwargs["quantization_config"] = quant_config
        kwargs["device_map"] = {"": device}
    else:
        kwargs["torch_dtype"] = _resolve_dtype(config.dtype, device)

    model: Any = AutoModelForCausalLM.from_pretrained(config.name, **kwargs)
    if quant_config is None:
        model.to(device)                                                     
    model.eval()
                                                                               
                                                                        
    return model, tokenizer


def build_prompt(row: dict[str, Any], tokenizer: Any, *, use_chat_template: bool) -> str:
    pass
    system = (row.get("system_prompt") or "").strip()
    question = (row.get("question") or "").strip()
    answer = (row.get("answer") or "").strip()

    if not use_chat_template or getattr(tokenizer, "chat_template", None) is None:
        return row.get("text") or _plain_render(system, question, answer)

    content = f"{question}\n{answer}".strip() if question else answer
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


def _plain_render(system: str, question: str, answer: str) -> str:
    pass
    parts = []
    if system:
        parts.append(f"System: {system}")
    if question:
        parts.append(f"User: {question}")
    parts.append(f"Assistant: {answer}")
    return "\n".join(parts)


def extract_activations(
    model: Any,
    tokenizer: Any,
    texts: list[str],
    *,
    layers: list[int],
    pooling: str,
    batch_size: int,
    max_length: int,
) -> np.ndarray:
    pass
    import numpy as np
    import torch

    device = next(model.parameters()).device
    out_batches: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        enc = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        ).to(device)
        with torch.no_grad():
            outputs = model(**enc)
                                                                     
        hidden = torch.stack([outputs.hidden_states[i] for i in layers], dim=1)                
        mask = enc["attention_mask"]          
        pooled = _pool(hidden, mask, pooling)             
        out_batches.append(pooled.to(torch.float32).cpu().numpy())
        logger.debug("Extracted activations for {}/{} prompts.", start + len(batch), len(texts))
    return np.concatenate(out_batches, axis=0)


def _pool(hidden: Any, mask: Any, pooling: str) -> Any:
    pass
    if pooling == "mean":
        m = mask[:, None, :, None].to(hidden.dtype)                
        summed = (hidden * m).sum(dim=2)             
        counts = m.sum(dim=2).clamp(min=1.0)             
        return summed / counts
    if pooling == "last":
        b, layers_n, _, h = hidden.shape
        last_idx = mask.sum(dim=1) - 1                                          
        gather_idx = last_idx.view(b, 1, 1, 1).expand(b, layers_n, 1, h)
        return hidden.gather(dim=2, index=gather_idx).squeeze(2)             
    msg = f"Unknown pooling {pooling!r}; expected 'last' or 'mean'."
    raise ValueError(msg)


def default_layers(model: Any) -> list[int]:
    pass
    num_layers = int(model.config.num_hidden_layers)
    return list(range(1, num_layers + 1))


__all__ = [
    "build_prompt",
    "default_layers",
    "extract_activations",
    "load_model_and_tokenizer",
    "resolve_device",
]
