"""
refine_insight.py
-----------------
Your weekly review tool. Takes Claude's draft insights and lets you
edit them to match your voice — saving the result as a training example.

HOW TO USE:
  python refine_insight.py             # Review the next unreviewed draft
  python refine_insight.py --all       # Review all pending drafts one by one
  python refine_insight.py --list      # Show all examples and their status
  python refine_insight.py --stats     # Show library stats and improvement over time
  python refine_insight.py --id 003    # Review or re-edit a specific example

THE WORKFLOW (takes 3-5 minutes per example):
  1. Script shows you the financial context + Claude's draft
  2. Draft opens in Notepad for you to edit
  3. You rewrite whatever feels off — tone, phrasing, emphasis, word choice
  4. Save and close Notepad
  5. Script saves your version as the final training example
  6. Done — that's one example added to the library

WHAT TO EDIT:
  - Make it sound like you, not a generic AI
  - Be more direct where Claude hedges
  - Add your signature phrases
  - Cut jargon, add context you know about the client's industry
  - Sharpen the "What to Watch" bullets — make them more specific
  - Keep the same three-section structure

AFTER 5+ EXAMPLES:
  Claude will start using your examples automatically. You'll notice
  the drafts need less editing over time — that's the system working.
"""

import sys
import os
import json
import pathlib
import subprocess
import datetime
import statistics
import tempfile

ROOT = pathlib.Path(__file__).parent
EXAMPLES_DIR = ROOT / "insight_examples"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _all_examples() -> list[pathlib.Path]:
    """All example folders, sorted by number."""
    if not EXAMPLES_DIR.exists():
        return []
    return sorted(
        [d for d in EXAMPLES_DIR.iterdir() if d.is_dir() and d.name[0].isdigit()],
        key=lambda d: d.name
    )


def _pending_examples() -> list[pathlib.Path]:
    """Folders with a draft but no final yet."""
    return [
        d for d in _all_examples()
        if (d / "draft.txt").exists() and not (d / "final.txt").exists()
    ]


def _complete_examples() -> list[pathlib.Path]:
    """Folders with both draft and final."""
    return [
        d for d in _all_examples()
        if (d / "draft.txt").exists() and (d / "final.txt").exists()
    ]


def _load_meta(folder: pathlib.Path) -> dict:
    meta_path = folder / "metadata.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _update_meta_has_final(folder: pathlib.Path):
    meta_path = folder / "metadata.json"
    meta = _load_meta(folder)
    meta["has_final"]    = True
    meta["finalized_at"] = datetime.datetime.now().isoformat()
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _open_in_editor(text: str) -> str:
    """
    Write text to a temp file, open it in Notepad, wait for user to
    save and close, then return the edited content.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    # Open in Notepad (Windows) and wait for it to close
    try:
        subprocess.run(["notepad.exe", tmp_path], check=True)
    except Exception:
        # Fallback: print path and wait for manual confirmation
        print(f"\n  Could not open Notepad automatically.")
        print(f"  Please open and edit this file:")
        print(f"  {tmp_path}")
        input("\n  Press Enter when you've saved and closed the file...")

    edited = pathlib.Path(tmp_path).read_text(encoding="utf-8")
    pathlib.Path(tmp_path).unlink(missing_ok=True)
    return edited


def _divider(char="-", width=66):
    print(char * width)


def _show_context(folder: pathlib.Path):
    """Print the financial context for this example."""
    meta = _load_meta(folder)
    input_path = folder / "input.json"

    print()
    _divider("=")
    print(f"  EXAMPLE: {folder.name}")
    _divider("=")

    if meta:
        print(f"  Client   : {meta.get('client_id', 'unknown')}")
        print(f"  Period   : {meta.get('period', 'unknown')}")
        print(f"  Industry : {meta.get('industry', 'n/a')}")
        rev = meta.get('revenue', 0)
        mrg = meta.get('net_margin', 0)
        if rev: print(f"  Revenue  : ${float(rev):,.0f}")
        if mrg: print(f"  Margin   : {float(mrg):.1f}%")
    print()


def _show_draft(folder: pathlib.Path):
    """Print Claude's draft."""
    draft_path = folder / "draft.txt"
    if not draft_path.exists():
        print("  (no draft found)")
        return
    draft = draft_path.read_text(encoding="utf-8")
    _divider()
    print("  CLAUDE'S DRAFT:")
    _divider()
    print()
    for line in draft.strip().split("\n"):
        print(f"  {line}")
    print()


