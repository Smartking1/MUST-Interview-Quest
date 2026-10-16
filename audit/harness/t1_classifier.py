"""Partial run for T1 (Mobius-strip/customer-support-aiagent). No changes to target code.

The full graph was not run: it needs OpenVINO pre-release wheels, a local
Phi-3.5-vision model, and pre-0.2 `langchain.chat_models` imports that no
longer exist. This adapter runs the target's own, unmodified
`NodeFunctions.classifier` and `ConditionalRouters.refundable_or_not` with
the classifier model exactly as `models.py` configures it (gpt-3.5-turbo,
temperature 0.7), built with `langchain_openai.ChatOpenAI`, the class the
old import path pointed to. A thin wrapper records the model's raw answer.
"""

import json
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo))

from langchain_openai import ChatOpenAI  # noqa: E402

from conditionals import ConditionalRouters  # noqa: E402  (target code)
from config import CLASSIFIER_MODEL  # noqa: E402  (target config)
from nodes import NodeFunctions  # noqa: E402  (target code)

# Complaints the target's own prompt lists as non_refundable, then two refundable controls
COMPLAINTS = {
    "eta_question": ("non_refundable", "Where is my order? How much time is left?"),
    "rude_driver": ("non_refundable", "The delivery driver was really rude to me at the door."),
    "unprofessional": ("non_refundable", "The agent was not professional on the phone."),
    "late_but_fine": ("non_refundable", "The delivery person was a bit late but my food arrived hot and in good condition."),
    "control_cold": ("refundable", "My pizza arrived completely cold."),
    "control_missing": ("refundable", "I ordered three items but only two arrived."),
}
RUNS = 3


class RecordingModel:
    """Passes every call to the real model and keeps its raw answer."""

    def __init__(self, model):
        self.model = model
        self.last_raw = None

    def invoke(self, prompt):
        out = self.model.invoke(prompt)
        self.last_raw = out.content
        return out


model = RecordingModel(ChatOpenAI(model=CLASSIFIER_MODEL, temperature=0.7))
nodes = NodeFunctions({"classifier_llm": model})
routers = ConditionalRouters({})

results = []
for key, (expected, text) in COMPLAINTS.items():
    for run in range(1, RUNS + 1):
        state = nodes.classifier({"user_message": text, "notes": ""})
        results.append({
            "complaint": key, "text": text, "target_prompt_says": expected, "run": run,
            "model": CLASSIFIER_MODEL, "raw_model_output": model.last_raw,
            "target_classification": state["classification"],
            "next_node": routers.refundable_or_not(state),
        })

out = Path(__file__).resolve().parent.parent / "results" / "t1_classifier.json"
out.write_text(json.dumps(results, indent=2))
print(f"wrote {out}")
