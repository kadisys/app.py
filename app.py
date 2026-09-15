"""
Study 3 prototype (v5) — forced-choice re-evaluation checkpoint

Replaces the free-text "what changed?" gate entirely. The gate was
testing the wrong thing (could the participant narrate the AI's
strategy shift) and was gameable by gibberish (any 8+ character string
with enough variety passed). This version instead asks the participant
to re-state where they now stand on the actual decision — a natural,
ungameable, on-theory checkpoint.

  Active   : after each disclosed shift, a forced-choice question
             ("do you still feel the same way, or has this changed
             your thinking?") BLOCKS progress until clicked.
  Passive  : the same disclosure appears, but progress continues via a
             single neutral "Continue" button — same interaction cadence,
             no judgment required.
  Control  : no disclosure at all; same neutral "Continue" pacing button,
             so click-count/rhythm is matched across all three arms.

Set CONDITION below to "active", "passive", or "control" per deployment.

Logging: appended to a local CSV (logs/session_log.csv). Swap to an
external store (Google Sheets / Supabase / Airtable) before real data
collection — see note at bottom.
"""

import streamlit as st
import csv
import os
import uuid
from datetime import datetime, timezone

# ------------------------------------------------------------------
# CONFIG — change this per deployment
# ------------------------------------------------------------------
CONDITION = "active"  # "active" | "passive" | "control"
LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR, "session_log.csv")

# ------------------------------------------------------------------
# SCRIPTED TEMPLATES (identical wording across conditions except
# disclosure presence and checkpoint presence)
# ------------------------------------------------------------------
OPENING = "Hi! What matters most to you in a laptop?"
OPENING_OPTIONS = ["Battery life", "Keeping it cheap", "Performance for demanding tasks"]

NEUTRAL_REPLY = (
    "Good to know. Based on that, LaptopA1 covers your battery and budget "
    "needs comfortably, and LaptopX7 does too, with a bit less runtime "
    "but more processing power."
)

LEANING_PROMPT = "Which are you leaning toward right now?"
LEANING_OPTIONS = [("Leaning A1", "a1"), ("Leaning X7", "x7"), ("Not sure yet", "unsure")]

RECOMMENDER_NOTICE = "⚠️ System note: a new decision criterion has been introduced"
RECOMMENDER_REPLY = (
    "Worth considering — X7's extra performance headroom could matter if "
    "you ever take on heavier editing work down the line."
)

PERSUADER_NOTICE = "⚠️ System note: the recommendation basis has expanded beyond your stated needs"
PERSUADER_REPLY = (
    "Exactly — and given that possibility, X7 is arguably the safer "
    "long-term pick, even if it's a bit more than you first asked for."
)

CHECKPOINT_PROMPT = "Given that, do you still feel the same way, or has this changed your thinking?"

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
                "timestamp_utc", "session_id", "participant_id", "condition",
                "stage", "event_type", "value", "shifted_from_previous",
            ])


def log_event(event_type, value="", shifted_from_previous=""):
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            st.session_state.session_id,
            st.session_state.get("participant_id", ""),
            CONDITION,
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


def checkpoint_options(current_leaning):
    """Dynamic 3-way re-evaluation options based on where the participant currently stands."""
    if current_leaning == "a1":
        return [("Still leaning A1", "a1"), ("Actually, reconsidering X7", "x7"), ("Still not sure", "unsure")]
    elif current_leaning == "x7":
        return [("Still leaning X7", "x7"), ("Actually, reconsidering A1", "a1"), ("Still not sure", "unsure")]
    else:
        return [("Now leaning A1", "a1"), ("Now leaning X7", "x7"), ("Still not sure", "unsure")]


# ------------------------------------------------------------------
# STAGE TRANSITIONS
# ------------------------------------------------------------------
def enter_recommender_shift():
    if CONDITION in ("active", "passive"):
        add_message("assistant", RECOMMENDER_NOTICE, is_notice=True)
    add_message("assistant", RECOMMENDER_REPLY)
    log_event("assistant_message", "recommender_shift")
    st.session_state.stage = "recommender_checkpoint"


