"""Deterministic transport fixture for the complete structured editorial protocol."""

import json


def response_for(payload, plan, usage=None):
    name = payload["response_format"]["json_schema"]["name"]
    supplied = json.loads(payload["messages"][1]["content"])
    if name == "editorial_v2":
        output = plan
    elif name == "rewrite_v3":
        output = {"events": []}
        for event in supplied["events"]:
            sentences = [
                {"text": evidence["fragment"], "evidence": [evidence]}
                for evidence in event["evidence"]
            ]
            output["events"].append(
                {"event_id": event["event_id"], "digest": sentences, "post": sentences}
            )
    else:
        output = {
            "sentences": [
                {"sentence_id": row["sentence_id"], "entailed": True, "evidence": row["evidence"]}
                for row in supplied["sentences"]
            ]
        }
    return {
        "model": "fixture-model",
        "choices": [{"message": {"content": json.dumps(output, ensure_ascii=False)}}],
        **({"usage": usage} if usage is not None else {}),
    }
