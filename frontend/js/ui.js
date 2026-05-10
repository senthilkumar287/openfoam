// UI Manager
class UIManager {
    constructor() {
        this.currentPanel = 'mesh';
        this.init();
    }

    init() {
        this.setupPanelNavigation();
        this.setupTabNavigation();
        this.attachEventListeners();
    }

    setupPanelNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const panel = item.getAttribute('data-panel');
                this.switchPanel(panel);
                
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
            });
        });
    }

    switchPanel(panelName) {
        document.querySelectorAll('.panel-content').forEach(p => {
            p.classList.remove('active');
        });
        
        const panel = document.getElementById(panelName);
        if (panel) {
            panel.classList.add('active');
        }
        
        this.currentPanel = panelName;
    }

    setupTabNavigation() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.getAttribute('data-tab');
                this.switchTab(tabName);
                
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });
    }

    switchTab(tabName) {
        document.querySelectorAll('.panel-tab').forEach(t => {
            t.classList.remove('active');
        });
        
        const tab = document.getElementById(tabName);
        if (tab) {
            tab.classList.add('active');
        }
    }

    attachEventListeners() {
        document.getElementById('btn-save').addEventListener('click', () => {
            const caseName = prompt('Case name:', 'myCase');
            if (caseName) {
                saveCase(caseName);
            }
        });

        document.getElementById('btn-load').addEventListener('click', () => {
            loadCase();
        });

        document.getElementById('btn-settings').addEventListener('click', () => {
            alert('Settings panel coming soon...');
        });
    }

    showError(message) {
        const modal = document.getElementById('error-modal');
        document.getElementById('error-message').textContent = message;
        modal.classList.add('active');
    }

    updateProgress(percent) {
        const bar = document.querySelector('.progress-bar');
        const text = document.getElementById('progress-text');
        bar.style.setProperty('--width', percent + '%');
        bar.style.width = percent + '%';
        text.textContent = percent + '%';
    }

    updateProperties(props) {
        Object.keys(props).forEach(key => {
            const el = document.getElementById(`prop-${key}`);
            if (el) {
                el.textContent = props[key];
            }
        });
    }

    log(message) {
        const logOutput = document.getElementById('log-output');
        const timestamp = new Date().toLocaleTimeString();
        logOutput.value += `[${timestamp}] ${message}\n`;
        logOutput.scrollTop = logOutput.scrollHeight;
    }

    addBCRow(patch, type, value) {
        const table = document.getElementById('bc-list');
        const row = table.insertRow();
        row.innerHTML = `
            <td>${patch}</td>
            <td>
                <select class="bc-type">
                    <option value="${type}" selected>${type}</option>
                </select>
            </td>
            <td><input type="number" value="${value}" placeholder="Value"></td>
            <td><button class="btn-small" onclick="updateBC(this)">Update</button></td>
        `;
    }

    updateMonitor(data) {
        document.getElementById('monitor-iteration').textContent = data.iteration || '-';
        document.getElementById('monitor-residual-u').textContent = data.residual_u || '-';
        document.getElementById('monitor-residual-p').textContent = data.residual_p || '-';
        document.getElementById('monitor-time').textContent = data.time || '0:00';
    }
}

// Global UI instance
const ui = new UIManager();

// Modal helpers
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

