(function(){
  'use strict';
  if(!window.currentUser)return;
  const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date=v=>new Date(v).toLocaleString();
  function historyRange(){
    const f=document.getElementById('history-from'),t=document.getElementById('history-to'),err=document.getElementById('history-filter-error');
    if(!f||!t)return null;
    const problem=Validate.dateRange(f.value,t.value);if(err)err.textContent=problem;if(problem)return null;
    const from=f.value?Validate.parseDay(f.value):null,to=t.value?Validate.parseDay(t.value):null;if(to)to.setDate(to.getDate()+1);
    return from||to?{from:from&&from.getTime(),to:to&&to.getTime()}:null;
  }
  function render(){
    const data=QueueStore.read(),active=QueueStore.active(data);
    const set=(id,text)=>{const el=document.getElementById(id);if(el)el.textContent=text;};
    set('current-queue-status',active?active.service.name:'Not in a queue');set('current-position',active?'#'+(active.index+1):'—');set('current-wait',active?active.index*active.service.duration+' min':'—');
    const list=document.getElementById('dashboard-services');if(list)list.innerHTML=data.services.map(s=>`<div class="service-row"><div><div class="service-name">${esc(s.name)}</div><div class="small muted">${s.queue.length} waiting • ${s.open?'Open':'Closed'} • about ${s.queue.length*s.duration} min</div></div>${s.open?`<a class="btn btn-secondary" href="join-queue.html?service=${s.id}">Join</a>`:'<span class="badge">Closed</span>'}</div>`).join('');
    const summary=document.getElementById('notification-summary');if(summary)summary.innerHTML=Notifications.all().slice(0,3).map(n=>`<p>${esc(n.message)}<br><small>${date(n.ts)}</small></p>`).join('')||'<div class="empty">No notifications yet.</div>';
    const select=document.getElementById('service-select');
    if(select){
      const selected=select.value||new URLSearchParams(location.search).get('service')||'';
      select.innerHTML='<option value="">Choose a service</option>'+data.services.map(s=>`<option value="${s.id}">${esc(s.name)}${s.open?'':' (closed)'}</option>`).join('');select.value=selected;
      const s=data.services.find(s=>s.id===Number(select.value));
      set('estimated-wait',s?s.queue.length*s.duration+' minutes':'Select a service');set('people-ahead',s?s.queue.length+' people currently waiting':'');
      const join=document.getElementById('join-btn');join.disabled=!s||!s.open||!!active;join.textContent=active?'Leave current queue before joining':s&&!s.open?'Queue closed':'Join Queue';
      document.getElementById('leave-btn').hidden=!active;
    }
    const status=document.getElementById('queue-status-content');if(status)status.innerHTML=active?`<div class="card queue-hero"><span class="badge">${!active.service.open?'Queue paused':active.index===0?'You’re next':'Waiting'}</span><h2>${esc(active.service.name)}</h2><div>Your current position</div><div class="position">#${active.index+1}</div><div class="stat-value">${active.index*active.service.duration} min</div><p class="muted">${active.service.open?'Your queue updates when staff serves students.':'Staff has paused this queue.'}</p><button class="btn btn-danger" id="leave-status">Leave Queue</button></div>`:'<div class="card empty"><h2>No active queue</h2><p>You are not currently waiting for a service.</p><a class="btn btn-primary" href="join-queue.html">Join a Queue</a></div>';
    const range=historyRange(),history=document.getElementById('history-list');if(history)history.innerHTML=data.history.filter(h=>h.userId===currentUser.id&&(!range||((!range.from||h.date>=range.from)&&(!range.to||h.date<range.to)))).map(h=>`<div class="history-row"><div><div class="service-name">${esc(h.serviceName)}</div><div class="small muted">${date(h.date)}</div></div><span class="badge">${esc(h.outcome)}</span></div>`).join('')||`<div class="empty">${range?'No history in this date range.':'No queue history yet.'}</div>`;
  }
  document.addEventListener('DOMContentLoaded',()=>{
    render();document.getElementById('service-select')?.addEventListener('change',render);
    ['history-from','history-to'].forEach(id=>document.getElementById(id)?.addEventListener('change',render));
    document.getElementById('history-clear')?.addEventListener('click',()=>{document.getElementById('history-from').value='';document.getElementById('history-to').value='';render();});
    document.addEventListener('click',e=>{if(!['join-btn','leave-btn','leave-status'].includes(e.target.id))return;try{if(e.target.id==='join-btn'){QueueStore.change(document.getElementById('service-select').value,'join');location.href='queue-status.html';}else{const a=QueueStore.active();if(a)QueueStore.change(a.service.id,'leave',currentUser.id);}}catch(error){const box=document.getElementById('people-ahead');if(box)box.textContent=error.message;}});
  });
  window.addEventListener('queue-change',render);window.addEventListener('notifications-change',render);
})();
