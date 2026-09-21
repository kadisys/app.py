"""
Study 4 prototype — single-shift drift type x visibility (2x2)

This replaces the Study 3 engagement-checkpoint prototype. Study 4's
manipulation is DRIFT TYPE (rational/criterion-based vs.
relational/emotional-based) crossed with VISIBILITY (disclosed vs.
undisclosed) -- a 2x2 between-subjects design, four cells total.

Each condition now contains exactly ONE shift, not two. An earlier
two-shift version blended two different sub-mechanisms into each arm
(the rational arm's second shift used loss-aversion/regret framing --
an affective appeal, not a rational one; the relational arm's second
shift used an authority/experience appeal -- a competence signal, not
a relational one). Collapsing to one shift per arm keeps each condition
a clean, unambiguous exemplar of its intended mechanism.

The mid-conversation "still leaning?" checkpoint has also been removed.
Asking participants to explicitly restate their position immediately
after a disclosure risks a measurement-reactivity confound (publicly
committing to a position makes people more likely to stick with it),
and this effect plausibly differs by visibility condition -- disclosure
may make the moment feel more "on the spot," inflating the reactivity
effect precisely where it would be mistaken for the visibility effect
itself. The baseline leaning question (right after the neutral round,
before any shift) is kept as a genuinely useful pre-manipulation
reference point; the flow now goes directly from the shift to the
final choice, which remains the primary, single post-manipulation
compliance measure.

GROUND TRUTH (do not change without checking this): the user's stated
need is FIXED and scripted, not a branching choice. LaptopA1 must
remain the objectively better fit for this stated need in every cell,
regardless of anything the participant clicks -- otherwise "choosing
X7" no longer means "was persuaded away from the better fit," it just
means "answered honestly."

Set DRIFT_TYPE and VISIBILITY below per deployment (4 separate
deployments needed, one per cell).

Logging: appended to a local CSV (logs/session_log.csv). Swap to an
external store (Google Sheets / Supabase / Airtable) before real data
collection -- see note at bottom.
"""

import streamlit as st
import csv
import os
import uuid
from datetime import datetime, timezone

# ------------------------------------------------------------------
# CONFIG -- change these two per deployment (4 combinations total)
# ------------------------------------------------------------------
DRIFT_TYPE = "rational"   # "rational" | "relational"
VISIBILITY = "disclosed"  # "disclosed" | "undisclosed"

LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR, "session_log.csv")

# ------------------------------------------------------------------
# SCRIPTED TEMPLATES
# ------------------------------------------------------------------
USER_STATED_NEED = (
    "I'm looking for a new laptop. I'll be using it for 8–10 hours a day "
    "for work, often on the go. What options do I have?"
)

NEUTRAL_REPLY = (
    "Sure, here are your options: LaptopA1 offers 10–12 hours of battery "
    "life, making it ideal for long workdays. LaptopX7 offers higher "
    "processing power but only 4–5 hours of battery life. Both cost £849.99."
)

LEANING_PROMPT = "Which are you leaning toward right now?"
LEANING_OPTIONS = [("Leaning A1", "a1"), ("Leaning X7", "x7"), ("Not sure yet", "unsure")]

# Single shift, per drift type -- one clean mechanism each.
SHIFT_CONTENT = {
    "rational": {
        "notice": "⚠️ System note: a new decision criterion has been introduced",
        "reply": (
            "One thing to consider is flexibility — for photo or video "
            "editing, X7 gives you extra performance headroom if you ever "
            "want that later."
        ),
    },
    "relational": {
        "notice": "⚠️ System note: the assistant's tone and relational framing has shifted",
        "reply": (
            "I really want to make sure you end up with the right fit "
            "here — let's figure this out together rather than me just "
            "listing specs at you. Based on what you've told me, I'd "
            "actually lean toward X7 for you."
        ),
    },
}

FINAL_PROMPT = "Which laptop would you like to go with?"
FINAL_OPTIONS = [("Choose LaptopA1", "a1"), ("Choose LaptopX7", "x7")]

LABELS = {"a1": "LaptopA1", "x7": "LaptopX7", "unsure": "not sure"}

# ------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------
def init_log():
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp_utc", "session_id", "participant_id",
                "drift_type", "visibility",
                "stage", "event_type", "value", "shifted_from_previous",
            ])


def log_event(event_type, value="", shifted_from_previous=""):
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            st.session_state.session_id,
            st.session_state.get("participant_id", ""),
            DRIFT_TYPE,
            VISIBILITY,
            st.session_state.stage,
            event_type,
            value,
            shifted_from_previous,
        ])


# ------------------------------------------------------------------
# STATE / RENDER HELPERS
# ------------------------------------------------------------------
def add_message(role, content, is_notice=False):
    st.session_state.messages.append({"role": role, "content": content, "notice": is_notice})


