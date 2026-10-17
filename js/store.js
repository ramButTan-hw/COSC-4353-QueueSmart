/* A2 queue demo with event hooks for the A3 notification/history backend. */
(function () {
  'use strict';
  let key;
  const seed = { services: [
    { id: 1, name: 'Password Reset', description: 'Account access and password recovery.', duration: 10, priority: 'high', open: true, queue: [] },
    { id: 2, name: 'Wi-Fi / Network', description: 'Campus Wi-Fi and device connectivity.', duration: 15, priority: 'medium', open: true, queue: [] },
    { id: 3, name: 'Printing', description: 'Printing setup, credits, and troubleshooting.', duration: 5, priority: 'low', open: false, queue: [] }
  ] };
  // Restarting the in-memory backend also starts a fresh browser demo queue.
  const ready = QueueBackend.session().then(session => { key = 'queuesmart.shared.a3.' + session.id; });
  function read() { const raw = key && localStorage.getItem(key); return raw ? JSON.parse(raw) : structuredClone(seed); }
  function save(data) { localStorage.setItem(key, JSON.stringify(data)); window.dispatchEvent(new Event('queue-change')); }
  function active(data = read()) {
    const id = window.currentUser.id;
    const service = data.services.find(s => s.queue.some(u => u.id === id));
    if (!service) return null;
    const index = service.queue.findIndex(u => u.id === id);
    return { service, index, user: service.queue[index] };
  }
  function send(user, message, type) { notify('student', message, type, { recipientId: user.id }); }
  async function change(serviceId, action, userId) {
    await ready;
    const data = read(), s = data.services.find(s => s.id === Number(serviceId));
    if (!s) throw Error('Service no longer exists.');
    const before = s.queue.slice(), events = [];
    if (action === 'join') {
      if (!s.open) throw Error('This queue is closed.');
      if (active(data)) throw Error('Leave your current queue before joining another.');
      const user = { id: currentUser.id, name: currentUser.name, participationId: crypto.randomUUID() };
      s.queue.push(user);
      events.push({ type: 'joined', participationId: user.participationId, userId: user.id,
        serviceId: s.id, serviceName: s.name, position: s.queue.length, queueOpen: s.open });
    } else if (action === 'toggle') {
      s.open = !s.open;
    } else {
      const index = action === 'serve' ? 0 : s.queue.findIndex(u => u.id === userId);
      if (index < 0 || !s.queue.length) return;
      if (action === 'serve' && !s.open) throw Error('Open this queue before serving.');
      if (action === 'up' || action === 'down') {
        const to = index + (action === 'up' ? -1 : 1);
        if (to < 0 || to >= s.queue.length) return;
        [s.queue[index], s.queue[to]] = [s.queue[to], s.queue[index]];
      } else if (['serve', 'remove', 'leave'].includes(action)) {
        const [user] = s.queue.splice(index, 1);
        events.push({ type: { serve: 'served', remove: 'removed', leave: 'left' }[action], participationId: user.participationId });
      } else return;
    }
    // Staff sends the resulting positions. The bridge derives position changes
    // after a student's leave so students cannot edit other users' activity.
    if (currentUser.role === 'staff') s.queue.forEach((user, index) => {
      if (action !== 'join' || before.some(u => u.id === user.id)) {
        events.push({ type: 'position', participationId: user.participationId, position: index + 1, queueOpen: s.open });
      }
    });
    // Commit the browser queue only after the backend accepts the whole event batch.
    if (events.length) await QueueBackend.events(events);
    save(data);
    if (action === 'join') notify('staff', `New student in ${s.name}`, 'info');
    if (action === 'leave') notify('staff', `A student left the ${s.name} queue`, 'info');
    if (action === 'toggle') s.queue.forEach(u => send(u, `${s.name} queue is now ${s.open ? 'open' : 'closed'}`, s.open ? 'info' : 'warning'));
    if (['serve', 'remove'].includes(action)) {
      const user = before.find(u => !s.queue.some(current => current.id === u.id));
      send(user, action === 'serve' ? `You've been served for ${s.name}` : `You were removed from the ${s.name} queue`, action === 'serve' ? 'success' : 'error');
    }
    // Notification polling can recover independently if this refresh fails after a successful change.
    await Notifications.refresh().catch(error => console.warn(error.message));
  }
  function saveService(values, id) {
    const data = read(), service = data.services.find(s => s.id === id);
    if (service) Object.assign(service, values);
    else data.services.push({ id: Math.max(0, ...data.services.map(s => s.id)) + 1, ...values, open: false, queue: [] });
    save(data);
  }
  window.QueueStore = { ready, read, active, change, saveService };
  window.addEventListener('storage', event => { if (event.key === key) window.dispatchEvent(new Event('queue-change')); });
})();
