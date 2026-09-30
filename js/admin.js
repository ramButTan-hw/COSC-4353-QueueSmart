/* Admin UI backed by the shared same-browser demo store. */
(function () {
  'use strict';
  if (!window.currentUser) return;
  initNotifications();
  let services = QueueStore.read().services;
  let selected = 1, feedbackTimer;
  const main = document.getElementById('main');
  const dialog = document.getElementById('service-dialog');
  const form = document.getElementById('service-form');
  const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const status = s => `<span class="badge ${s.open ? 'open' : 'closed'}">${s.open ? 'Open' : 'Closed'}</span>`;
  const toggleButton = s => `<button data-action="toggle" data-id="${s.id}">${s.open ? 'Close' : 'Open'} queue</button>`;
  function feedback(message) { clearTimeout(feedbackTimer); document.getElementById('feedback').textContent = message; feedbackTimer = setTimeout(() => document.getElementById('feedback').textContent = '', 4500); }
  function render() {
    const view = ['dashboard','services','queues'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'dashboard';
    document.querySelectorAll('nav a').forEach(a => { const active = a.hash === '#' + view; a.classList.toggle('active', active); if (active) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
    if (view === 'queues') { renderQueue(); return; }
    const overview = view === 'dashboard';
    main.innerHTML = `<div class="page-heading"><div><h1>${overview ? 'Admin dashboard' : 'Service management'}</h1><p class="muted">${overview ? 'Your help desk at a glance.' : 'Manage the support your help desk provides.'}</p></div><button class="primary" data-action="create">+ Create service</button></div>
      ${overview ? `<div class="stats"><div class="stat"><span>Total services</span><strong>${services.length}</strong></div><div class="stat"><span>Students waiting</span><strong>${services.reduce((n,s)=>n+s.queue.length,0)}</strong></div><div class="stat"><span>Open queues</span><strong>${services.filter(s=>s.open).length}</strong></div></div>` : ''}
      <section class="panel"><div class="panel-title"><h2>${overview ? 'Service overview' : 'All services'}</h2><span class="muted">${services.length} services</span></div><div class="table-scroll"><table><thead><tr><th>Service</th><th>${overview ? 'Status' : 'Priority'}</th><th>${overview ? 'Waiting' : 'Duration'}</th><th>Actions</th></tr></thead><tbody>${services.map(s=>`<tr><td><strong>${escape(s.name)}</strong><small>${escape(s.description)}</small></td><td>${overview ? status(s) : `<span class="badge ${s.priority}">${s.priority}</span>`}</td><td>${overview ? `<strong>${s.queue.length}</strong> students` : `${s.duration} min`}</td><td><div class="actions">${overview ? `${toggleButton(s)}<button data-action="queue" data-id="${s.id}">View queue →</button>` : `<button data-action="edit" data-id="${s.id}">Edit service</button>`}</div></td></tr>`).join('')}</tbody></table></div></section>`;
  }
  function renderQueue() {
    const s = services.find(s=>s.id===selected) || services[0]; selected = s.id;
    main.innerHTML = `<div class="page-heading"><div><h1>Queue management</h1><p class="muted">Keep students moving, one service at a time.</p></div></div><div class="queue-tools"><label for="queue-service">Service</label><select id="queue-service">${services.map(item=>`<option value="${item.id}" ${item.id===s.id?'selected':''}>${escape(item.name)}</option>`).join('')}</select>${status(s)}</div>
      <section class="panel"><div class="panel-title"><div><h2>${escape(s.name)}</h2><p class="muted">${s.queue.length} waiting · ${s.duration} min per student</p></div><div class="actions">${toggleButton(s)}<button class="primary" data-action="serve" data-id="${s.id}" ${!s.open || !s.queue.length?'disabled':''}>Serve next user</button></div></div>
      ${!s.open ? '<p class="muted" style="padding:16px 24px">Open this queue to serve the next student.</p>' : ''}
      ${s.queue.length ? `<div class="table-scroll"><table><thead><tr><th>Position</th><th>Student</th><th>Reorder</th><th>Actions</th></tr></thead><tbody>${s.queue.map((user,i)=>`<tr><td><span class="position">${i+1}</span></td><td><strong>${escape(user.name)}</strong>${i===0?'<small>Next in line</small>':''}</td><td><div class="actions"><button aria-label="Move ${escape(user.name)} up" data-action="up" data-id="${s.id}" data-user="${escape(user.id)}" ${i===0?'disabled':''}>↑</button><button aria-label="Move ${escape(user.name)} down" data-action="down" data-id="${s.id}" data-user="${escape(user.id)}" ${i===s.queue.length-1?'disabled':''}>↓</button></div></td><td><button class="danger" data-action="remove" data-id="${s.id}" data-user="${escape(user.id)}">Remove</button></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">No students waiting.<br>This queue is all caught up.</div>'}</section>`;
  }
  function openForm(s) {
    form.reset(); document.getElementById('service-id').value = s ? s.id : '';
    document.getElementById('form-title').textContent = s ? 'Edit service' : 'Create service';
    document.getElementById('service-name').value = s ? s.name : '';
    document.getElementById('description').value = s ? s.description : '';
    document.getElementById('duration').value = s ? s.duration : '';
    document.getElementById('priority').value = s ? s.priority : 'medium';
    form.querySelectorAll('input,textarea,select').forEach(el=>el.setCustomValidity(''));
    dialog.showModal(); document.getElementById('service-name').focus();
  }
  window.addEventListener('queue-change',()=>{services=QueueStore.read().services;render();});
  main.addEventListener('change',e=>{if(e.target.id==='queue-service'){selected=Number(e.target.value);render();}});
  main.addEventListener('click',e=>{
    const button=e.target.closest('button[data-action]');if(!button||button.disabled)return;
    const action=button.dataset.action,s=services.find(s=>s.id===Number(button.dataset.id));
    if(action==='create'){openForm();return;}if(!s)return;
    if(action==='edit'){openForm(s);return;}if(action==='queue'){selected=s.id;location.hash='queues';return;}
    try{QueueStore.change(s.id,action,button.dataset.user);feedback('Queue updated.');}catch(error){feedback(error.message);}
  });
  form.addEventListener('input',event=>event.target.setCustomValidity?.(''));
  form.addEventListener('submit',event=>{
    event.preventDefault();
    const name=document.getElementById('service-name'), description=document.getElementById('description'), duration=document.getElementById('duration');
    name.setCustomValidity(!name.value.trim() ? 'Enter a service name.' : name.value.length > 100 ? 'Service name must be 100 characters or fewer.' : '');
    description.setCustomValidity(description.value.trim()?'':'Enter a description.');
    const priority = document.getElementById('priority');
    priority.setCustomValidity(['low','medium','high'].includes(priority.value) ? '' : 'Choose low, medium, or high priority.');
    duration.setCustomValidity(Number.isSafeInteger(Number(duration.value)) && Number(duration.value)>0 ? '' : 'Enter a positive whole number of minutes.');
    if(!form.reportValidity())return;
    const values={name:name.value.trim(),description:description.value.trim(),duration:Number(duration.value),priority:document.getElementById('priority').value};
    const existing=services.find(s=>s.id===Number(document.getElementById('service-id').value));
    QueueStore.saveService(values,existing?.id);
    dialog.close();render();feedback(existing?'Service updated.':'Service created. Open its queue when ready.');
  });
  document.getElementById('cancel').onclick=()=>dialog.close();document.getElementById('dismiss').onclick=()=>dialog.close();
  window.addEventListener('hashchange',render);render();
})();