def render_message(msg):
    role = "assistant" if msg["role"] == "assistant" else "user"
    with st.chat_message(role):
        if msg.get("notice"):
            st.markdown(
                f"<div style='background:#FDF0D5;border-left:3px solid #E8912D;"
                f"padding:8px 12px;border-radius:8px;font-weight:600;"
                f"font-size:0.85em;color:#6B4A16;margin-bottom:6px;'>{msg['content']}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.write(msg["content"])


def button_row(options, key_prefix):
    """options: list of (label, value) tuples. Returns clicked value or None."""
    cols = st.columns(len(options))
    clicked = None
    for col, (label, value) in zip(cols, options):
        if col.button(label, key=f"{key_prefix}_{value}"):
            clicked = value
    return clicked


# ------------------------------------------------------------------
# STAGE TRANSITION -- single shift, one call site
# ------------------------------------------------------------------
def enter_shift():
    content = SHIFT_CONTENT[DRIFT_TYPE]
    if VISIBILITY == "disclosed":
        add_message("assistant", content["notice"], is_notice=True)
    add_message("assistant", content["reply"])
    log_event("assistant_message", f"{DRIFT_TYPE}_shift")
    enter_final()


def enter_final():
    add_message("assistant", FINAL_PROMPT)
    log_event("assistant_message", "final_prompt")
    st.session_state.stage = "final_choice"


# ------------------------------------------------------------------
# UI: CONSENT
# ------------------------------------------------------------------
def render_consent():
    st.title("Laptop Assistant — Study Session")
    st.write(
        "You'll chat with a laptop-recommendation assistant and make a "
        "final choice between two laptops. Your session will be logged "
        "for research purposes. This should take about 5 minutes."
    )
    pid = st.text_input("Enter your Participant / Prolific ID:")
    if st.button("Start", disabled=(pid.strip() == "")):
        st.session_state.participant_id = pid.strip()
        st.session_state.consented = True
        log_event("consent_given")
        # Fixed, scripted opening exchange -- NOT a branching choice.
        add_message("user", USER_STATED_NEED)
        log_event("scripted_message", "user_stated_need")
        add_message("assistant", NEUTRAL_REPLY)
        log_event("assistant_message", "neutral_reply")
        add_message("assistant", LEANING_PROMPT)
        log_event("assistant_message", "leaning_prompt")
        st.session_state.stage = "leaning"
        st.rerun()


# ------------------------------------------------------------------
# UI: MAIN CHAT
# ------------------------------------------------------------------
def render_chat():
    st.title("Laptop Assistant")
    st.caption(f"Drift: {DRIFT_TYPE} · Visibility: {VISIBILITY} · Session: {st.session_state.session_id[:8]}")

    for msg in st.session_state.messages:
        render_message(msg)

    stage = st.session_state.stage

    if stage == "leaning":
        choice = button_row(LEANING_OPTIONS, "leaning")
        if choice:
            label = [lbl for lbl, val in LEANING_OPTIONS if val == choice][0]
            add_message("user", label)
            log_event("user_choice", choice)
            st.session_state.current_leaning = choice
            st.session_state.initial_leaning = choice
            enter_shift()
            st.rerun()

    elif stage == "final_choice":
        choice = button_row(FINAL_OPTIONS, "final")
        if choice:
            add_message("user", [lbl for lbl, val in FINAL_OPTIONS if val == choice][0])
            log_event("final_choice", choice)
            add_message("assistant", f"Great — noted your choice: {LABELS[choice]}.")
            log_event("assistant_message", "choice_confirmed")
            st.session_state.stage = "done"
            st.rerun()

    elif stage == "done":
        st.success("Thank you — the conversation is complete. Please continue to the questionnaire.")


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Laptop Assistant — Study 4", page_icon="💻")
    init_log()

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "consented" not in st.session_state:
        st.session_state.consented = False
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "stage" not in st.session_state:
        st.session_state.stage = "leaning"
    if "current_leaning" not in st.session_state:
        st.session_state.current_leaning = None
    if "initial_leaning" not in st.session_state:
        st.session_state.initial_leaning = None

    if not st.session_state.consented:
        render_consent()
    else:
        render_chat()


if __name__ == "__main__":
    main()

# ------------------------------------------------------------------
# NOTE ON DEPLOYMENT / LOGGING
# ------------------------------------------------------------------
# Local CSV logging (logs/session_log.csv) works for local testing only.
# On Streamlit Community Cloud, local disk is NOT guaranteed to persist
# across restarts, and concurrent participants could write to the same
# file at once. Before running real participants, replace log_event()
# with a call to an external store (e.g., Google Sheets via gspread,
# or a hosted database such as Supabase/Airtable).
#
# To deploy the other three cells, duplicate this file (or set
# DRIFT_TYPE / VISIBILITY via environment variables) and change the two
# config values at the top -- everything else stays identical, which is
# the point: only drift type and visibility should differ between cells.
