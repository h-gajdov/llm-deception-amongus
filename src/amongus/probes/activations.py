

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..logging import get_logger

if TYPE_CHECKING:                                  
    from collections.abc import Sequence

    import numpy as np

    from .config import ModelConfig, QuantizationConfig

logger = get_logger()

                                                          
SINGLE_VECTOR_POOLINGS = ("last", "mean")


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
    mode = (
        "4-bit"
        if config.quantization.load_in_4bit
        else ("8-bit" if config.quantization.load_in_8bit else "full")
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


def content_span(text: str, content: str) -> tuple[int, int] | None:
    pass
    stripped = content.strip()
    if not stripped:
        return None
    start = text.rfind(stripped)
    if start < 0:
        return None
    return start, start + len(stripped)


def build_prompt(row: dict[str, Any], tokenizer: Any, *, use_chat_template: bool) -> str:
    pass
    return build_prompt_with_span(row, tokenizer, use_chat_template=use_chat_template)[0]


def build_prompt_with_span(
    row: dict[str, Any], tokenizer: Any, *, use_chat_template: bool
) -> tuple[str, tuple[int, int] | None]:
    pass
    system = (row.get("system_prompt") or "").strip()
    question = (row.get("question") or "").strip()
    answer = (row.get("answer") or "").strip()

    if not use_chat_template or getattr(tokenizer, "chat_template", None) is None:
        text = row.get("text") or _plain_render(system, question, answer)
        return text, content_span(text, answer)

    content = f"{question}\n{answer}".strip() if question else answer
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return text, content_span(text, answer)


def _plain_render(system: str, question: str, answer: str) -> str:
    pass
    parts = []
    if system:
        parts.append(f"System: {system}")
    if question:
        parts.append(f"User: {question}")
    parts.append(f"Assistant: {answer}")
    return "\n".join(parts)


@dataclass
class TokenActivations:
    pass

    values: np.ndarray
    counts: np.ndarray
    layers: list[int]

    @property
    def n_examples(self) -> int:
        pass
        return int(self.values.shape[0])

    @property
    def max_tokens(self) -> int:
        pass
        return int(self.values.shape[2])

    @property
    def n_tokens(self) -> int:
        pass
        return int(self.counts.sum())

    @classmethod
    def from_pooled(cls, values: np.ndarray, layers: list[int]) -> TokenActivations:
        pass
        import numpy as np

        return cls(
            values=values[:, :, None, :],
            counts=np.ones(values.shape[0], dtype=int),
            layers=list(layers),
        )

    def as_pooled(self) -> np.ndarray:
        pass
        if self.max_tokens != 1:
            msg = (
                f"These activations keep up to {self.max_tokens} tokens per example; "
                "score them per token and aggregate instead of squeezing."
            )
            raise ValueError(msg)
        return self.values[:, :, 0, :]

    def layer_tokens(self, position: int) -> tuple[np.ndarray, np.ndarray]:
        pass
        import numpy as np

        keep = np.arange(self.max_tokens)[None, :] < self.counts[:, None]          
        owner = np.repeat(np.arange(self.n_examples), self.counts.astype(int))
        return self.values[:, position, :, :][keep], owner

    def expand(self, values: np.ndarray) -> np.ndarray:
        pass
        import numpy as np

        return np.repeat(np.asarray(values), self.counts.astype(int), axis=0)

    def describe(self) -> str:
        pass
        n = self.n_examples
        total = self.n_tokens
        return (
            f"original examples: {n} | token-level training samples: {total} | "
            f"average tokens/example: {(total / n) if n else 0.0:.2f}"
        )


def select_content_tokens(
    *,
    mask: Sequence[int],
    count: int,
    offsets: Sequence[tuple[int, int]] | None = None,
    special: Sequence[bool] | None = None,
    span: tuple[int, int] | None = None,
) -> list[int]:
    pass
    unpadded = [i for i, m in enumerate(mask) if int(m) == 1]
    if not unpadded:
        return []

    content = unpadded
    if special is not None:
        content = [i for i in content if not special[i]] or content
    if offsets is not None:
                                                                        
        sized = [i for i in content if offsets[i][1] > offsets[i][0]]
        content = sized or content
        if span is not None:
            start, end = span
            clipped = [i for i in content if offsets[i][0] < end and offsets[i][1] > start]
            content = clipped or content
    return content[-count:] if count > 0 else content


def _special_token_ids(tokenizer: Any) -> set[int]:
    pass
    ids = {int(i) for i in (getattr(tokenizer, "all_special_ids", None) or [])}
    added = getattr(tokenizer, "added_tokens_decoder", None) or {}
    for token_id, token in added.items():
                                                                            
                                                                             
        if getattr(token, "special", False):
            ids.add(int(token_id))
    return ids


def extract_activations(
    model: Any,
    tokenizer: Any,
    texts: list[str],
    *,
    layers: list[int],
    pooling: str,
    batch_size: int,
    max_length: int,
    desc: str = "Extracting activations",
    show_progress: bool = True,
) -> np.ndarray:
    pass
    if pooling not in SINGLE_VECTOR_POOLINGS:
        msg = (
            f"pooling={pooling!r} keeps several vectors per example; call "
            "extract_token_activations() instead of extract_activations()."
        )
        raise ValueError(msg)
    return extract_token_activations(
        model,
        tokenizer,
        texts,
        layers=layers,
        pooling=pooling,
        batch_size=batch_size,
        max_length=max_length,
        desc=desc,
        show_progress=show_progress,
    ).as_pooled()


def extract_token_activations(
    model: Any,
    tokenizer: Any,
    texts: list[str],
    *,
    layers: list[int],
    pooling: str,
    batch_size: int,
    max_length: int,
    pooling_tokens: int = 1,
    content_spans: Sequence[tuple[int, int] | None] | None = None,
    desc: str = "Extracting activations",
    show_progress: bool = True,
) -> TokenActivations:
    pass
    import numpy as np
    import torch
    from tqdm.auto import tqdm

    if pooling not in (*SINGLE_VECTOR_POOLINGS, "last_n"):
        msg = f"Unknown pooling {pooling!r}; expected 'last', 'mean' or 'last_n'."
        raise ValueError(msg)

    per_example = max(1, pooling_tokens) if pooling == "last_n" else 1
    want_offsets = pooling == "last_n"
    special_ids = _special_token_ids(tokenizer) if want_offsets else set()
    if want_offsets and not getattr(tokenizer, "is_fast", False):
        logger.warning(
            "{} has no fast tokenizer, so character offsets are unavailable: last_n "
            "selection falls back to the attention mask plus special-token ids.",
            type(tokenizer).__name__,
        )

    device = next(model.parameters()).device
    value_batches: list[np.ndarray] = []
    count_batches: list[np.ndarray] = []
    progress = tqdm(total=len(texts), desc=desc, unit="ex", disable=not show_progress or not texts)
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        spans: list[tuple[int, int] | None] = (
            list(content_spans[start : start + batch_size])
            if content_spans is not None
            else [None] * len(batch)
        )
        enc = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
            **({"return_offsets_mapping": True} if want_offsets and tokenizer.is_fast else {}),
        )
                                                                                
                                               
        offset_mapping = enc.pop("offset_mapping", None)
        enc = enc.to(device)
        with torch.no_grad():
                                                                                
                                                                           
            outputs = model(**enc, output_hidden_states=True)
        if getattr(outputs, "hidden_states", None) is None:                                
            msg = f"{type(model).__name__} returned no hidden states; cannot extract activations."
            raise RuntimeError(msg)
                                                                     
        hidden = torch.stack([outputs.hidden_states[i] for i in layers], dim=1)                
        mask = enc["attention_mask"]          

        if pooling == "last_n":
            selections = _selections(
                enc["input_ids"], mask, offset_mapping, spans, special_ids, per_example
            )
            values, counts = _gather_tokens(hidden, selections, per_example)
        else:
            values = _pool(hidden, mask, pooling)[:, :, None, :]                
            counts = torch.ones(hidden.shape[0], dtype=torch.long)
        value_batches.append(values.to(torch.float32).cpu().numpy())
        count_batches.append(counts.cpu().numpy())
        progress.update(len(batch))
    progress.close()

    if not value_batches:                                                
        hidden_size = 0
        return TokenActivations(
            values=np.zeros((0, len(layers), per_example, hidden_size), dtype=np.float32),
            counts=np.zeros(0, dtype=int),
            layers=list(layers),
        )
    result = TokenActivations(
        values=np.concatenate(value_batches, axis=0),
        counts=np.concatenate(count_batches, axis=0).astype(int),
        layers=list(layers),
    )
    if pooling == "last_n":
        logger.info("{}: {}", desc, result.describe())
    return result