// UI Functions (called from HTML)
async function createMesh() {
    try {
        ui.log('Creating mesh...');
        
        const nx = parseInt(document.getElementById('mesh-nx').value);
        const ny = parseInt(document.getElementById('mesh-ny').value);
        const nz = parseInt(document.getElementById('mesh-nz').value);
        const meshType = document.getElementById('mesh-type').value;
        const domain = [
            parseFloat(document.getElementById('domain-x').value),
            parseFloat(document.getElementById('domain-y').value),
            parseFloat(document.getElementById('domain-z').value)
        ];

        const result = await api.createMesh(nx, ny, nz, domain, meshType);
        
        ui.log(`Mesh created: ${result.message}`);
        document.getElementById('mesh-info').innerHTML = `
            <strong>Mesh Info:</strong><br>
            Size: ${result.mesh.nx} x ${result.mesh.ny} x ${result.mesh.nz}<br>
            Domain: ${result.mesh.domain.join(' x ')} m<br>
            Cells: ${result.mesh.num_cells}
        `;
        
        ui.updateProperties({
            mesh: `${nx}x${ny}x${nz}`
        });

    } catch (error) {
        ui.showError(`Mesh creation failed: ${error.message}`);
        ui.log(`ERROR: ${error.message}`);
    }
}

async function createSolver() {
    try {
        ui.log('Creating solver...');
        
        const solverType = document.getElementById('solver-type').value;
        const config = {
            nu: parseFloat(document.getElementById('nu').value),
            rho: parseFloat(document.getElementById('rho').value),
            dt: parseFloat(document.getElementById('dt').value),
            end_time: parseFloat(document.getElementById('end-time').value),
            turbulence_model: document.getElementById('turbulence-model').value
        };

        const result = await api.createSolver(solverType, config);
        
        ui.log(`Solver created: ${result.message}`);
        ui.updateProperties({
            solver: solverType
        });

    } catch (error) {
        ui.showError(`Solver creation failed: ${error.message}`);
        ui.log(`ERROR: ${error.message}`);
    }
}

async function initializeFields() {
    try {
        ui.log('Initializing fields...');
        
        const U = [
            parseFloat(document.getElementById('U-x').value),
            parseFloat(document.getElementById('U-y').value),
            parseFloat(document.getElementById('U-z').value)
        ];
        const p = parseFloat(document.getElementById('p-init').value);
        const T = parseFloat(document.getElementById('T-init').value);

        const result = await api.initializeFields(U, p, T);
        
        ui.log('Fields initialized successfully');

    } catch (error) {
        ui.showError(`Field initialization failed: ${error.message}`);
        ui.log(`ERROR: ${error.message}`);
    }
}

function updateBC(button) {
    const row = button.parentElement.parentElement;
    const patch = row.cells[0].textContent;
    const type = row.cells[1].querySelector('select').value;
    const value = row.cells[2].querySelector('input').value;

    api.setBoundaryCondition(patch, type, value)
        .then(result => {
            ui.log(`BC updated: ${patch} (${type})`);
        })
        .catch(error => {
            ui.showError(`BC update failed: ${error.message}`);
        });
}

function addPatch() {
    const patchName = prompt('Patch name:');
    if (patchName) {
        ui.addBCRow(patchName, 'dirichlet', '0');
    }
}

let simulationRunning = false;
let monitorTimer = null;

