'use strict';
const { ApiError, event } = require('./validation.cjs');
const { Notifications } = require('./notifications.cjs');
const { History } = require('./history.cjs');
const { randomUUID } = require('node:crypto');

class Activity {
  constructor() { this.id = randomUUID(); this.notifications = new Notifications(); this.history = new History(); }

  // Queue modules call this hook after calculating their new positions. No queue is managed here.
  apply(events) {
    if (!Array.isArray(events) || !events.length || events.length > 1000) throw new ApiError(400, 'events must contain 1–1000 queue events.');
    const validated = events.map(event);
    const previous = structuredClone({ records: this.history.records, items: this.notifications.items });
    try {
      for (const item of validated) {
        const record = item.type === 'joined' ? this.history.join(item) : this.history.active(item.participationId);
        if (item.type === 'joined') this.notifications.joined(record, item.position);
        if (item.type === 'joined' || item.type === 'position') this.notifications.close(record, item.position, item.queueOpen);
        else this.history.complete(record, item.type);
      }
    } catch (error) {
      this.history.records = previous.records;
      this.notifications.items = previous.items;
      throw error;
    }
    return { processed: validated.length };
  }
}

module.exports = { Activity };
