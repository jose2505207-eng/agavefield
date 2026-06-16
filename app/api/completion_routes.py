"""Mobile worker completion flow.

GET  /work-orders/complete/{token}          -> self-contained mobile HTML page
POST /api/work-orders/complete/{token}/submit -> create immutable ExecutionRecords

The worker never sees the admin dashboard — only their assigned work order.
"""
from __future__ import annotations

import html
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operations import Activity, Product
from app.models.ops_schemas import SubmitPayload
from app.services import execution_service, work_order_service

logger = logging.getLogger("agave.api.completion")
router = APIRouter(tags=["completion"])


def _items_data(db: Session, work_order_id: int) -> list[dict]:
    data = []
    for it in work_order_service.get_items(db, work_order_id):
        activity = db.get(Activity, it.activity_id)
        product = db.get(Product, it.product_id) if it.product_id else None
        data.append({
            "id": it.id,
            "activity_name": activity.activity_name if activity else "Activity",
            "product_name": product.product_name if product else None,
            "instructions": it.instructions or "",
            "planned_surface": it.planned_surface_area_value,
            "planned_surface_unit": it.planned_surface_area_unit,
            "planned_dose": it.planned_dose_value,
            "planned_dose_unit": it.planned_dose_unit,
            "required_photo_count": it.required_photo_count,
            "requires_geolocation": it.requires_geolocation,
            "requires_manual_note": it.requires_manual_note,
        })
    return data


@router.get("/work-orders/complete/{token}", response_class=HTMLResponse)
def completion_page(token: str, db: Session = Depends(get_db)):
    wo = work_order_service.find_by_token(db, token)
    if not wo:
        return HTMLResponse(_ERROR_PAGE, status_code=404)
    items = _items_data(db, wo.id)
    meta = " / ".join(str(x) for x in (wo.field_id, wo.lot_id, wo.zone_id) if x) or "—"
    page = (
        _PAGE
        .replace("__TOKEN__", html.escape(token))
        .replace("__TITLE__", html.escape(wo.title or "Work Order"))
        .replace("__CODE__", html.escape(wo.work_order_code))
        .replace("__META__", html.escape(meta))
        .replace("__DUE__", html.escape(str(wo.due_date or "—")))
        .replace("__NOTE_REQUIRED__", "true" if wo.manual_note_required else "false")
        .replace("__ITEMS__", json.dumps(items))
    )
    return HTMLResponse(page)


@router.post("/api/work-orders/complete/{token}/submit")
def submit_completion(token: str, payload: SubmitPayload, db: Session = Depends(get_db)):
    wo = work_order_service.find_by_token(db, token)
    if not wo:
        raise HTTPException(403, "Invalid or expired link")
    if not payload.items:
        raise HTTPException(400, "No checklist items submitted")
    result = execution_service.submit_execution(db, wo, payload)
    db.commit()
    return result


