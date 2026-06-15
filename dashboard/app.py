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
        "Validation Queue",
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
        c1.metric("Total observations", s["total_observations"])
        c2.metric("Needs human review", s["needs_human_review"])
        c3.metric("Escalations sent", s["escalations_sent"])
        c4.metric("Verification rate", f"{s['human_verification_rate'] * 100:.0f}%")

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("By severity")
            sev = s["observations_by_severity"]
            if sev:
                st.bar_chart(pd.Series(sev, name="count"))
            else:
                st.info("No observations yet.")
        with col_b:
            st.subheader("By suspected issue")
            iss = s["observations_by_suspected_issue"]
            if iss:
                st.bar_chart(pd.Series(iss, name="count"))
            else:
                st.info("No issues recorded yet.")

    st.subheader("Recent observations")
    recent = api_get("/dashboard/recent-observations", {"limit": 10}) or []
    for o in recent:
        cols = st.columns([1, 4])
        thumb = o.get("thumbnail_url") or o.get("image_url")
        if thumb:
            cols[0].image(thumb, width=120)
        sev = SEVERITY_COLORS.get(o["severity"], "⚪")
        cols[1].markdown(
            f"**#{o['id']}** {sev} `{o['severity']}` · "
            f"{o.get('suspected_issue') or o['plant_condition']} · "
            f"conf {o['confidence'] * 100:.0f}%\n\n{o.get('ai_summary') or ''}"
        )

    st.subheader("Lot risk ranking")
    ranking = api_get("/dashboard/lot-risk-ranking") or []
    if ranking:
        st.dataframe(pd.DataFrame(ranking), use_container_width=True)


# --------------------------------------------------------------------------- #
# Photo gallery
# --------------------------------------------------------------------------- #
elif page == "Photo Gallery":
    st.header("Photo Gallery")
    f1, f2, f3 = st.columns(3)
    severity = f1.selectbox("Severity", ["", "critical", "high", "medium", "low", "unknown"])
    lots = api_get("/lots") or []
    lot_map = {f"{l['lot_code']} (#{l['id']})": l["id"] for l in lots}
    lot_choice = f2.selectbox("Lot", [""] + list(lot_map.keys()))
    issue = f3.text_input("Suspected issue contains")

    params = {"limit": 60}
    if severity:
        params["severity"] = severity
    if lot_choice:
        params["lot_id"] = lot_map[lot_choice]
    if issue:
        params["suspected_issue"] = issue

    photos = api_get("/dashboard/gallery", params) or []
    st.caption(f"{len(photos)} photos")
    cols = st.columns(4)
    for i, o in enumerate(photos):
        with cols[i % 4]:
            thumb = o.get("thumbnail_url") or o.get("image_url")
            if thumb:
                st.image(thumb, use_container_width=True)
            sev = SEVERITY_COLORS.get(o["severity"], "⚪")
            st.caption(
                f"#{o['id']} {sev} {o['severity']} · {o.get('suspected_issue') or '—'}"
            )


