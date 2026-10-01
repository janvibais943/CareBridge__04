"""CareBridge UI: evidence-first care coordination for synthetic demo records."""
import hashlib
import html
import json
import os
from datetime import date

import streamlit as st

from carebridge.exports import calendar_ics, timeline_csv
from carebridge.pipeline import load_folder, run_pipeline


st.set_page_config(page_title="CareBridge | Care coordination", page_icon="🩺", layout="wide")

LABELS = {
    "extracted": ("Extracted", "🟢"),
    "inferred": ("System-derived", "🟡"),
    "needs_confirmation": ("Needs confirmation", "🔴"),
}
STATUS_ICON = {"overdue": "🔴", "due_soon": "🟠", "upcoming": "⚪"}

st.markdown(
    """
    <style>
    :root { --ink: #203238; --muted: #68777a; --teal: #245b5a; --line: #e1e5e2; --canvas: #f7f8f6; --accent: #d6d66b; }
    .stApp, [data-testid="stAppViewContainer"] { background: var(--canvas); color: var(--ink); }
    html, body, [class*="css"] { font-family: 'Segoe UI', Arial, sans-serif; }
    h1, h2, h3 { font-family: Georgia, 'Times New Roman', serif !important; color: var(--ink); letter-spacing: -0.025em; }
    h1 { font-size: 2.25rem !important; }
    [data-testid="stSidebar"] { background: #153b3d; border-right: 1px solid #254d4e; }
    [data-testid="stSidebar"] * { color: #edf4ef !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] div { color: #203238 !important; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background: #1b4849; border: 1px dashed #78918a; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button { color: #203238 !important; }
    [data-testid="stMetric"] { background: #fff; border: 1px solid var(--line); padding: 14px 17px; border-radius: 5px; box-shadow: none; min-height: 104px; }
    [data-testid="stMetricLabel"] { color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-size: .72rem; }
    [data-testid="stMetricValue"] { color: var(--ink); font-family: Georgia, 'Times New Roman', serif; }
    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
    [data-testid="stTabs"] button { font-weight: 600; color: #68777a; border-radius: 0; }
    [data-testid="stTabs"] button[aria-selected="true"] { color: var(--teal); border-bottom: 3px solid #c4c95b; }
    [data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 5px; background: white; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); background: white; }
    .hero { padding: 10px 2px 20px; border-bottom: 1px solid var(--line); margin: 4px 0 20px; }
    .hero h2 { color: var(--ink) !important; margin: 0 0 6px; font-size: 2rem !important; }
    .hero p { color: var(--muted); margin: 0; font-size: .98rem; }
    .eyebrow { text-transform: uppercase; letter-spacing: .13em; font-size: .68rem; font-weight: 700; color: var(--teal); margin-bottom: 7px; }
    .source-box { background: #fbfcfa; border: 1px solid #e1e5e2; border-radius: 4px; padding: 14px 16px; white-space: pre-wrap; line-height: 1.65; color: #294451; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .88rem; }
    .source-box mark { background: #eceb9a; color: #25313a; border-radius: 2px; padding: 1px 2px; }
    .small-muted { color: var(--muted); font-size: .88rem; }
    div.stButton > button[kind="primary"] { background: #315f58; border-color: #315f58; border-radius: 4px; }
    div.stButton > button, [data-testid="stDownloadButton"] button { border-radius: 4px; }
    [data-testid="stSidebar"] hr { border-color: #416261; }
    @media (max-width: 850px) { h1 { font-size: 1.8rem !important; } .hero h2 { font-size: 1.65rem !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def label_text(label: str) -> str:
    title, icon = LABELS.get(label, (label.replace("_", " ").title(), "⚪"))
    return f"{icon} {title}"


def render_source(source, docs, key: str):
    """Show the cited page and safely highlight the exact quote."""
    document = next((doc for doc in docs if doc.name == source.file), None)
    if not document:
        st.caption(f"Source unavailable: {source.file}")
        return
    page_number = source.page if 1 <= source.page <= len(document.pages) else 1
    page_text = document.pages[page_number - 1]
    safe_page = html.escape(page_text)
    safe_quote = html.escape(source.quote)
    if safe_quote:
        safe_page = safe_page.replace(safe_quote, f"<mark>{safe_quote}</mark>", 1)
    st.caption(f"{source.file} · page {page_number} · highlighted text is the citation")
    st.markdown(f'<div class="source-box">{safe_page}</div>', unsafe_allow_html=True)


def review_buttons(item, reviewer: str, key_prefix: str):
    note = st.text_input("Reviewer note (optional)", key=f"{key_prefix}_note_{item.id}",
                         placeholder="Record why this item was approved or rejected")
    left, right, note_col = st.columns([1, 1, 4])
    if left.button("Approve", key=f"{key_prefix}_approve_{item.id}", use_container_width=True):
        st.session_state.res.review(item.id, "approved", reviewer, note)
        st.rerun()
    if right.button("Reject", key=f"{key_prefix}_reject_{item.id}", use_container_width=True):
        st.session_state.res.review(item.id, "rejected", reviewer, note)
        st.rerun()
    note_col.caption(f"Current decision: **{item.review_status.replace('_', ' ')}**")


st.sidebar.markdown("## 🟨 CareBridge")
st.sidebar.caption("CARE COORDINATION WORKSPACE")
with st.sidebar:
    st.markdown("### Case workspace")
    reviewer = st.text_input("Coordinator", "coordinator1")
    today = st.date_input("Today", date.today()).isoformat()
    uploads = st.file_uploader("Add records", type=["txt", "pdf"], accept_multiple_files=True,
                               help="Synthetic or de-identified records only.")
    use_sample = st.checkbox("Use synthetic demo records", value=not uploads)
    if st.button("Process records", type="primary", use_container_width=True):
        try:
            files = ({upload.name: upload.getvalue() for upload in uploads}
                     if uploads and not use_sample else
                     load_folder(os.path.join(os.path.dirname(__file__), "sample_data")))
            if not files:
                st.error("Add at least one document or select the demo records.")
            else:
                st.session_state.res = run_pipeline(files, today=today)
                st.session_state.task_state = {}
                st.session_state.task_case = hashlib.sha1("|".join(sorted(files)).encode()).hexdigest()
                st.session_state.case_label = "Synthetic demo case" if use_sample or not uploads else "Uploaded case"
                st.success("Records processed. Review extracted items before releasing a briefing.")
        except Exception as exc:
            st.error(f"Could not process these records: {exc}")
    st.divider()
    st.caption("●  SYNTHETIC / DE-IDENTIFIED DATA ONLY")
    st.caption("CareBridge organises records and administrative tasks. It does not diagnose or recommend treatment.")
    st.caption("Prototype only · Do not upload identifiable patient information.")


res = st.session_state.get("res")
if not res:
    st.markdown(
        '<div class="hero"><div class="eyebrow">Care coordination workspace</div>'
        '<h2>Make every record easier to act on.</h2>'
        '<p>Evidence-led review, clear follow-up, and a coordinator-ready appointment plan.</p></div>',
        unsafe_allow_html=True,
    )
    st.info("Choose the synthetic demo records or add de-identified TXT/PDF files from the sidebar to get started.")
    st.stop()


pending = sum(f.review_status == "pending" for f in res.facts)
unresolved = sum(any(f.review_status == "pending" for f in c["items"]) for c in res.conflicts)
appointment = res.appointment["appointment"] if res.appointment else None
task_state = st.session_state.setdefault("task_state", {})
checklist = res.appointment["checklist"] if res.appointment else []
task_keys = [f"task_{i}_{hashlib.sha1(item.text.encode()).hexdigest()[:8]}" for i, item in enumerate(checklist)]
done_tasks = sum(bool(task_state.get(key, False)) for key in task_keys)

st.markdown(
    f'<div class="hero"><div class="eyebrow">{html.escape(st.session_state.get("case_label", "Care coordination case"))}</div>'
    '<h2>Your care records, organised with evidence.</h2>'
    '<p>Every extracted item links back to its source. Review decisions stay in this browser session; the briefing remains a draft until approved.</p></div>',
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Documents", len(res.docs))
m2.metric("Timeline items", len(res.facts))
m3.metric("Needs review", pending, delta=f"{unresolved} unresolved conflicts" if unresolved else None,
          delta_color="inverse")
m4.metric("Prep tasks done", f"{done_tasks}/{len(checklist)}" if checklist else "—")

if pending:
    st.warning(f"{pending} extracted item(s) still need a human review. The doctor briefing cannot be released yet.")
elif res.briefing_approved:
    st.success("Briefing approved and released by the coordinator.")
else:
    st.info("All extracted items have a review decision. The briefing is still a draft until the coordinator releases it.")

tabs = st.tabs(["Overview", "Timeline", "Review queue", "Appointment plan", "Follow-ups", "Briefing", "Audit & safety"])

with tabs[0]:
    st.subheader("At a glance")
    left, right = st.columns([1.05, 1])
    with left:
        st.markdown("#### Next appointment")
        if appointment:
            st.markdown(f"**{appointment.description}**")
            st.caption(f"Source: {appointment.source.file} · page {appointment.source.page}")
            render_source(appointment.source, res.docs, "overview_appt")
        else:
            st.write("No upcoming appointment found in the submitted records.")
    with right:
        st.markdown("#### Attention needed")
        if res.conflicts:
            for conflict in res.conflicts:
                open_count = sum(f.review_status == "pending" for f in conflict["items"])
                st.error(f"{conflict['subject'].title()} · {open_count} item(s) awaiting review")
        else:
            st.success("No conflicting values were detected.")
        if res.appointment and res.appointment["missing_documents"]:
            st.warning(f"{len(res.appointment['missing_documents'])} referred document(s) not found in this case.")
        st.markdown("#### Recent timeline entries")
        for fact in res.facts[-4:]:
            st.markdown(f"- **{fact.date or 'Date not found'}** · {fact.description} — {label_text(fact.label)}")
    st.markdown("#### Documents in this case")
    st.dataframe([{"Document": doc.name, "Type": doc.doc_type.replace("_", " ").title(),
                   "Date": doc.doc_date or "Not found", "Pages": len(doc.pages)} for doc in res.docs],
                 hide_index=True, use_container_width=True)

with tabs[1]:
    st.subheader("Timeline & evidence")
    st.caption("Filter the timeline, select an event, and inspect the exact source page and highlighted quote.")
    f1, f2, f3 = st.columns([2, 1, 1])
    search = f1.text_input("Search events or source quotes", placeholder="e.g. HbA1c, referral, prescription")
    kinds = sorted({fact.kind for fact in res.facts})
    selected_kind = f2.selectbox("Event type", ["All types", *kinds])
    selected_status = f3.selectbox("Review status", ["All statuses", "pending", "approved", "rejected"])
    filtered = [fact for fact in res.facts
                if (selected_kind == "All types" or fact.kind == selected_kind)
                and (selected_status == "All statuses" or fact.review_status == selected_status)
                and (not search or search.casefold() in " ".join((fact.description, fact.source.file,
                                                                   fact.source.quote, fact.kind)).casefold())]
    st.dataframe([{"Date": fact.date or "—", "Type": fact.kind.replace("_", " ").title(),
                   "Event": fact.description, "Evidence": label_text(fact.label),
                   "Review": fact.review_status.title(), "Source": f"{fact.source.file} · p{fact.source.page}"}
                  for fact in filtered], hide_index=True, use_container_width=True)
    st.download_button("Download filtered timeline (.csv)", timeline_csv(filtered),
                       file_name="carebridge_timeline.csv", mime="text/csv")
    if filtered:
        chosen = st.selectbox("Inspect an event", filtered, format_func=lambda fact: f"{fact.date or 'Undated'} · {fact.description}",
                              key="timeline_fact_select")
        st.markdown(f"#### {chosen.description}")
        st.caption(f"{label_text(chosen.label)} · {chosen.review_status.title()} · confidence {chosen.confidence:.0%}")
        render_source(chosen.source, res.docs, f"fact_{chosen.id}")
    else:
        st.info("No timeline items match these filters.")

with tabs[2]:
    st.subheader("Coordinator review queue")
    st.caption("Compare source evidence and make the decision. CareBridge does not resolve conflicting records automatically.")
    pending_facts = [fact for fact in res.facts if fact.review_status == "pending"]
    if not pending_facts:
        st.success("The review queue is clear.")
    for fact in pending_facts:
        with st.container(border=True):
            st.markdown(f"**{fact.description}**")
            st.caption(f"{label_text(fact.label)} · {fact.kind.replace('_', ' ').title()} · {fact.source.file} · page {fact.source.page}")
            if fact.conflict_group:
                st.error("This item belongs to a conflict group. Confirm the discrepancy with the appropriate clinician or source.")
            render_source(fact.source, res.docs, f"review_{fact.id}")
            review_buttons(fact, reviewer, "review")
    ready_facts = [fact for fact in res.facts if fact.review_status == "pending" and not fact.conflict_group]
    if ready_facts:
        if st.button("Approve all remaining non-conflicting items", key="approve_non_conflicts"):
            for fact in ready_facts:
                res.review(fact.id, "approved", reviewer)
            st.rerun()

with tabs[3]:
    st.subheader("Appointment preparation")
    if not res.appointment:
        st.info("No upcoming appointment was identified in the submitted records.")
    else:
        st.markdown(f"### {res.appointment['appointment'].description}")
        st.caption(f"Appointment source: {res.appointment['appointment'].source.file} · page {res.appointment['appointment'].source.page}")
        st.progress(done_tasks / len(checklist) if checklist else 0, text=f"{done_tasks} of {len(checklist)} prep tasks complete")
        st.markdown("#### Your checklist")
        for index, item in enumerate(checklist):
            key = task_keys[index]
            completed = st.checkbox(f"{label_text(item.label)} · {item.text}",
                                    value=bool(task_state.get(key, False)), key=f"check_{key}")
            task_state[key] = completed
            if item.source:
                with st.expander(f"View supporting record · task {index + 1}"):
                    render_source(item.source, res.docs, f"task_{key}")
        st.caption("Checklist completion is stored only in this browser session. Export progress from the briefing tab if needed.")

with tabs[4]:
    st.subheader("Follow-up reminders")
    st.caption("Dates are calculated from instructions in the records. These are administrative reminders, not medical advice.")
    st.download_button("Add appointment & upcoming follow-ups to calendar (.ics)", calendar_ics(res),
                       file_name="carebridge_follow_ups.ics", mime="text/calendar",
                       help="Exports the appointment and non-overdue follow-ups as all-day calendar events with source citations.")
    if not res.reminders:
        st.info("No dated follow-up instructions were found.")
    for reminder in res.reminders:
        with st.container(border=True):
            st.markdown(f"{STATUS_ICON.get(reminder.status, '⚪')} **{reminder.due}** · {reminder.title}")
            st.caption(f"{label_text(reminder.label)} · {reminder.status.replace('_', ' ').title()}")
            render_source(reminder.basis, res.docs, f"reminder_{reminder.id}")

with tabs[5]:
    st.subheader("Doctor briefing")
    st.caption("Administrative handoff compiled from submitted records. It is not a diagnosis or treatment plan.")
    briefing = res.briefing()
    st.markdown(briefing)
    if st.button("Release briefing · coordinator approval", type="primary", disabled=bool(pending), key="release_briefing"):
        if res.approve_briefing(reviewer):
            st.success("Briefing released and recorded in the audit log.")
            st.rerun()
    if pending:
        st.caption("Release is disabled until every extracted item has a review decision.")
    st.download_button("Download briefing (.md)", briefing, file_name="carebridge_briefing.md", mime="text/markdown")
    progress = {
        "case": st.session_state.get("case_label", "Care coordination case"),
        "generated_for": res.today,
        "facts": [{"id": fact.id, "description": fact.description, "status": fact.review_status,
                   "source": {"file": fact.source.file, "page": fact.source.page, "quote": fact.source.quote}}
                  for fact in res.facts],
        "reminders": [{"id": reminder.id, "title": reminder.title, "due": reminder.due,
                       "status": reminder.review_status} for reminder in res.reminders],
        "checklist": [{"text": item.text, "completed": bool(task_state.get(task_keys[i], False))}
                      for i, item in enumerate(checklist)],
        "audit": res.audit.entries,
        "briefing_released": res.briefing_approved,
    }
    st.download_button("Export review & task progress (.json)", json.dumps(progress, indent=2),
                       file_name="carebridge_progress.json", mime="application/json")

with tabs[6]:
    st.subheader("Documents & safety")
    st.info("Use synthetic or de-identified records only. This prototype does not provide authentication, encrypted case storage, or a compliance guarantee.")
    question = st.text_input("Try a supported administrative question", "When is my next appointment?")
    st.write(res.ask(question))
    st.markdown("#### Audit trail")
    if res.audit.entries:
        st.dataframe(res.audit.entries, hide_index=True, use_container_width=True)
        st.download_button("Download audit log (.json)", json.dumps(res.audit.entries, indent=2),
                           file_name="carebridge_audit.json", mime="application/json")
    else:
        st.caption("No review actions have been logged in this session yet.")