def _show_diff(draft: str, final: str):
    """Print a simple before/after comparison."""
    d_words = len(draft.split())
    f_words = len(final.split())
    delta   = f_words - d_words
    sign    = "+" if delta >= 0 else ""
    print(f"\n  Words: {d_words} (draft) -> {f_words} (final)  [{sign}{delta}]")
    if final.strip() == draft.strip():
        print("  No changes made — draft accepted as-is.")
    else:
        # Show first differing line
        d_lines = draft.strip().split("\n")
        f_lines = final.strip().split("\n")
        changes = sum(1 for a, b in zip(d_lines, f_lines) if a != b)
        changes += abs(len(d_lines) - len(f_lines))
        print(f"  Lines changed: ~{changes}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list():
    """Show all examples with their status."""
    all_ex = _all_examples()
    if not all_ex:
        print("\n  No examples yet. Generate a report first.")
        print("  python generate_report.py")
        return

    print()
    _divider("=")
    print(f"  INSIGHT EXAMPLES LIBRARY  ({len(all_ex)} total)")
    _divider("=")
    print(f"  {'ID':<6} {'Client':<28} {'Period':<14} {'Status'}")
    _divider()

    complete = 0
    for folder in all_ex:
        meta     = _load_meta(folder)
        has_fin  = (folder / "final.txt").exists()
        status   = "COMPLETE" if has_fin else "needs review"
        cid      = meta.get("client_id", folder.name[4:])[:26]
        period   = meta.get("period", "")[:13]
        ex_id    = meta.get("example_id", folder.name[:3])
        print(f"  {ex_id:<6} {cid:<28} {period:<14} {status}")
        if has_fin:
            complete += 1

    _divider()
    pending = len(all_ex) - complete
    print(f"  Complete: {complete}   Pending review: {pending}")

    if pending:
        print(f"\n  Review next: python refine_insight.py")
    print()


def cmd_stats():
    """Show library statistics and what improvement level you're at."""
    all_ex     = _all_examples()
    complete   = _complete_examples()
    n_complete = len(complete)

    print()
    _divider("=")
    print("  INSIGHT LIBRARY STATS")
    _divider("=")
    print(f"  Total examples    : {len(all_ex)}")
    print(f"  Complete (trained): {n_complete}")
    print(f"  Pending review    : {len(all_ex) - n_complete}")
    print()

    # Training level
    if n_complete == 0:
        level = "Not started"
        tip   = "Generate a report, then run this script to review the draft."
    elif n_complete < 5:
        level = "Building library"
        tip   = f"Add {5 - n_complete} more to activate few-shot learning."
    elif n_complete < 10:
        level = "Few-shot active"
        tip   = "Claude is using your examples. Keep adding more."
    elif n_complete < 20:
        level = "Good — voice emerging"
        tip   = f"Add {20 - n_complete} more for strong consistency."
    else:
        level = "Strong — system is well-trained"
        tip   = "Maintain quality by reviewing 1-2 examples per month."

    print(f"  Training level    : {level}")
    print(f"  Tip               : {tip}")
    print()

    # Word count analysis — did your edits get shorter or longer?
    if n_complete >= 3:
        word_changes = []
        for folder in complete:
            try:
                draft = (folder / "draft.txt").read_text(encoding="utf-8")
                final = (folder / "final.txt").read_text(encoding="utf-8")
                word_changes.append(len(final.split()) - len(draft.split()))
            except Exception:
                pass

        if word_changes:
            avg_change = statistics.mean(word_changes)
            direction  = "shorter" if avg_change < -5 else ("longer" if avg_change > 5 else "similar length")
            print(f"  Your edits tend to make responses {direction}")
            print(f"  Avg word count change: {avg_change:+.0f} words per example")
    print()

    # Industry breakdown
    industries = {}
    for folder in complete:
        meta = _load_meta(folder)
        ind  = meta.get("industry", "untagged") or "untagged"
        industries[ind] = industries.get(ind, 0) + 1

    if industries:
        print("  Training examples by industry:")
        for ind, count in sorted(industries.items(), key=lambda x: -x[1]):
            bar = "#" * count
            print(f"    {ind[:30]:<32} {bar} ({count})")
    print()


def cmd_review(folder: pathlib.Path, allow_skip: bool = True) -> bool:
    """
    Review one example. Returns True if completed, False if skipped.
    """
    _show_context(folder)
    _show_draft(folder)

    # Ask what to do
    print("  What would you like to do?")
    print("  1 - Edit in Notepad (refine Claude's draft into your voice)")
    print("  2 - Accept draft as-is (it's already good)")
    if allow_skip:
        print("  3 - Skip for now")
    print()

    choice = input("  Enter 1, 2, or 3: ").strip()

    if choice == "3" and allow_skip:
        print("  Skipped.\n")
        return False

    draft = (folder / "draft.txt").read_text(encoding="utf-8") \
            if (folder / "draft.txt").exists() else ""

    if choice == "2":
        final_text = draft
        print("  Draft accepted as-is.")
    else:
        print()
        print("  Notepad will open with Claude's draft.")
        print("  Edit it to match your voice, then save and close Notepad.")
        print()
        input("  Press Enter to open Notepad...")
        final_text = _open_in_editor(draft)

    # Save final
    (folder / "final.txt").write_text(final_text, encoding="utf-8")
    _update_meta_has_final(folder)
    _show_diff(draft, final_text)

    n_complete = len(_complete_examples())
    print(f"\n  Saved. Library now has {n_complete} complete example(s).")

    # Milestone messages
    if n_complete == 5:
        print("  Few-shot learning is now ACTIVE — Claude will use your examples!")
    elif n_complete == 10:
        print("  10 examples — voice consistency should be noticeably better now.")
    elif n_complete == 20:
        print("  20 examples — strong training library. System is well-calibrated.")
    elif n_complete % 10 == 0:
        print(f"  {n_complete} examples — great library depth.")
    print()
    return True


def cmd_review_all():
    """Review all pending drafts one by one."""
    pending = _pending_examples()
    if not pending:
        print("\n  No pending examples to review.")
        print("  Run a report to generate new drafts: python generate_report.py")
        return

    print(f"\n  {len(pending)} draft(s) to review.\n")
    done = 0
    for folder in pending:
        completed = cmd_review(folder, allow_skip=True)
        if completed:
            done += 1
        cont = input("  Review next? [Y/n]: ").strip().lower()
        if cont == "n":
            break

    print(f"\n  Done. Reviewed {done} example(s) this session.")


def cmd_review_next():
    """Review the single oldest unreviewed draft."""
    pending = _pending_examples()
    if not pending:
        print("\n  No pending examples.")
        print("  Generate a report first: python generate_report.py")
        n_complete = len(_complete_examples())
        if n_complete > 0:
            print(f"\n  You have {n_complete} complete example(s) in the library.")
            print("  Claude is already learning from them.")
        return
    cmd_review(pending[0], allow_skip=False)


def cmd_review_id(example_id: str):
    """Review or re-edit a specific example by its ID."""
    target = None
    for folder in _all_examples():
        meta = _load_meta(folder)
        if meta.get("example_id") == example_id or folder.name.startswith(example_id):
            target = folder
            break

    if not target:
        print(f"\n  Example '{example_id}' not found.")
        print("  Run: python refine_insight.py --list")
        return

    if (target / "final.txt").exists():
        print(f"\n  Example {example_id} already has a final version.")
        redo = input("  Re-edit it? [y/N]: ").strip().lower()
        if redo != "y":
            return

    cmd_review(target, allow_skip=False)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args:
        # Default: review the next pending draft
        cmd_review_next()

    elif "--list" in args:
        cmd_list()

    elif "--stats" in args:
        cmd_stats()

    elif "--all" in args:
        cmd_review_all()

    elif "--id" in args:
        idx = args.index("--id")
        if idx + 1 >= len(args):
            print("  Usage: python refine_insight.py --id 003")
        else:
            cmd_review_id(args[idx + 1])

    else:
        print(f"  Unknown argument: {args[0]}")
        print(__doc__)


if __name__ == "__main__":
    main()
