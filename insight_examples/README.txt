INSIGHT EXAMPLES — Few-Shot Training Library
============================================

Each subfolder is one training example. They are numbered and named automatically.

FOLDER STRUCTURE:
  001_riverside_home_goods_2025-04/
    input.json      The financial data that was sent to Claude (auto-saved)
    draft.txt       Claude's first response (auto-saved)
    final.txt       YOUR edited version (you create this via refine_insight.py)
    metadata.json   Industry, revenue range, tags used for smart matching

HOW TO ADD AN EXAMPLE:
  1. Run any report — input.json and draft.txt are saved automatically
  2. Run: python refine_insight.py
  3. It shows you the draft, you edit it to match your voice, save it
  4. That's one training example done

HOW MANY DO YOU NEED:
  5  examples  — system starts using your voice
  10 examples  — noticeable improvement
  20 examples  — strong style consistency
  30+ examples — very close to indistinguishable from your own writing

EDITING TIPS:
  - Don't rewrite everything — just fix what feels off
  - Change the tone, word choice, level of directness
  - Add your signature phrases and ways of framing things
  - Keep the same structure (WHAT HAPPENED / WHY IT MATTERS / WHAT TO WATCH)
  - The more specific your edits, the faster the system learns

The system picks the 3 most relevant examples for each new report
based on industry and financial profile — not just the most recent ones.
