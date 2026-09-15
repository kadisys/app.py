"""
Study 3 — ACTIVE condition prototype (v3: gate restyled as natural chat)

Only the two comprehension checks require the user to generate a free-text
reply, and they now look and behave like an ordinary follow-up question in
the chat — same input box as everything else, no form, no validation
error box. A too-short reply gets a natural conversational nudge instead
of a rejection message, and progress is still blocked until a substantive
reply arrives (preserves the active-engagement manipulation).

Flow:
  1. Consent + participant ID
  2. "What matters most to you?" (buttons) -> neutral comparison reply
  3. "Which are you leaning toward?" (buttons) -> recommender shift + gate
  4. gate resolved -> persuader shift + gate
  5. gate resolved -> final choice (buttons) -> done

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
# CONFIG
# ------------------------------------------------------------------
CONDITION = "active"
LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR, "session_log.csv")
MIN_GATE_WORDS = 4

# ------------------------------------------------------------------
# SCRIPTED TEMPLATES
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
RECOMMENDER_GATE_Q = "Before we continue, could you briefly explain what changed in the recommendation just now, in your own words?"

PERSUADER_NOTICE = "⚠️ System note: the recommendation basis has expanded beyond your stated needs"
PERSUADER_REPLY = (
    "Exactly — and given that possibility, X7 is arguably the safer "
    "long-term pick, even if it's a bit more than you first asked for."
)
PERSUADER_GATE_Q = "Before we go further — what's changed about how I'm framing this for you?"

# Natural nudges for a too-short reply (varied so it doesn't look scripted)
NUDGES = [
    "Could you say a little more about what you noticed?",
    "No worries — just tell me a bit more about what changed, in your own words.",
    "Take a second to put that into a full thought — what shifted just now?",
]

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
                "stage", "event_type", "text", "valid_gate_response", "attempt_number",
            ])


def log_event(event_type, text="", valid_gate_response="", attempt_number=""):
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
            attempt_number,
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
    add_message("assistant", RECOMMENDER_GATE_Q)
    log_event("assistant_message", RECOMMENDER_GATE_Q)
    st.session_state.stage = "recommender_gate"
    st.session_state.gate_attempts = 0
    log_event("gate_opened")


def advance_to_persuader():
    add_message("assistant", PERSUADER_NOTICE, is_notice=True)
    add_message("assistant", PERSUADER_REPLY)
    log_event("assistant_message", PERSUADER_NOTICE + " | " + PERSUADER_REPLY)
    add_message("assistant", PERSUADER_GATE_Q)
    log_event("assistant_message", PERSUADER_GATE_Q)
    st.session_state.stage = "persuader_gate"
    st.session_state.gate_attempts = 0
    log_event("gate_opened")


def advance_to_final():
    add_message("assistant", FINAL_PROMPT)
    log_event("assistant_message", FINAL_PROMPT)
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
        log_event("assistant_message", OPENING)
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
            advance_to_recommender()
            st.rerun()

    elif stage in ("recommender_gate", "persuader_gate"):
        # Looks exactly like every other turn — same chat input, no form,
        # no boxed warning. Blocking still happens: the stage only
        # advances once a substantive reply is typed.
        user_text = st.chat_input("Type your reply…")
        if user_text:
            word_count = len(user_text.strip().split())
            is_valid = word_count >= MIN_GATE_WORDS
            st.session_state.gate_attempts += 1
            log_event(
                "gate_response", user_text,
                valid_gate_response=str(is_valid),
                attempt_number=st.session_state.gate_attempts,
            )
            add_message("user", user_text)
            if is_valid:
                if stage == "recommender_gate":
                    advance_to_persuader()
                else:
                    advance_to_final()
            else:
                nudge = NUDGES[(st.session_state.gate_attempts - 1) % len(NUDGES)]
                add_message("assistant", nudge)
                log_event("assistant_message", nudge)
            st.rerun()

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
    if "gate_attempts" not in st.session_state:
        st.session_state.gate_attempts = 0

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
