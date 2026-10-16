'use strict';
const { ApiError, dateRange } = require('./validation.cjs');

class History {
  constructor() { this.records = new Map(); }

  join(event) {
    if (this.records.has(event.participationId)) throw new ApiError(409, 'Participation already exists.');
    if ([...this.records.values()].some(r => r.userId === event.userId && r.outcome === 'Waiting')) {
      throw new ApiError(409, 'User already has an active participation.');
    }
    const record = { id: event.participationId, userId: event.userId, serviceId: event.serviceId, serviceName: event.serviceName,
      joinedAt: Date.now(), completedAt: null, outcome: 'Waiting', closeNotified: false };
    this.records.set(record.id, record);
    return record;
  }

  active(id) {
    const record = this.records.get(id);
    if (!record) throw new ApiError(404, 'Participation not found.');
    if (record.outcome !== 'Waiting') throw new ApiError(409, 'Participation is already complete.');
    return record;
  }

  complete(record, type) {
    record.outcome = { served: 'Served', left: 'Left queue', removed: 'Removed' }[type];
    record.completedAt = Date.now();
  }

  list(userId, from, to) {
    const { start, end } = dateRange(from, to);
    return [...this.records.values()].filter(r => r.userId === userId && (start === null || r.joinedAt >= start) && (end === null || r.joinedAt < end))
      .reverse().map(({ closeNotified, ...r }) => ({ ...r, date: r.completedAt ?? r.joinedAt }));
  }
}

module.exports = { History };