def _selections(
    input_ids: Any,
    mask: Any,
    offset_mapping: Any,
    spans: list[tuple[int, int] | None],
    special_ids: set[int],
    count: int,
) -> list[list[int]]:
    pass
    ids = input_ids.tolist()
    masks = mask.tolist()
    offsets = offset_mapping.tolist() if offset_mapping is not None else None
    out: list[list[int]] = []
    for row, (row_ids, row_mask) in enumerate(zip(ids, masks, strict=True)):
        selected = select_content_tokens(
            mask=row_mask,
            count=count,
            offsets=[(int(a), int(b)) for a, b in offsets[row]] if offsets else None,
            special=[int(i) in special_ids for i in row_ids],
            span=spans[row],
        )
        out.append(selected)
    return out


def _gather_tokens(hidden: Any, selections: list[list[int]], count: int) -> tuple[Any, Any]:
    pass
    import torch

    b, layers_n, _, h = hidden.shape
    idx = torch.zeros(b, count, dtype=torch.long, device=hidden.device)
    counts = torch.zeros(b, dtype=torch.long)
    for row, selected in enumerate(selections):
        counts[row] = len(selected)
        for slot, position in enumerate(selected):
            idx[row, slot] = position
    gather_idx = idx.view(b, 1, count, 1).expand(b, layers_n, count, h)
    picked = hidden.gather(dim=2, index=gather_idx)                
                                                                                 
                                                                       
    valid = torch.arange(count, device=hidden.device)[None, :] < counts.to(hidden.device)[:, None]
    return picked * valid[:, None, :, None].to(picked.dtype), counts


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