async function runSimulation() {
    if (simulationRunning) return;

    try {
        simulationRunning = true;
        document.getElementById('btn-run').disabled = true;
        document.getElementById('btn-pause').disabled = false;
        document.getElementById('btn-stop').disabled = false;
        
        const maxIters = parseInt(document.getElementById('max-iters').value);
        const dt = parseFloat(document.getElementById('dt').value);
        const tolerance = parseFloat(document.getElementById('tolerance').value);
        const sampleInterval = parseInt(document.getElementById('sample-interval').value);

        // Adjust for 3D meshes
        let adjustedMaxIters = maxIters;
        try {
            const meshInfo = await api.getMeshInfo();
            if (meshInfo && meshInfo.mesh && meshInfo.mesh.nz > 1) {
                adjustedMaxIters = Math.max(maxIters, 500); // Ensure at least 500 iterations for 3D
                ui.log(`3D mesh detected, adjusting max iterations to ${adjustedMaxIters}`);
            }
        } catch (e) {
            // Ignore mesh info error
        }

        ui.log(`Starting simulation: ${adjustedMaxIters} iterations, dt=${dt}, tol=${tolerance}`);
        ui.updateProperties({ status: 'Running...' });

        const startTime = Date.now();

        // Start monitoring timer
        monitorTimer = setInterval(async () => {
            try {
                const status = await api.getSimulationStatus();
                document.getElementById('monitor-iteration').textContent = status.iterations || 0;
                if (status.residuals && status.residuals.T && status.residuals.T.length > 0) {
                    document.getElementById('monitor-residual-t').textContent = status.residuals.T[status.residuals.T.length - 1].toFixed(2);
                }
                const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                document.getElementById('monitor-time').textContent = elapsed + 's';
            } catch (e) {
                // Ignore errors during monitoring
            }
        }, 500);

        const result = await api.runSimulation(adjustedMaxIters, dt, tolerance, sampleInterval);

        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        ui.log(`Simulation completed in ${elapsed}s`);
        ui.log(`Converged: ${result.converged}, Iterations: ${result.iterations}`);
        ui.updateProperties({
            status: result.converged ? 'Converged' : 'Completed',
            converged: result.converged ? 'Yes' : 'No'
        });

        // Update monitor with final residuals
        if (result.residuals && result.residuals.T && result.residuals.T.length > 0) {
            document.getElementById('monitor-residual-t').textContent = result.residuals.T[result.residuals.T.length - 1].toFixed(2);
        }

        ui.updateProgress(100);

    } catch (error) {
        ui.showError(`Simulation failed: ${error.message}`);
        ui.log(`ERROR: ${error.message}`);
    } finally {
        simulationRunning = false;
        if (monitorTimer) {
            clearInterval(monitorTimer);
            monitorTimer = null;
        }
        document.getElementById('btn-run').disabled = false;
        document.getElementById('btn-pause').disabled = true;
        document.getElementById('btn-stop').disabled = true;
    }
}

function pauseSimulation() {
    simulationRunning = false;
    ui.log('Simulation paused');
}

function stopSimulation() {
    simulationRunning = false;
    ui.log('Simulation stopped');
    document.getElementById('btn-run').disabled = false;
    document.getElementById('btn-pause').disabled = true;
    document.getElementById('btn-stop').disabled = true;
}

async function visualizeField() {
    try {
        const fieldName = document.getElementById('viz-field').value;
        ui.log(`Fetching field: ${fieldName}`);
        
        const result = await api.getHeatmap(fieldName);

        if (!result || !result.heatmap || !result.heatmap.data) {
            throw new Error('Invalid heatmap response from server');
        }

        ui.switchPanel('postprocess');

        const is3D = result.heatmap.shape && result.heatmap.shape[0] > 1;
        if (is3D) {
            document.getElementById('canvas-3d').style.display = 'block';
            document.getElementById('canvas-viz').style.display = 'none';
            window.render3DHeatmap(result.heatmap, {
                nx: result.heatmap.shape[2],
                ny: result.heatmap.shape[1],
                nz: result.heatmap.shape[0]
            });
            ui.log(`3D heatmap rendered for ${fieldName}`);
        } else {
            document.getElementById('canvas-3d').style.display = 'none';
            document.getElementById('canvas-viz').style.display = 'block';
            renderHeatmap(result.heatmap);
            ui.log(`Heatmap rendered for ${fieldName}`);
        }

    } catch (error) {
        ui.showError(`Visualization failed: ${error.message}`);
        ui.log(`ERROR: ${error.message}`);
    }
}

async function exportResults() {
    try {
        const formats = [];
        document.querySelectorAll('.export-options input:checked').forEach(cb => {
            formats.push(cb.value);
        });

        if (formats.length === 0) {
            alert('Select at least one format');
            return;
        }

        ui.log(`Exporting to: ${formats.join(', ')}`);
        
        for (const fmt of formats) {
            const result = await api.exportResults(fmt);
            ui.log(`Exported: ${result.file}`);
        }

    } catch (error) {
        ui.showError(`Export failed: ${error.message}`);
    }
}

