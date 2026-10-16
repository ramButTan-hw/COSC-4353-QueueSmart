'use strict';

class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

function text(value, field, max = 100) {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > max) {
    throw new ApiError(400, `${field} must be a nonempty string of at most ${max} characters.`);
  }
  return value.trim();
}

function positiveInteger(value, field) {
  if (!Number.isSafeInteger(value) || value < 1) throw new ApiError(400, `${field} must be a positive integer.`);
  return value;
}

function object(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ApiError(400, 'A JSON object is required.');
}

function event(value) {
  object(value);
  const type = text(value.type, 'type', 20);
  if (!['joined', 'position', 'served', 'left', 'removed'].includes(type)) throw new ApiError(400, 'Unknown queue event type.');
  const result = { type, participationId: text(value.participationId, 'participationId') };
  if (type === 'joined') {
    result.userId = text(value.userId, 'userId', 254);
    result.serviceId = positiveInteger(value.serviceId, 'serviceId');
    result.serviceName = text(value.serviceName, 'serviceName');
  }
  if (type === 'joined' || type === 'position') {
    result.position = positiveInteger(value.position, 'position');
    if (typeof value.queueOpen !== 'boolean') throw new ApiError(400, 'queueOpen must be a boolean.');
    result.queueOpen = value.queueOpen;
  }
  return result;
}

function dateRange(from, to) {
  const parse = (value, field) => {
    if (value === null || value === undefined) return null;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new ApiError(400, `${field} must be YYYY-MM-DD.`);
    const ms = Date.parse(value + 'T00:00:00Z');
    if (!Number.isFinite(ms) || new Date(ms).toISOString().slice(0, 10) !== value) throw new ApiError(400, `${field} must be a valid date.`);
    return ms;
  };
  const start = parse(from, 'from'), end = parse(to, 'to');
  if (start !== null && end !== null && start > end) throw new ApiError(400, 'from cannot be after to.');
  return { start, end: end === null ? null : end + 86400000 };
}

module.exports = { ApiError, text, object, event, dateRange };