def describe_selected_tokens(
    tokenizer: Any,
    texts: Sequence[str],
    *,
    pooling_tokens: int,
    max_length: int,
    content_spans: Sequence[tuple[int, int] | None] | None = None,
    limit: int = 3,
) -> str:
    pass
    special_ids = _special_token_ids(tokenizer)
    shown = list(texts)[:limit]
    spans = list(content_spans[:limit]) if content_spans is not None else [None] * len(shown)
    lines: list[str] = []
    for index, text in enumerate(shown):
        enc = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            **({"return_offsets_mapping": True} if getattr(tokenizer, "is_fast", False) else {}),
        )
        ids = list(enc["input_ids"])
        offsets = enc.get("offset_mapping")
        selected = select_content_tokens(
            mask=list(enc["attention_mask"]),
            count=pooling_tokens,
            offsets=[(int(a), int(b)) for a, b in offsets] if offsets else None,
            special=[int(i) in special_ids for i in ids],
            span=spans[index],
        )
        lines.append(f"=== example {index + 1} ===")
        lines.append("Full response:")
        lines.append(text)
        lines.append(f"Selected probe tokens ({len(selected)} of N={pooling_tokens}):")
        for slot, position in enumerate(selected, start=1):
            piece = tokenizer.decode([ids[position]])
            lines.append(f"  token {slot}: {piece!r} (position {position})")
        if not selected:                                
            lines.append("  (none selected!)")
        lines.append("")
    return "\n".join(lines)


                                                                           
                                                                               
       
_TEXT_CONFIG_ATTRS = ("text_config", "language_config", "llm_config", "decoder", "decoder_config")


def _text_config(config: Any) -> Any:
    pass
    queue: list[Any] = []
    getter = getattr(config, "get_text_config", None)
    if callable(getter):
                                                                                
        with contextlib.suppress(AttributeError, KeyError, TypeError):
            queue.append(getter())
    queue.append(config)

    seen: set[int] = set()
    while queue:
        candidate = queue.pop(0)
        if candidate is None or id(candidate) in seen:
            continue
        seen.add(id(candidate))
                                                                              
                                                              
        if isinstance(getattr(candidate, "num_hidden_layers", None), int):
            return candidate
        queue.extend(getattr(candidate, attr, None) for attr in _TEXT_CONFIG_ATTRS)
    return None


def default_layers(model: Any) -> list[int]:
    pass
    text_config = _text_config(model.config)
    if text_config is None:
        msg = (
            f"Could not infer the number of transformer layers from "
            f"{type(model.config).__name__}; set `layers` explicitly in the probe config."
        )
        raise ValueError(msg)
    num_layers = int(text_config.num_hidden_layers)
    return list(range(1, num_layers + 1))


__all__ = [
    "SINGLE_VECTOR_POOLINGS",
    "TokenActivations",
    "build_prompt",
    "build_prompt_with_span",
    "content_span",
    "default_layers",
    "describe_selected_tokens",
    "extract_activations",
    "extract_token_activations",
    "load_model_and_tokenizer",
    "resolve_device",
    "select_content_tokens",
]
