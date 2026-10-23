"""Builders for Laya /v1/systemone answer payloads (shape from docs/http-api.md)."""


def choice(probs):
    best = max(probs, key=probs.get)
    return {"type": "choice", "choice": best, "probabilities": dict(probs),
            "confidence": 0.5, "answer_confidence": probs[best], "action": {"act_probability": 1.0}}


def score(probs, levels):
    expected = sum(i * p for i, p in enumerate(probs))
    return {"type": "score", "score": expected,
            "legend": {str(i): text for i, text in enumerate(levels)},
            "probabilities": {str(i): p for i, p in enumerate(probs)},
            "confidence": 0.3, "answer_confidence": max(probs), "action": {"act_probability": 1.0}}


def noul(p):
    return {"type": "noul", "noul": p, "confidence": max(p, 1 - p), "answer_confidence": max(p, 1 - p),
            "action": {"act_probability": 1.0}}


def result(**answers):
    return {"model": "laya-rl-agent", "answers": answers, "usage": {"input_tokens": 10, "output_tokens": 0},
            "routing": {"model": "multilingual"}}
