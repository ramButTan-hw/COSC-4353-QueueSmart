'use strict';
const { randomUUID } = require('node:crypto');
const { ApiError } = require('./validation.cjs');

class Notifications {
  constructor() { this.items = []; }

  // One join and one near-front reminder per participation, even after reordering.
  joined(record, position) {
    this.add(record, 'joined', `You joined ${record.serviceName} at position ${position}.`, 'success');
  }

  close(record, position, queueOpen) {
    if (queueOpen && position <= 2 && !record.closeNotified) {
      record.closeNotified = true;
      this.add(record, 'close', `You're ${position === 1 ? 'next' : 'nearly next'} for ${record.serviceName}. Please head to the help desk.`, 'warning');
    }
  }

  add(record, kind, message, type) {
    this.items.unshift({ id: randomUUID(), recipientId: record.userId, role: 'student', participationId: record.id, kind, message, type, ts: Date.now(), read: false });
  }

  list(userId) { return structuredClone(this.items.filter(n => n.recipientId === userId)); }

  markRead(userId, id) {
    const item = this.items.find(n => n.id === id && n.recipientId === userId);
    if (!item) throw new ApiError(404, 'Notification not found.');
    item.read = true;
    return structuredClone(item);
  }

  markAllRead(userId) { this.items.forEach(n => { if (n.recipientId === userId) n.read = true; }); }
  clear(userId) { this.items = this.items.filter(n => n.recipientId !== userId); }
}

module.exports = { Notifications };
