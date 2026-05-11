const API_BASE = 'http://localhost:5000/api';

class APIClient {
    constructor(baseURL = API_BASE) {
        this.baseURL = baseURL;
        this.lastError = null;
    }

    async request(method, endpoint, data = null) {
        try {
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                }
            };

            if (data) {
                options.body = JSON.stringify(data);
            }

            const response = await fetch(`${this.baseURL}${endpoint}`, options);
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.message || `HTTP ${response.status}`);
            }

            return result;
        } catch (error) {
            this.lastError = error.message;
            console.error('API Error:', error);
            throw error;
        }
    }

    // Mesh operations
    async createMesh(nx, ny, nz, domain, meshType = 'structured') {
        return this.request('POST', '/mesh/create', {
            nx,
            ny,
            nz,
            domain: domain,
            mesh_type: meshType
        });
    }

    async getMeshInfo() {
        return this.request('GET', '/mesh/info');
    }

    async importMesh(file) {
        const formData = new FormData();
        formData.append('file', file);
        return fetch(`${this.baseURL}/mesh/import`, {
            method: 'POST',
            body: formData
        }).then(r => r.json());
    }

    // Solver operations
    async listSolvers() {
        return this.request('GET', '/solver/list');
    }

    async createSolver(type, config = {}) {
        return this.request('POST', '/solver/create', {
            type,
            config
        });
    }

    async getSolverInfo() {
        return this.request('GET', '/solver/info');
    }

    // Field operations
    async initializeFields(U, p, T) {
        return this.request('POST', '/fields/initialize', {
            U,
            p,
            T
        });
    }

    async getField(fieldName) {
        return this.request('GET', `/results/field/${fieldName}`);
    }

    // Boundary conditions
    async setBoundaryCondition(patch, type, value) {
        return this.request('POST', '/bc/set', {
            patch,
            type,
            value
        });
    }

    async listBCs() {
        return this.request('GET', '/bc/list');
    }

    // Simulation control
    async runSimulation(maxIters = 100, dt = 0.01, tolerance = 1e-5, sampleInterval = 10) {
        return this.request('POST', '/simulate/run', {
            max_iters: maxIters,
            dt,
            tolerance,
            sample_interval: sampleInterval
        });
    }

    async getSimulationStatus() {
        return this.request('GET', '/simulate/status');
    }

    // Results
    async getHeatmap(fieldName = 'T') {
        const endpoint = fieldName ? `/results/heatmap3d?field=${encodeURIComponent(fieldName)}` : '/results/heatmap';
        return this.request('GET', endpoint);
    }

    async exportResults(format = 'json') {
        return this.request('POST', '/results/export', { format });
    }

    // Case management
    async saveCase(name) {
        return this.request('POST', '/case/save', { name });
    }

    async loadCase(name) {
        return this.request('POST', '/case/load', { name });
    }
}

// Global API instance
const api = new APIClient();
