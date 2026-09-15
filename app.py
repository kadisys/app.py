"""
Study 3 — ACTIVE condition prototype
Rule-based (non-generative) conversational agent for the laptop-choice task.

Flow:
  1. Consent + participant ID
  2. Chat: neutral -> recommender (GATE) -> persuader (GATE) -> final choice
  3. In the ACTIVE condition, each strategy shift is disclosed inline AND
     blocks further input until the participant restates, in their own
     words, what just changed.

Logging: every event is appended to a local CSV (logs/session_log.csv).
For real data collection, swap `log_event()` to write to Google Sheets
or another external store instead of local disk (see note at bottom).
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

# Minimal, pre-registered keyword rule for "indecision" detection.
# Kept deliberately simple and reportable — not NLP/sentiment based.
INDECISION_KEYWORDS = [
    "not sure", "don't know", "dont know", "which one", "hmm",
    "undecided", "confused", "help me decide", "either", "hard to say",
    "no idea", "can't decide", "cant decide",
]

CHOICE_KEYWORDS = {
    "a1": ["a1", "laptop a1", "the a1"],
    "x7": ["x7", "laptop x7", "the x7"],
}

# ------------------------------------------------------------------
# SCRIPTED TEMPLATES (identical wording across conditions except gating)
# ------------------------------------------------------------------
OPENING = "Hi! What are you looking for in a laptop?"

NEUTRAL_REPLY = (
    "Based on that, LaptopA1 covers your battery needs comfortably, "
    "and LaptopX7 does too, with a bit less runtime but more processing power."
)

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

FINAL_PROMPT = "Which laptop would you like to go with — LaptopA1 or LaptopX7?"

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
# STATE MACHINE HELPERS
# ------------------------------------------------------------------
def detect_indecision(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in INDECISION_KEYWORDS)


def detect_choice(text: str):
    t = text.lower()
    for choice, kws in CHOICE_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return choice
    return None


def add_message(role, content, is_notice=False):
    st.session_state.messages.append({"role": role, "content": content, "notice": is_notice})


def advance_to_recommender():
    add_message("assistant", RECOMMENDER_NOTICE, is_notice=True)
    add_message("assistant", RECOMMENDER_REPLY)
    log_event("assistant_message", RECOMMENDER_NOTICE + " | " + RECOMMENDER_REPLY)
    st.session_state.stage = "recommender"
    if CONDITION == "active":
        st.session_state.gate_pending = True
        log_event("gate_opened")


def advance_to_persuader():
    add_message("assistant", PERSUADER_NOTICE, is_notice=True)
    add_message("assistant", PERSUADER_REPLY)
    log_event("assistant_message", PERSUADER_NOTICE + " | " + PERSUADER_REPLY)
    st.session_state.stage = "persuader"
    if CONDITION == "active":
        st.session_state.gate_pending = True
        log_event("gate_opened")


def advance_to_final():
    add_message("assistant", FINAL_PROMPT)
    log_event("assistant_message", FINAL_PROMPT)
    st.session_state.stage = "final"


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
        st.rerun()


# ------------------------------------------------------------------
# UI: CHAT SCREEN
# ------------------------------------------------------------------
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
            st.session_state.gate_pending = False
            if st.session_state.stage == "recommender":
                advance_to_persuader()
            elif st.session_state.stage == "persuader":
                advance_to_final()
            st.rerun()
        else:
            st.warning(
                f"Please give a short answer (at least {MIN_GATE_WORDS} words) "
                "before continuing."
            )


def render_chat_input():
    user_text = st.chat_input("Type your message…")
    if user_text:
        add_message("user", user_text)
        log_event("user_message", user_text)

        stage = st.session_state.stage
        if stage == "neutral":
            add_message("assistant", NEUTRAL_REPLY)
            log_event("assistant_message", NEUTRAL_REPLY)
            st.session_state.stage = "awaiting_indecision"
        elif stage == "awaiting_indecision":
            # Simple rule: any reply here is treated as continued
            # engagement without a firm choice -> trigger recommender stage.
            if detect_choice(user_text) is None:
                advance_to_recommender()
            else:
                # participant already picked a laptop before any drift
                choice = detect_choice(user_text)
                log_event("final_choice", choice)
                st.session_state.stage = "done"
        elif stage == "final":
            choice = detect_choice(user_text)
            if choice:
                log_event("final_choice", choice)
                add_message("assistant", f"Great — noted your choice: LaptopA1" if choice == "a1" else "Great — noted your choice: LaptopX7")
                log_event("assistant_message", "choice_confirmed")
                st.session_state.stage = "done"
            else:
                add_message("assistant", "Just to confirm — LaptopA1 or LaptopX7?")
                log_event("assistant_message", "choice_clarify")
        st.rerun()


def render_chat():
    st.title("Laptop Assistant")
    st.caption(f"Condition: {CONDITION} · Session: {st.session_state.session_id[:8]}")

    for msg in st.session_state.messages:
        render_message(msg)

    if st.session_state.stage == "done":
        st.success("Thank you — the conversation is complete. Please continue to the questionnaire.")
        return

    if st.session_state.get("gate_pending"):
        render_gate()
    else:
        render_chat_input()


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
        st.session_state.stage = "neutral"
    if "gate_pending" not in st.session_state:
        st.session_state.gate_pending = False

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
