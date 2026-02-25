# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Shared context between iterations — loop-awareness instructions."""


# ── Loop awareness instruction prepended to every prompt ─────────────────────

LOOP_INSTRUCTION = """\
## IMPORTANT: You are running inside an iterative agent loop.

This is iteration {iteration}{max_iter_str}. You are one of potentially \
multiple agents working on this task across iterations.

**You MUST maintain a flat-file memory system** in the working directory so \
that the next iteration knows what you (and other agents) have already done. \
Follow these rules:

1. At the START of every iteration, read `AGENT_MEMORY.md` if it exists. \
This file contains notes from all previous iterations.
2. At the END of every iteration, APPEND a new section to `AGENT_MEMORY.md` \
with:
   - Which iteration this was and which agent you are
   - What you did (files created, modified, decisions made)
   - What still needs to be done
   - Any problems encountered
3. Format your entry like this:
   ```
   ## Iteration {iteration} — [agent name]
   **Done:** [what you accomplished]
   **Files:** [files created or modified]
   **TODO:** [what remains]
   **Issues:** [any blockers or concerns]
   ```
4. NEVER delete or overwrite previous entries — only APPEND.
5. When the task is fully complete, write `TASK_COMPLETE` at the end of your \
response so the loop knows to stop.

Read AGENT_MEMORY.md NOW before doing anything else, then proceed with the task.
---

"""


def build_loop_prompt(prompt: str, iteration: int, max_iterations: int = 0) -> str:
    """Wrap the user prompt with loop-awareness instructions."""
    max_iter_str = f"/{max_iterations}" if max_iterations else ""
    header = LOOP_INSTRUCTION.format(
        iteration=iteration,
        max_iter_str=max_iter_str,
    )

    if iteration > 1:
        return header + prompt + "\n\nContinue from where the previous iteration left off."
    return header + prompt


def has_completion_signal(text: str, signal: str) -> bool:
    """Check if the output contains the completion signal."""
    return signal.upper() in text.upper()
