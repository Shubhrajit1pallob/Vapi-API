"""
Admin UI — SoLAr Study.
Run:  .venv/bin/streamlit run admin/app.py   (from project root)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any, List

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from admin.db import (
    create_patient,
    delete_patient,
    get_active_template,
    list_patient_responses,
    list_patients,
    list_survey_templates,
    save_survey_template,
    set_template_active,
    update_system_prompt,
)
from admin.pdf_extractor import extract_from_pdf, regenerate_system_prompt

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(page_title="SoLAr Admin", layout="wide")
st.title("SoLAr Study — Admin")

# ── Session state ─────────────────────────────────────────────────────
for key, default in [
    ("questions", []),
    ("system_prompt", ""),
    ("extraction_done", False),
    ("saved_template_id", None),
    ("templates", []),
    ("patients", []),
    ("responses", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

tab1, tab2, tab3 = st.tabs(
    ["Survey Templates", "Patients", "Responses"]
)


# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — Survey Templates
# ═══════════════════════════════════════════════════════════════════════
with tab1:

    # ── Upload + Extract ──────────────────────────────────────────────
    st.header("Upload Survey PDF")
    uploaded = st.file_uploader("Choose a PDF", type=["pdf"], label_visibility="collapsed")

    if uploaded and st.button("Extract Questions & Generate Prompt", type="primary"):
        st.session_state.extraction_done = False
        st.session_state.questions = []
        st.session_state.system_prompt = ""
        st.session_state.saved_template_id = None

        log_box = st.empty()
        log_lines: List[str] = []

        def log(msg: str) -> None:
            log_lines.append(f"• {msg}")
            log_box.info("\n".join(log_lines))

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        try:
            with st.spinner("Running…"):
                questions, system_prompt = extract_from_pdf(tmp_path, progress_callback=log)

            st.session_state.questions = questions
            st.session_state.system_prompt = system_prompt
            st.session_state.extraction_done = True
            st.success(f"{len(questions)} questions extracted.")
        except Exception as exc:
            st.error(f"Extraction failed: {exc}")
        finally:
            os.unlink(tmp_path)

    # ── Results ───────────────────────────────────────────────────────
    if st.session_state.extraction_done:
        questions: List[Any] = st.session_state.questions

        st.divider()
        col_q, col_p = st.columns(2)

        # Left: questions preview
        with col_q:
            st.subheader(f"Questions ({len(questions)})")
            import pandas as pd
            df = pd.DataFrame([
                {
                    "ID":      q.get("id", ""),
                    "Section": q.get("section", ""),
                    "Type":    q.get("type", ""),
                    "Question": q.get("Q", "")[:90],
                }
                for q in questions
            ])
            st.dataframe(df, use_container_width=True, height=300)

            with st.expander("JSON preview (first 5)"):
                st.json(questions[:5])

            with st.expander("Full JSON editor"):
                edited_json = st.text_area(
                    "Edit JSON if needed",
                    value=json.dumps(questions, indent=2),
                    height=400,
                    key="json_editor",
                    label_visibility="collapsed",
                )

        # Right: system prompt
        with col_p:
            st.subheader("System Prompt")
            st.caption(
                "This is sent to Vapi. `{{QUESTIONS}}` is replaced with 3 random "
                "questions at the start of each patient session."
            )
            edited_prompt = st.text_area(
                "System prompt (editable)",
                value=st.session_state.system_prompt,
                height=300,
                key="prompt_editor",
                label_visibility="collapsed",
            )
            # Sync edits back to session state
            st.session_state.system_prompt = edited_prompt

            st.markdown("**Additional instructions** *(optional)*")
            extra = st.text_area(
                "e.g. 'Speak in a slower pace' or 'Also ask if they have eaten today'",
                height=80,
                key="extra_instructions",
                label_visibility="collapsed",
            )
            if st.button("Regenerate Prompt with These Instructions"):
                if not extra.strip():
                    st.warning("Type some instructions first.")
                else:
                    with st.spinner("Regenerating…"):
                        try:
                            new_prompt = regenerate_system_prompt(
                                questions=st.session_state.questions,
                                additional_instructions=extra.strip(),
                            )
                            st.session_state.system_prompt = new_prompt
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Regeneration failed: {exc}")

        # ── Save ──────────────────────────────────────────────────────
        st.divider()
        st.subheader("Save Template")
        col_name, col_active, col_btn = st.columns([3, 1, 1])
        with col_name:
            tpl_name = st.text_input("Template name", placeholder="e.g. SoLAr Main Survey v2")
        with col_active:
            set_active = st.checkbox("Set active", value=True)
        with col_btn:
            st.write("")
            save_btn = st.button("Save to Supabase", type="primary")

        if save_btn:
            if not tpl_name.strip():
                st.warning("Enter a template name.")
            else:
                # Use the possibly-edited JSON
                try:
                    qs = json.loads(st.session_state.get("json_editor", json.dumps(questions)))
                except json.JSONDecodeError as exc:
                    st.error(f"JSON error: {exc}")
                    qs = None

                sp = st.session_state.system_prompt
                if not sp.strip():
                    st.warning("System prompt is empty — regenerate it first.")
                elif "{{QUESTIONS}}" not in sp:
                    st.warning(
                        "System prompt doesn't contain `{{QUESTIONS}}`. "
                        "Click Regenerate — the placeholder is required."
                    )
                elif qs is not None:
                    try:
                        row = save_survey_template(
                            name=tpl_name.strip(),
                            questions=qs,
                            system_prompt=sp,
                            set_active=set_active,
                        )
                        st.session_state.saved_template_id = row.get("id")
                        st.success(
                            f"Saved '{row.get('name')}' — "
                            f"v{row.get('version')} | {len(qs)} questions"
                        )
                    except Exception as exc:
                        st.error(f"Save failed: {exc}")

    st.divider()

    # ── Existing templates ────────────────────────────────────────────
    st.subheader("Saved Templates")
    col_r1, col_r2 = st.columns([1, 4])
    with col_r1:
        if st.button("Refresh"):
            try:
                st.session_state.templates = list_survey_templates()
            except Exception as exc:
                st.error(str(exc))

    if st.session_state.templates:
        import pandas as pd
        tdf = pd.DataFrame([
            {
                "Ver.":          t.get("version"),
                "Name":          t.get("name", ""),
                "Active":        "Yes" if t.get("is_active") else "",
                "Has Prompt":    "Yes" if t.get("system_prompt") else "No",
                "Created":       str(t.get("created_at", ""))[:19],
                "ID (prefix)":   str(t.get("id", ""))[:8],
            }
            for t in st.session_state.templates
        ])
        st.dataframe(tdf, use_container_width=True)

        col_a, col_b = st.columns([3, 1])
        with col_a:
            activate_prefix = st.text_input("ID prefix to activate (first 8 chars)")
        with col_b:
            st.write("")
            if st.button("Set Active"):
                if activate_prefix.strip():
                    try:
                        match = [
                            t for t in st.session_state.templates
                            if str(t.get("id", "")).startswith(activate_prefix.strip())
                        ]
                        if not match:
                            st.error("No match found.")
                        else:
                            set_template_active(match[0]["id"])
                            st.success(f"'{match[0].get('name')}' is now active.")
                            st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
    else:
        st.info("Click Refresh or upload a PDF above.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — Patients
# ═══════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Create Patient")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_pid = st.text_input("Patient ID", placeholder="e.g. P-001")
    with col2:
        new_name = st.text_input("Patient Name", placeholder="e.g. Jane Doe")
    with col3:
        st.write("")
        if st.button("Create", type="primary"):
            if not new_pid.strip() or not new_name.strip():
                st.warning("Both fields required.")
            else:
                try:
                    result = create_patient(new_pid.strip(), new_name.strip())
                    pin = result.get("pin", "????")
                    st.success(f"Created {new_name.strip()}")
                    col_pin, col_info = st.columns([1, 2])
                    with col_pin:
                        st.markdown(
                            f"""<div style="background:#1e3a5f;border-radius:12px;
                            padding:20px 28px;text-align:center;font-size:44px;
                            font-weight:bold;letter-spacing:8px;color:#fff;white-space:nowrap">{pin}</div>""",
                            unsafe_allow_html=True,
                        )
                    with col_info:
                        st.info(
                            f"**ID:** {new_pid.strip()}  \n**Name:** {new_name.strip()}  \n\n"
                            "PIN shown once only — share it with the patient now."
                        )
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Error: {exc}")

    st.divider()
    st.subheader("Patient List")
    col_r, col_d1, col_d2 = st.columns([1, 2, 1])
    with col_r:
        if st.button("Refresh", key="ref_pts"):
            try:
                st.session_state.patients = list_patients()
            except Exception as exc:
                st.error(str(exc))

    if st.session_state.patients:
        import pandas as pd
        st.dataframe(
            pd.DataFrame([
                {
                    "Patient ID": p.get("patient_id", ""),
                    "Name":       p.get("name", ""),
                    "Created":    str(p.get("created_at", ""))[:19],
                }
                for p in st.session_state.patients
            ]),
            use_container_width=True,
        )
        with col_d1:
            del_pid = st.text_input("Patient ID to delete", key="del_pid")
        with col_d2:
            st.write("")
            if st.button("Delete", type="secondary"):
                if del_pid.strip():
                    try:
                        delete_patient(del_pid.strip())
                        st.success(f"Deleted '{del_pid.strip()}'.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
    else:
        st.info("Click Refresh.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — Responses
# ═══════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Call Responses")
    col_f, col_r2 = st.columns([3, 1])
    with col_f:
        filter_pid = st.text_input("Filter by Patient ID (blank = all)", key="filter_pid")
    with col_r2:
        st.write("")
        refresh_resp = st.button("Refresh", key="ref_resp")

    if refresh_resp or filter_pid != st.session_state.get("_last_filter_pid", ""):
        st.session_state["_last_filter_pid"] = filter_pid
        try:
            st.session_state.responses = list_patient_responses(
                filter_pid.strip() or None
            )
        except Exception as exc:
            st.error(str(exc))

    if st.session_state.responses:
        import pandas as pd

        # Build question-id → question-text lookup from the active template
        _qmap: dict = {}
        try:
            _tpl = get_active_template()
            if _tpl:
                for q in (_tpl.get("questions") or []):
                    _qmap[q.get("id", "")] = q.get("Q", "")
        except Exception:
            pass

        st.dataframe(
            pd.DataFrame([
                {
                    "Patient ID": r.get("patient_id", ""),
                    "Call ID":    r.get("call_id", "")[:24] + "...",
                    "Date":       str(r.get("created_at", ""))[:19],
                    "# Answers":  len(r.get("answers") or []),
                }
                for r in st.session_state.responses
            ]),
            use_container_width=True,
        )
        for r in st.session_state.responses:
            answers = r.get("answers") or []
            with st.expander(
                f"{r.get('patient_id')} — {str(r.get('call_id',''))[:24]}... "
                f"({len(answers)} answers)"
            ):
                if not answers:
                    st.write("No answers recorded.")
                    continue
                for a in answers:
                    qid = a.get("question_id", "?")
                    ans = a.get("answer", "—")
                    q_text = _qmap.get(qid, "")
                    label = f"{q_text} ({qid})" if q_text else qid
                    st.markdown(f"**{label}:** {ans}")
    else:
        st.info("Click Refresh.")