# --------------------------------------------------------------------------- #
# Observation detail
# --------------------------------------------------------------------------- #
elif page == "Observation Detail":
    st.header("Observation Detail")
    obs_id = st.number_input("Observation ID", min_value=1, step=1)
    if st.button("Load") or obs_id:
        o = api_get(f"/observations/{int(obs_id)}")
        if o:
            left, right = st.columns([2, 3])
            with left:
                if o.get("image_url"):
                    st.image(o["image_url"], use_container_width=True)
            with right:
                sev = SEVERITY_COLORS.get(o["severity"], "⚪")
                st.subheader(f"#{o['id']} {sev} {o['severity'].upper()}")
                st.write(f"**Suspected issue:** {o.get('suspected_issue') or '—'}")
                st.write(f"**Plant condition:** {o['plant_condition']}")
                st.write(f"**Confidence:** {o['confidence'] * 100:.0f}%")
                st.write(f"**Symptoms:** {', '.join(o.get('visible_symptoms_json') or []) or '—'}")
                st.write(f"**AI summary:** {o.get('ai_summary') or '—'}")
                st.write(f"**Recommended next step:** {o.get('recommended_next_step') or '—'}")
                st.write(f"**Lot:** {o.get('lot_id') or 'unknown'}")
                if o.get("latitude") is not None:
                    st.write(f"**Location:** {o['latitude']}, {o['longitude']}")
                st.write(f"**Human verified:** {o['human_verified']}")
                if o.get("human_correction"):
                    st.info(f"Correction: {o['human_correction']}")

                w = o.get("weather")
                if w:
                    st.markdown("**Weather context**")
                    st.write(
                        f"{w.get('temperature_c')}°C · humidity {w.get('humidity_percent')}% · "
                        f"recent rain {w.get('recent_rain_mm')} mm · "
                        f"heat risk {w.get('heat_risk')} · drought risk {w.get('drought_risk')}"
                    )

                escs = o.get("escalations") or []
                if escs:
                    st.markdown("**Escalation history**")
                    st.dataframe(pd.DataFrame(escs), use_container_width=True)

            st.divider()
            a, b, c = st.columns(3)
            if a.button("✅ Verify"):
                api_patch(f"/observations/{o['id']}/verify", {"human_verified": True})
                st.success("Verified"); st.cache_data.clear()
            correction = b.text_input("Correction note")
            if b.button("💾 Save correction") and correction:
                api_patch(
                    f"/observations/{o['id']}/correct", {"human_correction": correction}
                )
                st.success("Correction saved"); st.cache_data.clear()
            if c.button("⚠️ Escalate"):
                api_post(f"/observations/{o['id']}/escalate")
                st.warning("Escalation triggered"); st.cache_data.clear()


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
            sev = SEVERITY_COLORS.get(z.get("severity"), "⚪")
            cols[1].markdown(
                f"{sev} **{z.get('lot_name') or z.get('zone_name') or 'Zone'}** "
                f"(passport #{z.get('passport_id')}) · status: {z.get('status')}\n\n"
                f"{z.get('latest_observation') or ''}\n\n_Last inspection: {z.get('inspection_date') or '—'}_"
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
            cols[0].caption(f"BEFORE · {b['observed_at']}")
            if b.get("image_url"):
                cols[0].image(b["image_url"], use_container_width=True)
            cols[0].write(f"{b.get('diagnosis')} ({b.get('severity')})")
            cols[1].caption(f"AFTER · {a['observed_at']}")
            if a.get("image_url"):
                cols[1].image(a["image_url"], use_container_width=True)
            cols[1].write(f"{a.get('diagnosis')} ({a.get('severity')})")
            st.info(cmp.get("change_summary"))


# --------------------------------------------------------------------------- #
# Validation Queue
# --------------------------------------------------------------------------- #
elif page == "Validation Queue":
    st.header("🧑‍🌾 Human Validation Queue")
    st.caption("Low-confidence or high-severity AI observations awaiting a human.")
    queue = api_get("/observations/queue/needs-review") or []
    if not queue:
        st.success("Queue empty — nothing awaiting validation.")
    for o in queue:
        with st.container(border=True):
            cols = st.columns([1, 3])
            thumb = o.get("thumbnail_url") or o.get("image_url")
            if thumb:
                cols[0].image(thumb, use_container_width=True)
            sev = SEVERITY_COLORS.get(o["severity"], "⚪")
            cols[1].markdown(
                f"**#{o['id']}** {sev} `{o['severity']}` · conf {o['confidence']*100:.0f}%\n\n"
                f"Diagnosis: **{o.get('diagnosis') or '—'}**\n\n{o.get('ai_summary') or ''}"
            )
            with cols[1]:
                label = st.text_input("Corrected label", key=f"lbl{o['id']}")
                bc = st.columns(3)
                if bc[0].button("✅ Confirm", key=f"cf{o['id']}"):
                    api_patch(f"/observations/{o['id']}/validate", {"status": "confirmed", "validated_by": "dashboard"})
                    st.cache_data.clear(); st.rerun()
                if bc[1].button("✏️ Correct", key=f"co{o['id']}") and label:
                    api_patch(f"/observations/{o['id']}/validate", {"status": "corrected", "corrected_label": label, "validated_by": "dashboard"})
                    st.cache_data.clear(); st.rerun()
                if bc[2].button("🚫 Reject", key=f"rj{o['id']}"):
                    api_patch(f"/observations/{o['id']}/validate", {"status": "rejected", "validated_by": "dashboard"})
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
