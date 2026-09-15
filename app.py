"""
Study 3 — ACTIVE condition prototype (v4: participation filter, not a
comprehension validator)

IMPORTANT DESIGN NOTE — read before changing the filter below:
The gate's job is to enforce the OPPORTUNITY and REQUIREMENT to generate
an explanation. It is NOT meant to verify that the explanation reflects
genuine comprehension — no live text filter can do that reliably, and
trying to make it do so (e.g. keyword-matching the "correct" answer)
would risk teaching participants the intended interpretation rather than
measuring whether they arrived at it themselves.

So: `is_substantive_response()` below only blocks obvious non-participation
(empty/trivial replies, keyboard mashing). It does NOT judge whether the
reply is correct or shows real recognition. That judgment happens later,
offline, via manual content-coding of every logged gate_response for
recognition of the disclosed shift (0 = no recognition, 1 = partial,
2 = clear recognition), by two raters with reported inter-rater agreement.

CRITICAL: recognition coding is an OUTCOME/manipulation-check variable —
it must never be used to decide inclusion/exclusion. Only participation
(did they type a substantive, non-trivial reply) gates continuation and
is used for exclusion decisions. Excluding participants whose free-text
reply shows no recognition would remove exactly the cases where the
active-engagement manipulation may have failed to produce its intended
effect — discarding them would artificially inflate the apparent effect
of the manipulation.

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

# Participation filter thresholds — deliberately modest. This blocks
# obvious non-responses; it does not and cannot verify comprehension.
MIN_GATE_CHARS = 8
TRIVIAL_RESPONSES = {
    "ok", "okay", "yes", "no", "sure", "idk", "nothing", "fine",
    "sure thing", "n/a", "na", "none", "not sure",
}


def is_substantive_response(text: str) -> bool:
    """
    Basic non-response filter (NOT a comprehension check).
    Rejects: empty/too-short strings, common trivial replies, and
    strings dominated by one or two repeated characters (keyboard mash
    or repeated punctuation, e.g. "aaaaaaaa", "......").
    Everything else — including brief-but-real or off-target answers —
    is accepted here and left for offline recognition coding.
    """
    cleaned = text.strip().lower()
    if len(cleaned) < MIN_GATE_CHARS:
        return False
    if cleaned in TRIVIAL_RESPONSES:
        return False
    letters_only = cleaned.replace(" ", "")
    if letters_only and len(set(letters_only)) <= 2:
        return False
    return True

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
RECOMMENDER_GATE_Q = "Just to make sure I'm following — what do you think changed in my recommendation just now?"

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
                "stage", "event_type", "text", "passed_participation_filter",
                "attempt_number", "recognition_code",
            ])


def log_event(event_type, text="", passed_participation_filter="", attempt_number="", recognition_code=""):
    # recognition_code is left blank at collection time — it is filled in
    # later during offline manual coding (0/1/2, see module docstring).
    # It must never be computed live or used to gate the conversation.
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
            passed_participation_filter,
            attempt_number,
            recognition_code,
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
        # advances once a reply clears the basic participation filter.
        # This filter does NOT judge correctness/recognition — see the
        # module docstring. Recognition is coded offline, afterward.
        user_text = st.chat_input("Type your reply…")
        if user_text:
            is_valid = is_substantive_response(user_text)
            st.session_state.gate_attempts += 1
            log_event(
                "gate_response", user_text,
                passed_participation_filter=str(is_valid),
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
