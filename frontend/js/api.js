/* API client */
const API_BASE = 'http://localhost:5000';

const api = {
  async request(method, path, body) {
    const opts = { method, headers: {'Content-Type':'application/json'} };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(API_BASE + '/api' + path, opts);
    return r.json();
  },
  getHeatmap: (field='T') => api.request('GET', `/results/heatmap3d?field=${field}`),
  getSimulationStatus: () => api.request('GET', '/simulate/status'),
};
