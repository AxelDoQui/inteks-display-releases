// Web de la cuenta: una sola página, sin librerías. Todo lo que viene del servidor se
// inserta con textContent, nunca con innerHTML.
export const PAGINA = `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>InTeks Cuenta</title>
<style>
:root{--bg:#0f1115;--card:#181b22;--tx:#e8eaf0;--mut:#9aa3b2;--ac:#4f8cff;--ok:#2ecc71;--mal:#ff5d5d;--bd:#2a2f3a}
@media (prefers-color-scheme:light){:root{--bg:#f4f6fa;--card:#fff;--tx:#161a22;--mut:#5b6575;--bd:#dde2ea}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,sans-serif}
main{max-width:720px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}p.s{color:var(--mut);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px;margin-bottom:16px}
input,button{font:inherit;border-radius:8px;border:1px solid var(--bd);padding:9px 12px;background:var(--bg);color:var(--tx)}
button{background:var(--ac);border-color:var(--ac);color:#fff;cursor:pointer}button.g{background:none;color:var(--tx);border-color:var(--bd)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.pc{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-top:1px solid var(--bd);flex-wrap:wrap}
.pc:first-child{border-top:0}.pin{font:600 26px/1 ui-monospace,monospace;letter-spacing:4px}.mut{color:var(--mut);font-size:13px}
.on{color:var(--ok)}.off{color:var(--mal)}
</style></head><body><main>
<h1>InTeks Cuenta</h1><p class="s">Tus PCs con acceso remoto.</p>
<div class="card"><div class="row"><input id="n" placeholder="nombre (tienda1)" maxlength="30" autocomplete="off">
<button id="add">Añadir PC</button></div><p class="mut" id="msg"></p></div>
<div class="card" id="lista"></div>
<script>
const $=(i)=>document.getElementById(i);
const msg=(t,e)=>{$("msg").textContent=t;$("msg").style.color=e?"var(--mal)":"var(--mut)"};
async function cargar(){
  const r=await fetch("/api/pcs");const d=await r.json();const l=$("lista");l.textContent="";
  if(!d.pcs||!d.pcs.length){l.textContent="Aún no hay ningún PC.";return}
  for(const p of d.pcs){
    const f=document.createElement("div");f.className="pc";const a=document.createElement("div");
    const t=document.createElement("strong");t.textContent=p.nombre;a.appendChild(t);
    const s=document.createElement("div");s.className="mut";
    if(p.estado==="activo"){
      s.textContent=p.hostname+" · ";const e=document.createElement("span");
      e.className=p.enLinea?"on":"off";e.textContent=p.enLinea===null?"estado desconocido":p.enLinea?"en línea":"sin conexión";s.appendChild(e);
      a.appendChild(s);
    }else{
      s.textContent=p.pin?"Pendiente de enlazar. PIN válido unos minutos:":"PIN caducado";a.appendChild(s);
      if(p.pin){const n=document.createElement("div");n.className="pin";n.textContent=p.pin;a.appendChild(n)}
    }
    const b=document.createElement("button");b.className="g";b.textContent="Quitar";
    b.onclick=async()=>{if(!confirm("¿Quitar "+p.nombre+"? Su dirección dejará de funcionar."))return;
      const x=await fetch("/api/pcs/"+encodeURIComponent(p.nombre),{method:"DELETE"});const j=await x.json();msg(j.ok?"Quitado.":j.error,!j.ok);cargar()};
    f.appendChild(a);f.appendChild(b);l.appendChild(f)}
}
$("add").onclick=async()=>{const nombre=$("n").value.trim().toLowerCase();
  const r=await fetch("/api/pcs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nombre})});
  const d=await r.json();if(!d.ok){msg(d.error,true);return}msg("Listo: escribe el PIN en el panel del PC (Ajustes → Acceso remoto).");$("n").value="";cargar()};
cargar();setInterval(cargar,15000);
</script></main></body></html>`;