function performExport() {
    exportResults();
}

async function saveCase(name) {
    try {
        const result = await api.saveCase(name);
        ui.log(`Case saved: ${name}`);
        document.getElementById('case-name').textContent = name;
    } catch (error) {
        ui.showError(`Save failed: ${error.message}`);
    }
}

function importMesh() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.stl,.msh,.foam';
    input.onchange = (e) => {
        api.importMesh(e.target.files[0])
            .then(result => {
                ui.log(`Mesh imported: ${result.message}`);
            })
            .catch(error => {
                ui.showError(`Import failed: ${error.message}`);
            });
    };
    input.click();
}

function loadCase() {
    const caseName = prompt('Case name to load:');
    if (caseName) {
        api.loadCase(caseName)
            .then(result => {
                ui.log(`Case loaded: ${caseName}`);
                document.getElementById('case-name').textContent = caseName;
            })
            .catch(error => {
                ui.showError(`Load failed: ${error.message}`);
            });
    }
}

function openBlockMesh() {
    ui.log('blockMesh configuration opened');
    alert('blockMesh utility - coming soon');
}

function decompose() {
    ui.log('Starting domain decomposition...');
    alert('decomposePar utility - coming soon');
}

function setFields() {
    ui.log('Setting fields...');
    alert('setFields utility - coming soon');
}

function mapFields() {
    ui.log('Mapping fields...');
    alert('mapFields utility - coming soon');
}

// 3D Support
document.addEventListener('DOMContentLoaded', function() {
    const dimensionSelect = document.getElementById('mesh-dimension');
    if (dimensionSelect) {
        dimensionSelect.addEventListener('change', function(e) {
            const nzGroup = document.getElementById('nz-group');
            const canvas3d = document.getElementById('canvas-3d');
            const meshNz = document.getElementById('mesh-nz');
            const domainZ = document.getElementById('domain-z');
            if (nzGroup) {
                nzGroup.style.display = e.target.value === '3d' ? 'block' : 'none';
            }
            if (canvas3d) {
                canvas3d.style.display = e.target.value === '3d' ? 'block' : 'none';
            }
            if (e.target.value === '3d') {
                if (meshNz && parseInt(meshNz.value, 10) <= 1) {
                    meshNz.value = 10;
                }
                if (domainZ && parseFloat(domainZ.value) <= 1.0) {
                    domainZ.value = 0.2;
                }
            } else {
                if (meshNz) meshNz.value = 1;
                if (domainZ) domainZ.value = 1.0;
            }
        });
    }
});

async function createMesh3D() {
    try {
        const nx = parseInt(document.getElementById('mesh-nx').value);
        const ny = parseInt(document.getElementById('mesh-ny').value);
        const nz = parseInt(document.getElementById('mesh-nz').value);
        const domain = [
            parseFloat(document.getElementById('domain-x').value),
            parseFloat(document.getElementById('domain-y').value),
            parseFloat(document.getElementById('domain-z').value)
        ];
        
        ui.log('Creating 3D mesh...');
        const result = await fetch('http://localhost:5000/api/mesh/create3d', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({nx, ny, nz, domain})
        }).then(r => r.json());
        
        if (result.status === 'success') {
            ui.log(result.message);
            document.getElementById('mesh-info').innerHTML = `
                <strong>3D Mesh:</strong><br>
                ${result.mesh.nx} × ${result.mesh.ny} × ${result.mesh.nz}<br>
                ${result.mesh.num_cells} cells
            `;
        }
    } catch (e) {
        ui.showError('3D Mesh failed: ' + e.message);
    }
}

const originalCreateMesh = window.createMesh;
window.createMesh = function() {
    const dim = document.getElementById('mesh-dimension');
    if (dim && dim.value === '3d') {
        createMesh3D();
    } else {
        originalCreateMesh();
    }
};
