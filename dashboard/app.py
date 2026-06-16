"""Agave Field Copilot — Streamlit dashboard.

Reads everything from the FastAPI backend (API_BASE_URL). Shows the overview
metrics, a photo gallery with filters, observation detail, lot views, and a
map of geolocated observations. The dashboard always shows PHOTOS, not just
numbers (product principle #7).
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Agave Field Copilot", page_icon="🌵", layout="wide")

SEVERITY_COLORS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "unknown": "⚪",
}


@st.cache_data(ttl=15)
def api_get(path: str, params: dict | None = None):
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", params=params or {}, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error on {path}: {exc}")
        return None


def api_patch(path: str, payload: dict):
    resp = requests.patch(f"{API_BASE_URL}{path}", json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, payload: dict | None = None):
    resp = requests.post(f"{API_BASE_URL}{path}", json=payload or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


st.sidebar.title("🌵 Agave Field Copilot")
st.sidebar.caption("Field Command Center")
page = st.sidebar.radio(
    "View",
    [
        "Overview",
        "Agave Passports",
        "Map / Zones",
        "Tasks",
        "Alerts",
        "Weather",
        "Before / After",
        "Field Notes Review",
        "Weekly Reports",
        "Photo Gallery",
        "Observation Detail",
        "Lots",
    ],
)
st.sidebar.caption(f"API: {API_BASE_URL}")

health = api_get("/health")
if health:
    st.sidebar.success(
        f"Vision: {health.get('vision_provider')} · "
        f"WhatsApp: {'on' if health.get('whatsapp_enabled') else 'off'}"
    )


# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #
if page == "Overview":
    st.header("Field Overview")
    s = api_get("/dashboard/summary")
    if s and s.get("total_observations", 0) == 0:
        st.info("📭 No observations yet. Send a photo to the Telegram bot to get started — "
                "data will appear here in real time.")
    if s:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total records", s.get("total_observations", 0))
        c2.metric("Photos", s.get("photo_count", 0))
        c3.metric("Pending review", s.get("pending_review", 0))
        c4.metric("Follow-ups needed", s.get("follow_ups_pending", 0))

        st.subheader("By event type")
        evt = s.get("observations_by_event_type") or {}
        if evt:
            st.bar_chart(pd.Series(evt, name="count"))
        else:
            st.info("No records yet.")

    st.subheader("Recent records")
    recent = api_get("/dashboard/recent-observations", {"limit": 10}) or []
    for o in recent:
        cols = st.columns([1, 4])
        thumb = o.get("thumbnail_url") or o.get("image_url")
        if thumb:
            cols[0].image(thumb, width=120)
        fu = " · ⏰ follow-up" if o.get("follow_up_needed") else ""
        note = o.get("manual_note") or "_(no note yet)_"
        cols[1].markdown(
            f"**#{o['id']}** · `{o.get('event_type', 'observation')}`{fu}\n\n"
            f"📝 {note}\n\n_{o.get('observed_at', '')[:16]} · review: {o.get('review_status', 'pending_review')}_"
        )

    st.subheader("Lot activity ranking")
    ranking = api_get("/dashboard/lot-risk-ranking") or []
    if ranking:
        st.dataframe(pd.DataFrame(ranking), use_container_width=True)


# --------------------------------------------------------------------------- #
# Photo gallery
# --------------------------------------------------------------------------- #
elif page == "Photo Gallery":
    st.header("Photo Gallery")
    f1, f2 = st.columns(2)
    lots = api_get("/lots") or []
    lot_map = {f"{l['lot_code']} (#{l['id']})": l["id"] for l in lots}
    lot_choice = f1.selectbox("Lot", [""] + list(lot_map.keys()))
    note_q = f2.text_input("Note contains")

    params = {"limit": 60}
    if lot_choice:
        params["lot_id"] = lot_map[lot_choice]

    photos = api_get("/dashboard/gallery", params) or []
    if note_q:
        photos = [o for o in photos if note_q.lower() in (o.get("manual_note") or "").lower()]
    st.caption(f"{len(photos)} photos")
    cols = st.columns(4)
    for i, o in enumerate(photos):
        with cols[i % 4]:
            thumb = o.get("thumbnail_url") or o.get("image_url")
            if thumb:
                st.image(thumb, use_container_width=True)
            st.caption(
                f"#{o['id']} · `{o.get('event_type', 'observation')}` · "
                f"{(o.get('manual_note') or '—')[:40]}"
            )


# --------------------------------------------------------------------------- #
# Observation detail
# --------------------------------------------------------------------------- #
elif page == "Observation Detail":
    st.header("Field Record Detail")
    obs_id = st.number_input("Record ID", min_value=1, step=1)
    if st.button("Load") or obs_id:
        o = api_get(f"/observations/{int(obs_id)}")
        if o:
            left, right = st.columns([2, 3])
            with left:
                if o.get("image_url"):
                    st.image(o["image_url"], use_container_width=True)
            with right:
                st.subheader(f"Record #{o['id']} · {o.get('event_type', 'observation')}")
                st.write(f"**📝 Note:** {o.get('manual_note') or '—'}")
                st.write(f"**Process / treatment:** {o.get('process_type') or '—'}")
                st.write(f"**Responsible:** {o.get('responsible_person') or '—'}")
                st.write(f"**Date:** {(o.get('observed_at') or '')[:16] or '—'}")
                st.write(f"**Lot:** {o.get('lot_id') or '—'} · **Passport:** {o.get('passport_id') or '—'}")
                if o.get("latitude") is not None:
                    st.write(f"**Location:** {o['latitude']}, {o['longitude']}")
                fu = o.get("follow_up_needed")
                st.write(f"**Follow-up needed:** {'yes' if fu else 'no'}"
                         + (f" (by {(o.get('follow_up_date') or '')[:10]})" if o.get("follow_up_date") else ""))
                st.write(f"**Review status:** {o.get('review_status', 'pending_review')}")
                if o.get("agronomist_notes"):
                    st.info(f"Agronomist notes: {o['agronomist_notes']}")

                w = o.get("weather")
                if w:
                    st.markdown("**Weather context** (at time of record)")
                    st.write(
                        f"{w.get('temperature_c')}°C · humidity {w.get('humidity_percent')}% · "
                        f"recent rain {w.get('recent_rain_mm')} mm"
                    )


# --------------------------------------------------------------------------- #
# Lots
# --------------------------------------------------------------------------- #
elif page == "Lots":
    st.header("Lots")
    lots = api_get("/lots") or []
    for lot in lots:
        with st.expander(f"{lot['lot_code']} (#{lot['id']}) — {lot.get('crop_type')}"):
            obs = api_get(f"/lots/{lot['id']}/observations") or []
            st.write(f"{len(obs)} observations")
            if obs:
                st.write(f"Last inspection: {obs[0].get('observed_at')}")
                df = pd.DataFrame(
                    [
                        {
                            "id": o["id"],
                            "severity": o["severity"],
                            "issue": o.get("suspected_issue"),
                            "observed_at": o.get("observed_at"),
                        }
                        for o in obs
                    ]
                )
                st.dataframe(df, use_container_width=True)
                thumbs = [o for o in obs if o.get("thumbnail_url")]
                if thumbs:
                    cols = st.columns(min(4, len(thumbs)))
                    for i, o in enumerate(thumbs[:8]):
                        cols[i % len(cols)].image(o["thumbnail_url"], use_container_width=True)


# --------------------------------------------------------------------------- #
# Agave Passports
# --------------------------------------------------------------------------- #
elif page == "Agave Passports":
    st.header("🪪 Agave Passports")
    st.caption("The persistent memory of each plant / row / zone / lot.")
    passports = api_get("/api/passports") or []
    if not passports:
        st.info("No passports yet. Send a field photo to create the first one.")
    for p in passports:
        risk = SEVERITY_COLORS.get(p.get("risk_level"), "⚪")
        with st.expander(
            f"{risk} {p['passport_code']} — {p.get('label') or p.get('lot_name') or 'zone'} "
            f"· health: {p.get('health_status')} · risk: {p.get('risk_level')}"
        ):
            detail = api_get(f"/api/passports/{p['id']}") or {}
            cols = st.columns(3)
            cols[0].metric("Observations", len(detail.get("observations", [])))
            cols[1].metric("Open tasks", sum(1 for t in detail.get("tasks", []) if t["status"] in ("open", "in_progress")))
            cols[2].write(
                f"**Last inspection:** {p.get('last_inspection_at') or '—'}\n\n"
                f"**Next inspection:** {p.get('next_inspection_at') or '—'}"
            )
            obs = detail.get("observations", [])
            thumbs = [o for o in obs if o.get("thumbnail_url") or o.get("image_url")]
            if thumbs:
                st.caption("Photo history")
                tc = st.columns(min(5, len(thumbs)))
                for i, o in enumerate(thumbs[:10]):
                    tc[i % len(tc)].image(o.get("thumbnail_url") or o.get("image_url"), use_container_width=True)
            if detail.get("tasks"):
                st.caption("Tasks")
                st.dataframe(pd.DataFrame(detail["tasks"])[["title", "priority", "status", "due_date"]], use_container_width=True)


# --------------------------------------------------------------------------- #
# Map / Zones
# --------------------------------------------------------------------------- #
elif page == "Map / Zones":
    st.header("🗺️ Map / Zone Overview")
    zones = api_get("/api/map/zones") or []
    geo = [z for z in zones if z.get("latitude") is not None]
    if geo:
        df = pd.DataFrame(geo)
        st.map(df[["latitude", "longitude"]])
        for z in geo:
            cols = st.columns([1, 4])
            if z.get("latest_photo"):
                cols[0].image(z["latest_photo"], width=110)
            cols[1].markdown(
                f"📍 **{z.get('lot_name') or z.get('zone_name') or 'Zone'}** "
                f"(passport #{z.get('passport_id')}) · last event: `{z.get('severity')}`\n\n"
                f"📝 {z.get('latest_observation') or '—'}\n\n_Last record: {(z.get('inspection_date') or '—')[:16]}_"
            )
    else:
        st.info("No geolocated zones yet. Send a photo with a shared location.")


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
elif page == "Tasks":
    st.header("✅ Tasks")
    f1, f2 = st.columns(2)
    status = f1.selectbox("Status", ["", "open", "in_progress", "completed", "cancelled"])
    priority = f2.selectbox("Priority", ["", "low", "medium", "high", "urgent"])
    params = {}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority
    tasks = api_get("/api/tasks", params) or []
    overdue = {t["id"] for t in (api_get("/api/tasks/queue/overdue") or [])}
    st.caption(f"{len(tasks)} tasks · {len(overdue)} overdue")
    for t in tasks:
        flag = "🔴 OVERDUE " if t["id"] in overdue else ""
        approval = "" if t["approved"] else "⛔ NEEDS APPROVAL "
        with st.container(border=True):
            st.markdown(
                f"{flag}{approval}**{t['title']}** · `{t['priority']}` · {t['status']} "
                f"· due {t.get('due_date') or '—'} · _{t['source']}_"
            )
            if t.get("description"):
                st.caption(t["description"])
            cols = st.columns(4)
            if not t["approved"] and cols[0].button("Approve", key=f"ap{t['id']}"):
                api_patch(f"/api/tasks/{t['id']}", {"approved": True}); st.cache_data.clear(); st.rerun()
            if cols[1].button("Start", key=f"st{t['id']}"):
                api_patch(f"/api/tasks/{t['id']}", {"status": "in_progress"}); st.cache_data.clear(); st.rerun()
            if cols[2].button("Complete", key=f"cp{t['id']}"):
                api_patch(f"/api/tasks/{t['id']}", {"status": "completed"}); st.cache_data.clear(); st.rerun()
            if cols[3].button("Cancel", key=f"cx{t['id']}"):
                api_patch(f"/api/tasks/{t['id']}", {"status": "cancelled"}); st.cache_data.clear(); st.rerun()


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #
elif page == "Alerts":
    st.header("🚨 Alerts")
    alerts = api_get("/api/alerts") or []
    if not alerts:
        st.success("No alerts. All quiet in the field.")
    for a in alerts:
        sev = SEVERITY_COLORS.get(a.get("severity"), "⚪")
        with st.container(border=True):
            st.markdown(
                f"{sev} **{a['title']}** · `{a['severity']}` · via {a['channel']} "
                f"· {a['delivery_status']}{'  ·  ✅ read' if a['read'] else ''}"
            )
            st.caption(a.get("message") or "")
            st.caption(f"Reason: {a.get('reason') or '—'} · {a.get('created_at')}")
            if not a["read"] and st.button("Mark read", key=f"al{a['id']}"):
                api_patch(f"/api/alerts/{a['id']}/read", {}); st.cache_data.clear(); st.rerun()


# --------------------------------------------------------------------------- #
# Weather
# --------------------------------------------------------------------------- #
elif page == "Weather":
    st.header("🌦️ Weather")
    c1, c2 = st.columns(2)
    lat = c1.number_input("Latitude", value=20.8806, format="%.4f")
    lon = c2.number_input("Longitude", value=-103.8366, format="%.4f")
    ctx = api_get("/api/weather/context", {"lat": lat, "lon": lon}) or {}
    cur = ctx.get("current") or {}
    if not cur:
        st.info("Weather data not available for this location right now.")
    else:
        m = st.columns(4)
        m[0].metric("Temp °C", cur.get("temperature_c"))
        m[1].metric("Humidity %", cur.get("humidity_percent"))
        m[2].metric("Heat risk", cur.get("heat_risk"))
        m[3].metric("Frost risk", cur.get("frost_risk"))
        st.caption(f"Source: {cur.get('source')}")
        if ctx.get("treatment_warning"):
            st.error(f"⚠️ {ctx['treatment_warning']}")
        if ctx.get("forecast"):
            st.subheader("Forecast")
            st.dataframe(pd.DataFrame(ctx["forecast"]), use_container_width=True)


# --------------------------------------------------------------------------- #
# Before / After
# --------------------------------------------------------------------------- #
elif page == "Before / After":
    st.header("📸 Before / After Comparison")
    passports = api_get("/api/passports") or []
    pmap = {f"{p['passport_code']} (#{p['id']})": p["id"] for p in passports}
    choice = st.selectbox("Passport", [""] + list(pmap.keys()))
    if choice:
        cmp = api_get(f"/api/passports/{pmap[choice]}/photos/compare") or {}
        if not cmp.get("comparison_available"):
            st.info("Need at least two photos for this passport to compare.")
        else:
            b, a = cmp["before"], cmp["after"]
            cols = st.columns(2)
            cols[0].caption(f"BEFORE · {(b.get('observed_at') or '')[:16]}")
            if b.get("image_url"):
                cols[0].image(b["image_url"], use_container_width=True)
            cols[0].write(f"📝 {b.get('manual_note') or '—'} · `{b.get('event_type')}`")
            cols[1].caption(f"AFTER · {(a.get('observed_at') or '')[:16]}")
            if a.get("image_url"):
                cols[1].image(a["image_url"], use_container_width=True)
            cols[1].write(f"📝 {a.get('manual_note') or '—'} · `{a.get('event_type')}`")
            st.caption(cmp.get("change_summary"))
            st.caption("Comparison is by human-selected photos — no AI evaluation.")


# --------------------------------------------------------------------------- #
# Field Notes Review (replaces the AI validation queue)
# --------------------------------------------------------------------------- #
elif page == "Field Notes Review":
    st.header("🧑‍🌾 Field Notes Review")
    st.caption("Supervisor review of submitted field records — correct the event type, "
               "add notes, link a process, approve, or request a follow-up photo.")
    EVENT_TYPES = ["observation", "fertilization", "compost", "irrigation", "pest_treatment",
                   "herbicide", "weed_control", "maintenance", "follow_up_inspection"]
    queue = api_get("/observations/queue/review") or []
    if not queue:
        st.success("Queue empty — all field records reviewed.")
    for o in queue:
        with st.container(border=True):
            cols = st.columns([1, 3])
            thumb = o.get("thumbnail_url") or o.get("image_url")
            if thumb:
                cols[0].image(thumb, use_container_width=True)
            cols[1].markdown(
                f"**Record #{o['id']}** · `{o.get('event_type', 'observation')}`"
                f"{' · ⏰ follow-up' if o.get('follow_up_needed') else ''}\n\n"
                f"📝 {o.get('manual_note') or '_(no note)_'}\n\n"
                f"_{(o.get('observed_at') or '')[:16]} · lot {o.get('lot_id') or '—'}_"
            )
            with cols[1]:
                idx = EVENT_TYPES.index(o["event_type"]) if o.get("event_type") in EVENT_TYPES else 0
                new_evt = st.selectbox("Event type", EVENT_TYPES, index=idx, key=f"evt{o['id']}")
                process = st.text_input("Process / treatment", value=o.get("process_type") or "", key=f"pr{o['id']}")
                notes = st.text_input("Agronomist notes", key=f"an{o['id']}")
                bc = st.columns(3)
                if bc[0].button("✅ Approve", key=f"ap{o['id']}"):
                    api_patch(f"/observations/{o['id']}/review", {
                        "event_type": new_evt, "process_type": process or None,
                        "agronomist_notes": notes or None, "approved": True, "reviewed_by": "dashboard"})
                    st.cache_data.clear(); st.rerun()
                if bc[1].button("💾 Save", key=f"sv{o['id']}"):
                    api_patch(f"/observations/{o['id']}/review", {
                        "event_type": new_evt, "process_type": process or None,
                        "agronomist_notes": notes or None, "reviewed_by": "dashboard"})
                    st.cache_data.clear(); st.rerun()
                if bc[2].button("⏰ Request follow-up", key=f"fu{o['id']}"):
                    api_patch(f"/observations/{o['id']}/review", {
                        "event_type": new_evt, "request_followup": True,
                        "agronomist_notes": notes or None, "reviewed_by": "dashboard"})
                    st.cache_data.clear(); st.rerun()


# --------------------------------------------------------------------------- #
# Weekly Reports
# --------------------------------------------------------------------------- #
elif page == "Weekly Reports":
    st.header("📈 Weekly Report")
    if st.button("Generate report now"):
        api_post("/api/reports/weekly/generate"); st.cache_data.clear()
    rep = api_get("/api/reports/weekly") or {}
    if not rep:
        st.info("No report yet. Click 'Generate report now'.")
    else:
        m = st.columns(5)
        m[0].metric("Observations", rep.get("observation_count", 0))
        m[1].metric("Photos", rep.get("photo_count", 0))
        m[2].metric("Open tasks", rep.get("open_tasks", 0))
        m[3].metric("Overdue", rep.get("overdue_tasks", 0))
        m[4].metric("Completed", rep.get("completed_tasks", 0))
        st.subheader("Top issues")
        if rep.get("top_issues"):
            st.dataframe(pd.DataFrame(rep["top_issues"]), use_container_width=True)
        else:
            st.info("Data not available — no issues detected in this period.")
        if rep.get("high_risk_zones"):
            st.subheader("High-risk zones")
            st.dataframe(pd.DataFrame(rep["high_risk_zones"]), use_container_width=True)
        if rep.get("human_validation_corrections"):
            st.subheader("Human corrections (training data)")
            st.dataframe(pd.DataFrame(rep["human_validation_corrections"]), use_container_width=True)
        thumbs = rep.get("thumbnails", [])
        if thumbs:
            st.subheader("Photo thumbnails")
            tc = st.columns(min(6, len(thumbs)))
            for i, url in enumerate(thumbs):
                if url:
                    tc[i % len(tc)].image(url, use_container_width=True)
        st.caption("Satellite/NDVI regional view: planned for Version 2.")
