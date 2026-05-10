// Add to ui.js

// Toggle 3D/2D UI
document.addEventListener('DOMContentLoaded', function() {
    const dimensionSelect = document.getElementById('mesh-dimension');
    if (dimensionSelect) {
        dimensionSelect.addEventListener('change', function(e) {
            const nzGroup = document.getElementById('nz-group');
            const viz3dSection = document.getElementById('viz-3d-section');
            const canvas3d = document.getElementById('canvas-3d');
            
            if (e.target.value === '3d') {
                nzGroup.style.display = 'block';
                viz3dSection.style.display = 'block';
                canvas3d.style.display = 'block';
            } else {
                nzGroup.style.display = 'none';
                viz3dSection.style.display = 'none';
                canvas3d.style.display = 'none';
            }
        });
    }
    
    const sliceIndex = document.getElementById('slice-index');
    if (sliceIndex) {
        sliceIndex.addEventListener('input', function(e) {
            document.getElementById('slice-value').textContent = e.target.value;
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
        
        const result = await api.request('POST', '/mesh/create3d', {
            nx, ny, nz, domain
        });
        
        ui.log(result.message);
        document.getElementById('mesh-info').innerHTML = `
            <strong>3D Mesh Info:</strong><br>
            Size: ${result.mesh.nx} x ${result.mesh.ny} x ${result.mesh.nz}<br>
            Domain: ${result.mesh.domain.join(' x ')} m<br>
            Cells: ${result.mesh.num_cells}
        `;
        
    } catch (error) {
        ui.showError(`3D Mesh creation failed: ${error.message}`);
    }
}

async function render3DHeatmap() {
    try {
        ui.log('Rendering 3D heatmap...');
        
        const result = await api.request('GET', '/results/heatmap3d');
        
        if (result.heatmap) {
            const sliceAxis = document.getElementById('slice-axis').value;
            const sliceIndex = parseInt(document.getElementById('slice-index').value);
            
            window.render3DHeatmap(result.heatmap, {
                nx: result.heatmap.shape[2],
                ny: result.heatmap.shape[1],
                nz: result.heatmap.shape[0]
            });
            
            ui.log('3D visualization rendered');
        }
    } catch (error) {
        ui.showError(`3D rendering failed: ${error.message}`);
    }
}

// Override createMesh for 3D support
const originalCreateMesh = window.createMesh;
window.createMesh = function() {
    const dimension = document.getElementById('mesh-dimension').value;
    if (dimension === '3d') {
        createMesh3D();
    } else {
        originalCreateMesh();
    }
};
