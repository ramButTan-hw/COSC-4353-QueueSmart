/* A read cache of the team's services and queue APIs. No browser-owned queue state. */
(function () {
  'use strict';
  let data = { services: [] }, pending;
  function read() { return structuredClone(data); }
  function active(snapshot = read()) {
    const id = window.currentUser?.id;
    const service = snapshot.services.find(s => s.queue.some(user => user.id === id));
    if (!service) return null;
    const user = service.queue.find(user => user.id === id);
    return { service, index: user.position - 1, user };
  }
  function refresh() {
    if (pending) return pending;
    pending = (async () => {
      const [services, queues] = await Promise.all([Api.get('/services'), Api.get('/queues')]);
      const updated = { services: services.map(service => {
        const queue = queues.find(q => q.service_id === service.id);
        return { ...service, open: queue?.open ?? service.open, count: queue?.count ?? 0,
          estimatedWait: queue?.estimated_wait_minutes,
          queue: (queue?.entries || []).map(entry => ({ id: entry.user_id, name: entry.user_name,
            entryId: entry.id, priority: entry.priority, position: entry.position,
            estimatedWait: entry.estimated_wait_minutes })) };
      }) };
      if (JSON.stringify(updated) !== JSON.stringify(data)) {
        data = updated;
        window.dispatchEvent(new Event('queue-change'));
      }
      return read();
    })().finally(() => { pending = null; });
    return pending;
  }
  const ready = window.currentUser ? refresh() : Promise.resolve();
  async function change(serviceId, action, userId) {
    await ready;
    const service = data.services.find(s => s.id === Number(serviceId));
    if (!service) throw Error('Service no longer exists.');
    const route = '/queues/' + service.id;
    if (action === 'join') await Api.post(route + '/join');
    else if (action === 'leave') await Api.del(route + '/leave');
    else if (action === 'serve') await Api.post(route + '/serve-next');
    else if (action === 'toggle') await Api.post(route + (service.open ? '/close' : '/open'));
    else if (action === 'remove') await Api.del(route + '/members/' + encodeURIComponent(userId));
    else if (action === 'up' || action === 'down') await Api.post(route + '/move', { user_id: userId, direction: action });
    else throw Error('Unknown queue action.');
    if (action === 'join') notify('staff', `New student in ${service.name}`, 'info');
    if (action === 'leave') notify('staff', `A student left the ${service.name} queue`, 'info');
    // An already-running poll may predate this mutation. Finish it, then fetch fresh state.
    if (pending) await pending.catch(() => {});
    await refresh().catch(error => console.warn(error.message));
    await Notifications.refresh().catch(error => console.warn(error.message));
  }
  window.QueueStore = { ready, read, active, change, refresh };
  if (window.currentUser) {
    setInterval(() => refresh().catch(error => console.warn(error.message)), 5000);
    // Keep initialization errors observable through ready without an unhandled rejection.
    ready.catch(error => console.warn(error.message));
  }
})();
