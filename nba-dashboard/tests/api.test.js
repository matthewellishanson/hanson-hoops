import assert from 'node:assert/strict';
import test from 'node:test';

import { api, sharedGet } from '../src/lib/api.js';

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
