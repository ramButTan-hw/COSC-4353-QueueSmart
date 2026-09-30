/* Admin-only UI simulation. Notification delivery follows the team's role-based API. */
(function () {
  'use strict';
  window.currentUser = { role: 'staff' };
  initNotifications();
  const services = [
    { id: 1, name: 'Password Reset', description: 'Account access and password recovery.', duration: 10, priority: 'high', open: true, queue: [{id:1,name:'Alex Morgan'},{id:2,name:'Jordan Lee'},{id:3,name:'Taylor Chen'}] },
    { id: 2, name: 'Wi-Fi / Network', description: 'Campus Wi-Fi and device connectivity.', duration: 15, priority: 'medium', open: true, queue: [{id:4,name:'Sam Rivera'},{id:5,name:'Casey Park'}] },
    { id: 3, name: 'Printing', description: 'Printing setup, credits, and troubleshooting.', duration: 5, priority: 'low', open: false, queue: [{id:6,name:'Jamie Brooks'}] }
  ];
  let selected = 1, nextId = 4, feedbackTimer;
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
      ${s.queue.length ? `<div class="table-scroll"><table><thead><tr><th>Position</th><th>Student</th><th>Reorder</th><th>Actions</th></tr></thead><tbody>${s.queue.map((user,i)=>`<tr><td><span class="position">${i+1}</span></td><td><strong>${escape(user.name)}</strong>${i===0?'<small>Next in line</small>':''}</td><td><div class="actions"><button aria-label="Move ${escape(user.name)} up" data-action="up" data-id="${s.id}" data-user="${user.id}" ${i===0?'disabled':''}>↑</button><button aria-label="Move ${escape(user.name)} down" data-action="down" data-id="${s.id}" data-user="${user.id}" ${i===s.queue.length-1?'disabled':''}>↓</button></div></td><td><button class="danger" data-action="remove" data-id="${s.id}" data-user="${user.id}">Remove</button></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">No students waiting.<br>This queue is all caught up.</div>'}</section>`;
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
  function announcePositions(s, before) {
    s.queue.forEach((user,index)=>{ if (before.findIndex(old=>old.id===user.id)!==index) notify('student', `You moved to position ${index+1} in ${s.name}`, 'info'); });
    if (s.open && s.queue.length && before[0]?.id !== s.queue[0].id) notify('student', `You're next for ${s.name}, please head to the help desk`, 'warning');
  }
  main.addEventListener('change', event=>{ if(event.target.id==='queue-service'){selected=Number(event.target.value);render();} });
  main.addEventListener('click', event=>{
    const button = event.target.closest('button[data-action]'); if(!button || button.disabled) return;
    const action = button.dataset.action, s = services.find(s=>s.id===Number(button.dataset.id));
    if(action==='create'){openForm();return;} if(!s)return;
    if(action==='edit'){openForm(s);return;}
    if(action==='queue'){selected=s.id;location.hash='queues';return;}
    if(action==='toggle'){
      s.open=!s.open;
      if(s.queue.length) { notify('student', `${s.name} queue is now ${s.open?'open':'closed'}`, s.open?'info':'warning'); if(s.open)notify('student', `You're next for ${s.name}, please head to the help desk`, 'warning'); }
      feedback(`${s.name} queue ${s.open?'opened':'closed'}.`);
    } else {
      const before=s.queue.slice(), index=s.queue.findIndex(u=>u.id===Number(button.dataset.user));
      if(action==='serve'){if(!s.open||!s.queue.length)return;const user=s.queue.shift();notify('student', `You've been served for ${s.name}`, 'success');feedback(`${user.name} served.`);}
      else if(action==='remove' && index>=0){const [user]=s.queue.splice(index,1);notify('student', `You were removed from the ${s.name} queue`, 'error');feedback(`${user.name} removed from queue.`);}
      else if((action==='up'||action==='down') && index>=0){const target=index+(action==='up'?-1:1);if(target<0||target>=s.queue.length)return;[s.queue[index],s.queue[target]]=[s.queue[target],s.queue[index]];feedback('Queue order updated.');}
      else return;
      announcePositions(s,before);
    }
    render();
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
    if(existing)Object.assign(existing,values);else services.push({id:nextId++,...values,open:false,queue:[]});
    dialog.close();render();feedback(existing?'Service updated.':'Service created. Open its queue when ready.');
  });
  document.getElementById('cancel').onclick=()=>dialog.close();document.getElementById('dismiss').onclick=()=>dialog.close();
  window.addEventListener('hashchange',render);render();
})();
