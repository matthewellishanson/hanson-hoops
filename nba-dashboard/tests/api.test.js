import assert from 'node:assert/strict';
import test from 'node:test';

import {
  api,
  getTeamBio,
  getTeamProfileStats,
  getTeamShots,
  sharedGet,
} from '../src/lib/api.js';

test('identical in-flight GET requests are coalesced', async () => {
  const originalAdapter = api.defaults.adapter;
  let requests = 0;
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  api.defaults.adapter = async (config) => {
    requests += 1;
    await gate;
    return {
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    };
  };

  try {
    const first = sharedGet('/fixture', { params: { season: '2023-24', player_id: '2544' } });
    const second = sharedGet('/fixture', { params: { player_id: '2544', season: '2023-24' } });
    assert.equal(first, second);
    release();
    const [firstResponse, secondResponse] = await Promise.all([first, second]);
    assert.equal(requests, 1);
    assert.deepEqual(firstResponse.data, secondResponse.data);
  } finally {
    api.defaults.adapter = originalAdapter;
  }
});

test('team requests send the independently selected team and season as query params', async () => {
  const originalAdapter = api.defaults.adapter;
  const requests = [];
  api.defaults.adapter = async (config) => {
    requests.push({ url: config.url, params: config.params });
    return {
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    };
  };

  try {
    await getTeamBio('1610612755', '2025-26');
    await getTeamProfileStats('1610612743', '2009-10');
    await getTeamShots('1610612738', '2007-08');
    assert.deepEqual(requests, [
      {
        url: '/team_bio',
        params: { team_id: '1610612755', season: '2025-26' },
      },
      {
        url: '/team_profile_stats',
        params: {
          team_id: '1610612743',
          season: '2009-10',
          scale: 'percentile',
          opp_scale: 'percentile',
        },
      },
      {
        url: '/team_shots',
        params: { team_id: '1610612738', season: '2007-08' },
      },
    ]);
  } finally {
    api.defaults.adapter = originalAdapter;
  }
});
