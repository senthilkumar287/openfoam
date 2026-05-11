// 3D UI Updates - handles dimension toggle and 3D mesh creation
// This file supplements ui.js for 3D-specific controls

document.addEventListener('DOMContentLoaded', function() {
    const dimensionSelect = document.getElementById('mesh-dimension');
    if (dimensionSelect) {
        dimensionSelect.addEventListener('change', function(e) {
            const nzGroup = document.getElementById('nz-group');
            const meshNz = document.getElementById('mesh-nz');
            const domainZ = document.getElementById('domain-z');

            if (nzGroup) nzGroup.style.display = (e.target.value === '3d') ? 'block' : 'none';

            if (e.target.value === '3d') {
                if (meshNz && parseInt(meshNz.value, 10) <= 1) meshNz.value = 10;
                if (domainZ && parseFloat(domainZ.value) <= 0) domainZ.value = 0.2;
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

        if (isNaN(nx) || isNaN(ny) || isNaN(nz) || nz < 1) {
            ui.showError('Invalid 3D mesh dimensions');
            return;
        }

        ui.log('Creating 3D mesh...');

        const result = await api.request('POST', '/mesh/create3d', { nx, ny, nz, domain });

        ui.log(result.message || '3D mesh created');
        const meshInfo = document.getElementById('mesh-info');
        if (meshInfo && result.mesh) {
            meshInfo.innerHTML = `
                <strong>3D Mesh:</strong><br>
                ${result.mesh.nx} &times; ${result.mesh.ny} &times; ${result.mesh.nz}<br>
                Domain: ${domain.join(' &times; ')} m<br>
                Cells: ${result.mesh.num_cells}
            `;
        }
    } catch (e) {
        ui.showError('3D Mesh creation failed: ' + e.message);
    }
}

// Override createMesh to support 3D
const _origCreateMesh = window.createMesh;
window.createMesh = function() {
    const dim = document.getElementById('mesh-dimension');
    if (dim && dim.value === '3d') {
        createMesh3D();
    } else if (typeof _origCreateMesh === 'function') {
        _origCreateMesh();
    }
};
