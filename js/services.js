/*
 * QueueSmart – services from the back end (Assignment 3)
 *
 * The service catalogue (name, description, duration, priority) lives on the server. Queues also live on the server. Successful changes refresh
 * the service and queue cache in QueueStore. Screens keep reading services through QueueStore as before.
 *
 *   Services.load()               GET /services, then sync into QueueStore
 *   Services.create(values)       POST /services          (staff)
 *   Services.update(id, changes)  PATCH /services/{id}    (staff; send only the changed fields)
 *   Services.remove(id)           DELETE /services/{id}   (staff)
 *
 * Failed calls reject with the ApiError from js/api.js (use error.fields for per-input messages).
 * Load order: js/api.js, js/session.js, js/store.js, then this file.
 */
(function () {
  'use strict';

  async function load() {
    await QueueStore.ready;
    return (await QueueStore.refresh()).services;
  }

  // The change itself succeeded once we get here; a failed refresh only leaves the list stale until the next load.
  function refresh() { return load().catch(function (e) { console.warn('Could not refresh services:', e.message); }); }

  async function create(values) {
    var service = await Api.post('/services', values);
    await refresh();
    return service;
  }

  async function update(id, changes) {
    var service = await Api.patch('/services/' + id, changes);
    await refresh();
    return service;
  }

  async function remove(id) {
    await Api.del('/services/' + id);
    await refresh();
  }

  window.Services = { load: load, create: create, update: update, remove: remove };
})();