_ERROR_PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Agave Field</title></head><body style="font-family:system-ui;padding:2rem;text-align:center">
<h2>🌵 Link not valid</h2><p>This work-order link is invalid or has expired. Please contact your agronomist.</p>
</body></html>"""


_PAGE = """<!doctype html><html lang=en><head>
<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Agave Field — __CODE__</title>
<style>
:root{--g:#2e7d32;--bg:#f5f7f4;--card:#fff;--line:#dde3dc;--ink:#1b2a1e}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--g);color:#fff;padding:16px}
header h1{font-size:1.05rem;margin:0 0 4px}header .meta{font-size:.8rem;opacity:.9}
main{padding:14px;max-width:680px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:12px 0}
.card h3{margin:0 0 6px;font-size:1rem}.muted{color:#5b6b5e;font-size:.85rem}
label{display:block;font-size:.8rem;margin:10px 0 4px;font-weight:600}
input,textarea{width:100%;padding:11px;border:1px solid var(--line);border-radius:9px;font-size:1rem}
.row{display:flex;gap:8px}.row>div{flex:1}
button{background:var(--g);color:#fff;border:0;border-radius:10px;padding:13px;font-size:1rem;width:100%;font-weight:600}
button.sec{background:#fff;color:var(--g);border:1px solid var(--g)}
.gps{font-size:.82rem;padding:8px;border-radius:8px;background:#eef3ec;margin:8px 0}
.thumbs{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.thumbs img{width:54px;height:54px;object-fit:cover;border-radius:6px}
.ok{color:var(--g)}.warn{color:#b26a00}
#done{display:none;text-align:center;padding:24px}
</style></head><body>
<header><h1>🌵 __TITLE__</h1><div class=meta>__CODE__ · Field/Lot/Zone: __META__ · Due: __DUE__</div></header>
<main id=app>
<div class=gps id=gpsbox>📍 Location not captured yet.</div>
<button class=sec id=loc type=button>Use my current location</button>
<div id=items></div>
<label>Your name</label><input id=who placeholder="Who completed this work?">
<button id=submit type=button style="margin-top:14px">Submit for review</button>
<p class=muted style="text-align:center">Photos are evidence. A reviewer will approve your submission.</p>
</main>
<div id=done><h2 class=ok>✅ Submitted</h2><p class=muted id=donemsg></p></div>
<script>
const TOKEN="__TOKEN__";
const ITEMS=__ITEMS__, NOTE_REQ=__NOTE_REQUIRED__;
let gps={lat:null,lon:null,acc:null,at:null};
const photos={}; ITEMS.forEach(i=>photos[i.id]=[]);
const $=s=>document.querySelector(s);

function renderItems(){
  $('#items').innerHTML=ITEMS.map(it=>`
   <div class=card>
     <h3>${it.activity_name}</h3>
     ${it.product_name?`<div class=muted>Product: ${it.product_name}</div>`:''}
     ${it.instructions?`<div class=muted>${it.instructions}</div>`:''}
     ${it.planned_surface?`<div class=muted>Planned: ${it.planned_surface} ${it.planned_surface_unit||''}</div>`:''}
     <div class=row>
       <div><label>Actual surface</label><input type=number step=any id="surf_${it.id}"></div>
       <div><label>Unit</label><input id="surfu_${it.id}" value="${it.planned_surface_unit||'ha'}"></div>
     </div>
     <div class=row>
       <div><label>Total product</label><input type=number step=any id="prod_${it.id}"></div>
       <div><label>Unit</label><input id="produ_${it.id}" value="kg"></div>
     </div>
     <label>Note ${it.requires_manual_note?'(required)':''}</label>
     <textarea id="note_${it.id}" rows=2></textarea>
     <label>Photos (need ${it.required_photo_count})</label>
     <input type=file accept="image/*" capture="environment" onchange="up(this,${it.id})">
     <div class=thumbs id="th_${it.id}"></div>
   </div>`).join('');
}
$('#loc').onclick=()=>{
  if(!navigator.geolocation){$('#gpsbox').textContent='Geolocation not supported on this device.';return;}
  $('#gpsbox').textContent='📍 Getting location…';
  navigator.geolocation.getCurrentPosition(p=>{
    gps={lat:p.coords.latitude,lon:p.coords.longitude,acc:p.coords.accuracy,at:new Date().toISOString()};
    $('#gpsbox').innerHTML='📍 <b>Location captured</b> ('+gps.lat.toFixed(5)+', '+gps.lon.toFixed(5)+', ±'+Math.round(gps.acc)+'m)';
  },e=>{$('#gpsbox').textContent='📍 Could not get location: '+e.message;},{enableHighAccuracy:true,timeout:15000});
};
async function up(input,itemId){
  const f=input.files[0]; if(!f)return;
  const fd=new FormData();
  fd.append('token',TOKEN); fd.append('file',f); fd.append('work_order_item_id',itemId);
  if(gps.lat!=null){fd.append('gps_latitude',gps.lat);fd.append('gps_longitude',gps.lon);fd.append('gps_accuracy',gps.acc);fd.append('captured_at',gps.at);}
  try{
    const r=await fetch('/api/photos/upload',{method:'POST',body:fd});
    const j=await r.json();
    if(j.id){photos[itemId].push(j.id);
      const img=document.createElement('img');img.src=j.thumbnail_url||j.file_url;$('#th_'+itemId).appendChild(img);}
  }catch(e){alert('Photo upload failed: '+e);}
  input.value='';
}
$('#submit').onclick=async()=>{
  const items=ITEMS.map(it=>({
    work_order_item_id:it.id,
    actual_surface_area_value:parseFloat($('#surf_'+it.id).value)||null,
    actual_surface_area_unit:$('#surfu_'+it.id).value||null,
    actual_total_product_value:parseFloat($('#prod_'+it.id).value)||null,
    actual_total_product_unit:$('#produ_'+it.id).value||null,
    manual_note:$('#note_'+it.id).value||null,
    evidence_photo_ids:photos[it.id]
  }));
  const body={responsible_person:$('#who').value||null,submitted_by_name:$('#who').value||null,
    gps_latitude:gps.lat,gps_longitude:gps.lon,gps_accuracy:gps.acc,gps_captured_at:gps.at,
    execution_completed_at:new Date().toISOString(),items};
  $('#submit').disabled=true;$('#submit').textContent='Submitting…';
  try{
    const r=await fetch('/api/work-orders/complete/'+TOKEN+'/submit',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(!r.ok){throw new Error(j.detail||'submit failed');}
    const warns=(j.executions||[]).flatMap(e=>e.warnings||[]);
    $('#app').style.display='none';$('#done').style.display='block';
    $('#donemsg').innerHTML=warns.length?('Submitted with notes: '+[...new Set(warns)].join(', ')+'. A reviewer will follow up.'):'Your work was submitted for review. Thank you.';
  }catch(e){$('#submit').disabled=false;$('#submit').textContent='Submit for review';alert('Submit failed: '+e.message);}
};
renderItems();
</script></body></html>"""
