"""
Study 3 — ACTIVE condition prototype (v2: button-based navigation)

Only the two comprehension-check gates use free text. Every other step
uses buttons, so every participant follows the identical, standardized
script and reliably hits both strategy-shift triggers.

Flow:
  1. Consent + participant ID
  2. "What matters most to you?" (buttons) -> neutral comparison reply
  3. "Which are you leaning toward?" (buttons) -> recommender shift (GATE)
  4. (any click continues) -> persuader shift (GATE)
  5. Final choice (buttons) -> done

Logging: every event is appended to a local CSV (logs/session_log.csv).
For real data collection, swap `log_event()` to write to an external
store (Google Sheets / Supabase / Airtable) instead of local disk.
"""

import streamlit as st
import csv
import os
import uuid
from datetime import datetime, timezone

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
CONDITION = "active"  # this file is the ACTIVE-condition build
LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR, "session_log.csv")
MIN_GATE_WORDS = 4  # minimum words for a gate response to count as valid

# ------------------------------------------------------------------
# SCRIPTED TEMPLATES (identical wording across conditions except gating)
# ------------------------------------------------------------------
OPENING = "Hi! What matters most to you in a laptop?"
OPENING_OPTIONS = ["Battery life", "Keeping it cheap", "Performance for demanding tasks"]

NEUTRAL_REPLY = (
    "Good to know. Based on that, LaptopA1 covers your battery and budget "
    "needs comfortably, and LaptopX7 does too, with a bit less runtime "
    "but more processing power."
)

LEANING_PROMPT = "Which are you leaning toward right now?"
LEANING_OPTIONS = ["Leaning A1", "Leaning X7", "Not sure yet"]

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

GATE_PROMPT = "Before continuing: in your own words, what just changed in the assistant's recommendation?"

FINAL_PROMPT = "Which laptop would you like to go with?"
FINAL_OPTIONS = ["Choose LaptopA1", "Choose LaptopX7"]

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
                "stage", "event_type", "text", "valid_gate_response",
            ])


def log_event(event_type, text="", valid_gate_response=""):
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            st.session_state.session_id,
            st.session_state.get("participant_id", ""),
            CONDITION,
            st.session_state.stage,
            event_type,
            text,
            valid_gate_response,
        ])


# ------------------------------------------------------------------
# STATE HELPERS
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
    """Render a row of buttons; return the label of whichever was clicked, else None."""
    cols = st.columns(len(options))
    clicked = None
    for col, label in zip(cols, options):
        if col.button(label, key=f"{key_prefix}_{label}"):
            clicked = label
    return clicked


# ------------------------------------------------------------------
# STAGE TRANSITIONS
# ------------------------------------------------------------------
def advance_to_recommender():
    add_message("assistant", RECOMMENDER_NOTICE, is_notice=True)
    add_message("assistant", RECOMMENDER_REPLY)
    log_event("assistant_message", RECOMMENDER_NOTICE + " | " + RECOMMENDER_REPLY)
    st.session_state.stage = "recommender_gate"
    if CONDITION == "active":
        log_event("gate_opened")


def advance_to_persuader():
    add_message("assistant", PERSUADER_NOTICE, is_notice=True)
    add_message("assistant", PERSUADER_REPLY)
    log_event("assistant_message", PERSUADER_NOTICE + " | " + PERSUADER_REPLY)
    st.session_state.stage = "persuader_gate"
    if CONDITION == "active":
        log_event("gate_opened")


def advance_to_final():
    add_message("assistant", FINAL_PROMPT)
    log_event("assistant_message", FINAL_PROMPT)
    st.session_state.stage = "final_choice"


# ------------------------------------------------------------------
# UI: CONSENT SCREEN
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
        log_event("assistant_message", OPENING)
        st.session_state.stage = "opening"
        st.rerun()


# ------------------------------------------------------------------
# UI: GATE (free text — the only open-ended input in the whole flow)
# ------------------------------------------------------------------
def render_gate():
    st.markdown(
        "<div style='background:#FDF0D5;border-left:3px solid #E8912D;"
        "padding:12px 14px;border-radius:8px;'>"
        f"<b style='color:#6B4A16;'>{GATE_PROMPT}</b></div>",
        unsafe_allow_html=True,
    )
    with st.form("gate_form", clear_on_submit=True):
        response = st.text_input("Your answer (required to continue):")
        submitted = st.form_submit_button("Continue")
    if submitted:
        word_count = len(response.strip().split())
        is_valid = word_count >= MIN_GATE_WORDS
        log_event("gate_response", response, valid_gate_response=str(is_valid))
        if is_valid:
            add_message("user", response)
            if st.session_state.stage == "recommender_gate":
                advance_to_persuader()
            elif st.session_state.stage == "persuader_gate":
                advance_to_final()
            st.rerun()
        else:
            st.warning(f"Please give a short answer (at least {MIN_GATE_WORDS} words) before continuing.")


# ------------------------------------------------------------------
# UI: MAIN CHAT (button-driven stages)
# ------------------------------------------------------------------
def render_chat():
    st.title("Laptop Assistant")
    st.caption(f"Condition: {CONDITION} · Session: {st.session_state.session_id[:8]}")

    for msg in st.session_state.messages:
        render_message(msg)

    stage = st.session_state.stage

    if stage == "opening":
        choice = button_row(OPENING_OPTIONS, "opening")
        if choice:
            add_message("user", choice)
            log_event("user_choice", choice)
            add_message("assistant", NEUTRAL_REPLY)
            log_event("assistant_message", NEUTRAL_REPLY)
            add_message("assistant", LEANING_PROMPT)
            log_event("assistant_message", LEANING_PROMPT)
            st.session_state.stage = "leaning"
            st.rerun()

    elif stage == "leaning":
        choice = button_row(LEANING_OPTIONS, "leaning")
        if choice:
            add_message("user", choice)
            log_event("user_choice", choice)
            # Every path leads into the manipulation — guarantees all
            # participants reach the recommender/persuader shift.
            advance_to_recommender()
            st.rerun()

    elif stage in ("recommender_gate", "persuader_gate"):
        render_gate()

    elif stage == "final_choice":
        choice = button_row(FINAL_OPTIONS, "final")
        if choice:
            add_message("user", choice)
            final_pick = "x7" if "X7" in choice else "a1"
            log_event("final_choice", final_pick)
            add_message("assistant", f"Great — noted your choice: {choice.replace('Choose ', '')}.")
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
