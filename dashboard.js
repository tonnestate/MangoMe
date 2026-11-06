/*
 * MangoMe / Jantt: optional read-only schedule projection.
 * Copyright (c) MangoMe contributors. Apache-2.0.
 *
 * This file deliberately does not create a second state store, synthesize dates,
 * mutate MangoMe state, load remote scripts, or bypass MangoMe governance.
 *
 * Integration (the host supplies canonical MangoMe records and Jantt's IIFE):
 *   const snapshot = { family, slices, scheduleBySliceId };
 *   const view = MangoMeJantt.mount(existingElement, snapshot, window.Jantt);
 *   // view.projection contains the source revision and dependency requirements.
 *
 * scheduleBySliceId is host-maintained display-only planning data:
 *   { [canonicalSliceId]: { start: 'YYYY-MM-DD', end: 'YYYY-MM-DD' } }
 * Its values are not MangoMe normative, execution or assurance state.
 *
 * A schedule with missing dates is rejected to prevent silently dropping
 * prerequisite tasks from the timeline. No mutation callbacks are registered.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module && module.exports) module.exports = api;
  if (root) root.MangoMeJantt = api;
})(typeof globalThis !== 'undefined' ? globalThis : undefined, function () {
  'use strict';

  const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
  const ASSURANCE = new Set(['UNVERIFIED', 'PARTIAL', 'VERIFIED', 'ACCEPTED', 'REJECTED']);
  const EXECUTION = new Set(['PLANNED', 'STARTED', 'ACTIVE', 'PAUSED', 'BLOCKED', 'DONE_CLAIMED', 'CANCELLED']);
  const REQUIREMENTS = new Set(['DONE_CLAIMED', 'VALIDATED', 'VERIFIED', 'CLOSED', 'ACCEPTED']);

  function fail(message) {
    throw new Error('MangoMeJantt: ' + message);
  }

  function record(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function nonEmpty(value, name) {
    if (typeof value !== 'string' || !value.trim()) fail(name + ' must be a non-empty string');
    return value;
  }

  function date(value, name) {
    if (typeof value !== 'string' || !ISO_DATE.test(value)) fail(name + ' must be YYYY-MM-DD');
    const [y, m, d] = value.split('-').map(Number);
    const utc = new Date(0);
    utc.setUTCFullYear(y, m - 1, d);
    if (utc.getUTCFullYear() !== y || utc.getUTCMonth() !== m - 1 || utc.getUTCDate() !== d) {
      fail(name + ' is not a calendar date');
    }
    return value;
  }

  function ratio(slice) {
    const current = slice.current_step;
    const total = slice.total_steps;
    if (current == null && total == null) return undefined;
    if (!Number.isInteger(current) || !Number.isInteger(total) || total < 1 || current < 0 || current > total) {
      fail('invalid steps for slice ' + slice.entity_id);
    }
    return current / total;
  }

  function taskStatus(slice) {
    const execution = slice.execution_state || 'PLANNED';
    const assurance = slice.assurance_state || 'UNVERIFIED';
    if (!EXECUTION.has(execution)) fail('unknown execution state on slice ' + slice.entity_id);
    if (!ASSURANCE.has(assurance)) fail('unknown assurance state on slice ' + slice.entity_id);
    if (assurance === 'VERIFIED' || assurance === 'ACCEPTED') return 'completed';
    if (execution === 'BLOCKED') return 'blocked';
    if (execution === 'DONE_CLAIMED') return 'submitted';
    if (execution === 'STARTED' || execution === 'ACTIVE' || execution === 'PAUSED') return 'in-progress';
    return 'not-started';
  }

  function normalizedDeps(slice) {
    const structured = slice.dependency_requirements;
    if (structured != null && !Array.isArray(structured)) fail('dependency_requirements must be an array');
    const legacy = slice.depends_on;
    if (legacy != null && !Array.isArray(legacy)) fail('depends_on must be an array');
    const dedup = new Map();
    for (const item of structured || []) {
      if (!record(item)) fail('invalid dependency on ' + slice.entity_id);
      const id = nonEmpty(item.slice_id, 'dependency.slice_id');
      const required = item.required_level || 'DONE_CLAIMED';
      if (!REQUIREMENTS.has(required)) fail('unknown dependency requirement ' + required);
      if (dedup.has(id) && dedup.get(id) !== required) fail('conflicting dependency levels on ' + slice.entity_id);
      dedup.set(id, required);
    }
    for (const id of legacy || []) {
      nonEmpty(id, 'depends_on entry');
      if (!dedup.has(id)) dedup.set(id, 'DONE_CLAIMED');
    }
    if (dedup.has(slice.entity_id)) fail('self-dependency on ' + slice.entity_id);
    return Array.from(dedup, ([slice_id, required_level]) => ({ slice_id, required_level }));
  }

  function assertDag(edges) {
    const visited = new Set();
    const visiting = new Set();
    const visit = function (id) {
      if (visiting.has(id)) fail('cyclic dependencies involving ' + id);
      if (visited.has(id)) return;
      visiting.add(id);
      for (const dep of edges.get(id)) visit(dep.slice_id);
      visiting.delete(id);
      visited.add(id);
    };
    for (const id of edges.keys()) visit(id);
  }

  // Deterministic read model: no guessed dates, schedule cascades or writes.
  function project(snapshot) {
    if (!record(snapshot)) fail('snapshot must be an object');
    const family = snapshot.family;
    if (!record(family)) fail('family is required');
    const familyId = nonEmpty(family.entity_id, 'family.entity_id');
    if (!Array.isArray(snapshot.slices)) fail('slices must be an array');
    const schedule = snapshot.scheduleBySliceId || {};
    if (!record(schedule)) fail('scheduleBySliceId must be an object');

    const byId = new Map();
    const edges = new Map();
    for (const slice of snapshot.slices) {
      if (!record(slice)) fail('invalid slice');
      const id = nonEmpty(slice.entity_id, 'slice.entity_id');
      if (slice.family_id !== familyId) fail('cross-family slice ' + id);
      if (byId.has(id)) fail('duplicate slice ID ' + id);
      nonEmpty(slice.title, 'slice.title');
      byId.set(id, slice);
      edges.set(id, normalizedDeps(slice));
    }
    for (const [id, deps] of edges) {
      for (const dep of deps) {
        if (!byId.has(dep.slice_id)) fail('unresolved dependency ' + dep.slice_id + ' for slice ' + id);
      }
    }
    assertDag(edges);
    for (const id of Object.keys(schedule)) {
      if (!byId.has(id)) fail('schedule entry refers to unknown slice ' + id);
    }

    const missingScheduleIds = [];
    const tasks = [];
    const dependencyLevels = {};
    for (const [id, slice] of byId) {
      const deps = edges.get(id);
      dependencyLevels[id] = deps.map(dep => ({ ...dep }));
      const dates = schedule[id];
      if (dates == null) {
        missingScheduleIds.push(id);
        continue;
      }
      if (!record(dates)) fail('invalid schedule for slice ' + id);
      const start = date(dates.start, id + '.start');
      const end = date(dates.end, id + '.end');
      if (start > end) fail('end before start for slice ' + id);
      const status = taskStatus(slice);
      const progress = ratio(slice);
      tasks.push({
        id,
        label: slice.title,
        category: 'mangome-work',
        start,
        end,
        dependsOn: deps.map(d => d.slice_id),
        locked: true,
        status,
        ...(progress === undefined ? {} : { progress }),
        fields: {
          execution_state: slice.execution_state || 'PLANNED',
          assurance_state: slice.assurance_state || 'UNVERIFIED',
          validation_state: slice.validation_state || 'NOT_STARTED',
          dependency_requirements: dependencyLevels[id]
        }
      });
    }
    if (missingScheduleIds.length) {
      fail('missing explicit schedule for slice IDs: ' + missingScheduleIds.join(', '));
    }

    const plan = {
      meta: {
        title: typeof family.title === 'string' && family.title.trim() ? family.title : familyId,
        scale: 'week',
        defaultGapDays: 0,
        showCriticalPath: true,
        autoCascade: false,
        sourceFamilyId: familyId,
        sourceFamilyRevision: family.revision
      },
      categories: { 'mangome-work': { label: 'MangoMe Work', color: '#64748b' } },
      tasks
    };
    return { plan, familyId, sourceFamilyRevision: family.revision, dependencyLevels };
  }

  // The chart is always read-only. The host controls how canonical data is fetched.
  function mount(target, snapshot, engine) {
    const jantt = engine || (typeof globalThis !== 'undefined' && globalThis.Jantt);
    if (!jantt || typeof jantt.mount !== 'function') fail('Jantt.mount is unavailable; provide the locally installed Jantt standalone bundle');
    if (!target) fail('a mount target is required');
    const projection = project(snapshot);
    if (typeof jantt.validate === 'function') {
      const validation = jantt.validate(projection.plan);
      if (!validation || validation.valid !== true) {
        const problems = (validation && Array.isArray(validation.errors)) ? validation.errors.map(e => e.message || e.code).join('; ') : 'unknown Jantt validation result';
        fail('Jantt rejected schedule: ' + problems);
      }
    }
    const instance = jantt.mount(target, projection.plan, {
      readOnly: true,
      autoCascade: false,
      viewport: { scale: 'week', showCriticalPath: true, autoCascade: false }
    });
    return { instance, projection };
  }

  return Object.freeze({ project, mount });
});