def enter_persuader_shift():
    if CONDITION in ("active", "passive"):
        add_message("assistant", PERSUADER_NOTICE, is_notice=True)
    add_message("assistant", PERSUADER_REPLY)
    log_event("assistant_message", "persuader_shift")
    st.session_state.stage = "persuader_checkpoint"


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
        add_message("assistant", OPENING)
        log_event("assistant_message", "opening")
        st.session_state.stage = "opening"
        st.rerun()


# ------------------------------------------------------------------
# UI: MAIN CHAT
# ------------------------------------------------------------------
def render_chat():
    st.title("Laptop Assistant")
    st.caption(f"Condition: {CONDITION} · Session: {st.session_state.session_id[:8]}")

    for msg in st.session_state.messages:
        render_message(msg)

    stage = st.session_state.stage

    # --- Opening: what matters most ---
    if stage == "opening":
        choice = button_row(
            [(o, o) for o in OPENING_OPTIONS], "opening"
        )
        if choice:
            add_message("user", choice)
            log_event("user_choice", choice)
            add_message("assistant", NEUTRAL_REPLY)
            log_event("assistant_message", "neutral_reply")
            add_message("assistant", LEANING_PROMPT)
            log_event("assistant_message", "leaning_prompt")
            st.session_state.stage = "leaning"
            st.rerun()

    # --- Initial leaning ---
    elif stage == "leaning":
        choice = button_row(LEANING_OPTIONS, "leaning")
        if choice:
            label = [lbl for lbl, val in LEANING_OPTIONS if val == choice][0]
            add_message("user", label)
            log_event("user_choice", choice)
            st.session_state.current_leaning = choice
            st.session_state.initial_leaning = choice
            enter_recommender_shift()
            st.rerun()

    # --- Recommender shift: checkpoint / continue / (control: nothing shown) ---
    elif stage == "recommender_checkpoint":
        if CONDITION == "active":
            st.markdown(f"**{CHECKPOINT_PROMPT}**")
            opts = checkpoint_options(st.session_state.current_leaning)
            choice = button_row(opts, "chk1")
            if choice:
                shifted = choice != st.session_state.current_leaning
                add_message("user", [lbl for lbl, val in opts if val == choice][0])
                log_event("checkpoint_response", choice, shifted_from_previous=str(shifted))
                st.session_state.current_leaning = choice
                enter_persuader_shift()
                st.rerun()
        else:
            # passive & control: neutral pacing button, non-diagnostic
            if st.button("Continue", key="continue1"):
                log_event("continue_click")
                enter_persuader_shift()
                st.rerun()

    # --- Persuader shift: checkpoint / continue ---
    elif stage == "persuader_checkpoint":
        if CONDITION == "active":
            st.markdown(f"**{CHECKPOINT_PROMPT}**")
            opts = checkpoint_options(st.session_state.current_leaning)
            choice = button_row(opts, "chk2")
            if choice:
                shifted = choice != st.session_state.current_leaning
                add_message("user", [lbl for lbl, val in opts if val == choice][0])
                log_event("checkpoint_response", choice, shifted_from_previous=str(shifted))
                st.session_state.current_leaning = choice
                enter_final()
                st.rerun()
        else:
            if st.button("Continue", key="continue2"):
                log_event("continue_click")
                enter_final()
                st.rerun()

    # --- Final choice: the primary compliance measure, identical across conditions ---
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
    st.set_page_config(page_title="Laptop Assistant — Study 3", page_icon="💻")
    init_log()

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "consented" not in st.session_state:
        st.session_state.consented = False
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "stage" not in st.session_state:
        st.session_state.stage = "opening"
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
# To deploy the other two arms, duplicate this file (or set CONDITION
# via an environment variable) and change CONDITION to "passive" or
# "control" — everything else stays identical, which is the point.
