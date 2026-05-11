// 3D Visualization with Three.js (r128)
// FIXED: proper geometry, OrbitControls via inline impl, correct color normalization

class Visualization3D {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.currentMesh = null;
        this.sliceIndex = 0;
        this.sliceAxis = 'z';
        this._lastHeatmapData = null;
        this._lastMeshInfo = null;
        this.init();
    }

    init() {
        const width = this.container.clientWidth || 800;
        const height = this.container.clientHeight || 500;

        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e);

        // Camera
        this.camera = new THREE.PerspectiveCamera(60, width / height, 0.01, 100);
        this.camera.position.set(0.5, 0.5, 2.0);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.innerHTML = '';
        this.container.appendChild(this.renderer.domElement);

        // Add lights (persistent — added once, not inside render3DHeatmap)
        this._setupLights();

        // Simple orbit controls via mouse events
        this._setupOrbitControls();

        // Add axes helper
        const axes = new THREE.AxesHelper(0.3);
        this.scene.add(axes);

        // Animation loop
        this._animate();
    }

    _setupLights() {
        const ambient = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambient);
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(2, 3, 2);
        this.scene.add(dirLight);
    }

    _setupOrbitControls() {
        // Manual orbit controls (THREE.OrbitControls not available in CDN r128 bundle)
        let isDragging = false;
        let prevX = 0, prevY = 0;
        let spherical = { theta: 0, phi: Math.PI / 4, radius: 2.0 };
        let target = new THREE.Vector3(0.5, 0.5, 0.0);

        const updateCamera = () => {
            this.camera.position.x = target.x + spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
            this.camera.position.y = target.y + spherical.radius * Math.cos(spherical.phi);
            this.camera.position.z = target.z + spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
            this.camera.lookAt(target);
        };

        updateCamera();

        const canvas = this.renderer.domElement;

        canvas.addEventListener('mousedown', (e) => {
            isDragging = true;
            prevX = e.clientX;
            prevY = e.clientY;
        });

        canvas.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = (e.clientX - prevX) * 0.005;
            const dy = (e.clientY - prevY) * 0.005;
            spherical.theta -= dx;
            spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + dy));
            prevX = e.clientX;
            prevY = e.clientY;
            updateCamera();
        });

        canvas.addEventListener('mouseup', () => { isDragging = false; });
        canvas.addEventListener('mouseleave', () => { isDragging = false; });

        canvas.addEventListener('wheel', (e) => {
            spherical.radius = Math.max(0.5, Math.min(10, spherical.radius + e.deltaY * 0.002));
            updateCamera();
            e.preventDefault();
        }, { passive: false });

        this._updateCamera = updateCamera;
        this._spherical = spherical;
    }

    render3DHeatmap(heatmapData, meshInfo) {
        this._lastHeatmapData = heatmapData;
        this._lastMeshInfo = meshInfo;

        // Remove only mesh objects, not lights/axes
        const toRemove = [];
        this.scene.children.forEach(obj => {
            if (obj.isMesh || obj instanceof THREE.Points) toRemove.push(obj);
        });
        toRemove.forEach(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
            this.scene.remove(obj);
        });

        const { data, min, max } = heatmapData;
        const { nx, ny, nz } = meshInfo;

        if (!data || data.length === 0) {
            console.warn('No heatmap data to render');
            return;
        }

        const cellSize = 1.0 / Math.max(nx, ny, nz || 1);
        const slice = this._getSliceData(data, nx, ny, nz);
        const sliceNx = this._getSliceWidth(nx, ny, nz);
        const sliceNy = this._getSliceHeight(nx, ny, nz);

        // Build geometry with proper triangulated quads (2 triangles per cell)
        const numCells = slice.length;
        const positions = new Float32Array(numCells * 6 * 3);  // 6 verts per quad (2 tri)
        const colors = new Float32Array(numCells * 6 * 3);

        let pIdx = 0, cIdx = 0;

        const valueRange = (max - min) > 1e-10 ? (max - min) : 1.0;

        for (let i = 0; i < slice.length; i++) {
            const val = slice[i] !== undefined ? slice[i] : min;
            const normalized = (val - min) / valueRange;
            const col = this._hslToRgb((1.0 - normalized) * 240, 1.0, 0.5);

            const col_x = i % sliceNx;
            const col_y = Math.floor(i / sliceNx);

            let x0, y0, z0, x1, y1, z1;

            if (this.sliceAxis === 'z') {
                x0 = col_x * cellSize;       y0 = col_y * cellSize;       z0 = this.sliceIndex * cellSize;
                x1 = x0 + cellSize;           y1 = y0 + cellSize;           z1 = z0;
                // Quad as 2 triangles: (x0,y0) (x1,y0) (x1,y1), (x0,y0) (x1,y1) (x0,y1)
                positions[pIdx++]=x0; positions[pIdx++]=y0; positions[pIdx++]=z0;
                positions[pIdx++]=x1; positions[pIdx++]=y0; positions[pIdx++]=z0;
                positions[pIdx++]=x1; positions[pIdx++]=y1; positions[pIdx++]=z0;
                positions[pIdx++]=x0; positions[pIdx++]=y0; positions[pIdx++]=z0;
                positions[pIdx++]=x1; positions[pIdx++]=y1; positions[pIdx++]=z0;
                positions[pIdx++]=x0; positions[pIdx++]=y1; positions[pIdx++]=z0;
            } else if (this.sliceAxis === 'x') {
                y0 = col_x * cellSize;        z0 = col_y * cellSize;        x0 = this.sliceIndex * cellSize;
                y1 = y0 + cellSize;            z1 = z0 + cellSize;
                positions[pIdx++]=x0; positions[pIdx++]=y0; positions[pIdx++]=z0;
                positions[pIdx++]=x0; positions[pIdx++]=y1; positions[pIdx++]=z0;
                positions[pIdx++]=x0; positions[pIdx++]=y1; positions[pIdx++]=z1;
                positions[pIdx++]=x0; positions[pIdx++]=y0; positions[pIdx++]=z0;
                positions[pIdx++]=x0; positions[pIdx++]=y1; positions[pIdx++]=z1;
                positions[pIdx++]=x0; positions[pIdx++]=y0; positions[pIdx++]=z1;
            } else { // y
                x0 = col_x * cellSize;        z0 = col_y * cellSize;        y0 = this.sliceIndex * cellSize;
                x1 = x0 + cellSize;            z1 = z0 + cellSize;
                positions[pIdx++]=x0; positions[pIdx++]=y0; positions[pIdx++]=z0;
                positions[pIdx++]=x1; positions[pIdx++]=y0; positions[pIdx++]=z0;
                positions[pIdx++]=x1; positions[pIdx++]=y0; positions[pIdx++]=z1;
                positions[pIdx++]=x0; positions[pIdx++]=y0; positions[pIdx++]=z0;
                positions[pIdx++]=x1; positions[pIdx++]=y0; positions[pIdx++]=z1;
                positions[pIdx++]=x0; positions[pIdx++]=y0; positions[pIdx++]=z1;
            }

            // 6 vertices share same color
            for (let v = 0; v < 6; v++) {
                colors[cIdx++] = col.r;
                colors[cIdx++] = col.g;
                colors[cIdx++] = col.b;
            }
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.computeVertexNormals();

        const material = new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide });
        const mesh = new THREE.Mesh(geometry, material);
        this.scene.add(mesh);

        // Add wireframe bounding box
        const boxGeo = new THREE.BoxGeometry(
            nx * cellSize, ny * cellSize, Math.max(nz, 1) * cellSize
        );
        const boxMat = new THREE.EdgesGeometry(boxGeo);
        const boxLine = new THREE.LineSegments(boxMat, new THREE.LineBasicMaterial({ color: 0x888888 }));
        boxLine.position.set(nx * cellSize / 2, ny * cellSize / 2, Math.max(nz, 1) * cellSize / 2);
        this.scene.add(boxLine);

        this._addColorbar(min, max);
    }

    _getSliceData(data, nx, ny, nz) {
        // data is always [nz][ny][nx] from backend/ui.js
        // Detect actual dimensionality safely
        const is3D = Array.isArray(data) && Array.isArray(data[0]) && Array.isArray(data[0][0]);

        if (!is3D) {
            // Fallback: treat as flat 2D [ny][nx]
            return Array.isArray(data[0]) ? data.flat() : data;
        }

        const axisMax = {
            'z': data.length,
            'y': data[0].length,
            'x': data[0][0].length
        };
        const safeSlice = Math.min(this.sliceIndex, (axisMax[this.sliceAxis] || 1) - 1);

        if (this.sliceAxis === 'z') {
            const kIdx = Math.min(safeSlice, data.length - 1);
            return data[kIdx].flat();
        } else if (this.sliceAxis === 'x') {
            const result = [];
            for (let k = 0; k < data.length; k++) {
                for (let j = 0; j < data[k].length; j++) {
                    const iIdx = Math.min(safeSlice, data[k][j].length - 1);
                    result.push(data[k][j][iIdx]);
                }
            }
            return result;
        } else { // y
            const result = [];
            for (let k = 0; k < data.length; k++) {
                const jIdx = Math.min(safeSlice, data[k].length - 1);
                for (let i = 0; i < data[k][jIdx].length; i++) {
                    result.push(data[k][jIdx][i]);
                }
            }
            return result;
        }
    }

    _getSliceWidth(nx, ny, nz) {
        if (this.sliceAxis === 'z') return nx;
        if (this.sliceAxis === 'x') return ny;
        return nx; // y
    }

    _getSliceHeight(nx, ny, nz) {
        if (this.sliceAxis === 'z') return ny;
        if (this.sliceAxis === 'x') return nz;
        return nz; // y
    }

    _hslToRgb(h, s, l) {
        // h in [0,360], s and l in [0,1]
        h = ((h % 360) + 360) % 360;
        const c = (1 - Math.abs(2 * l - 1)) * s;
        const x = c * (1 - Math.abs((h / 60) % 2 - 1));
        const m = l - c / 2;
        let r = 0, g = 0, b = 0;
        if (h < 60)       { r = c; g = x; b = 0; }
        else if (h < 120) { r = x; g = c; b = 0; }
        else if (h < 180) { r = 0; g = c; b = x; }
        else if (h < 240) { r = 0; g = x; b = c; }
        else if (h < 300) { r = x; g = 0; b = c; }
        else              { r = c; g = 0; b = x; }
        return { r: r + m, g: g + m, b: b + m };
    }

    _addColorbar(min, max) {
        // Draw colorbar on an overlay canvas
        let cb = document.getElementById('colorbar-canvas-3d');
        if (!cb) {
            cb = document.createElement('canvas');
            cb.id = 'colorbar-canvas-3d';
            cb.width = 30;
            cb.height = 200;
            cb.style.cssText = 'position:absolute;right:16px;top:16px;border-radius:4px;';
            this.container.style.position = 'relative';
            this.container.appendChild(cb);

            // Labels
            const lblContainer = document.createElement('div');
            lblContainer.id = 'colorbar-labels-3d';
            lblContainer.style.cssText = 'position:absolute;right:50px;top:16px;color:#fff;font-size:11px;font-family:monospace;';
            lblContainer.innerHTML = `<div id="cb-max-3d" style="margin-bottom:180px">${max.toFixed(2)}</div><div id="cb-min-3d">${min.toFixed(2)}</div>`;
            this.container.appendChild(lblContainer);
        } else {
            const maxEl = document.getElementById('cb-max-3d');
            const minEl = document.getElementById('cb-min-3d');
            if (maxEl) maxEl.textContent = max.toFixed(2);
            if (minEl) minEl.textContent = min.toFixed(2);
        }

        const ctx = cb.getContext('2d');
        const grad = ctx.createLinearGradient(0, 0, 0, cb.height);
        for (let i = 0; i <= 10; i++) {
            const t = i / 10;
            const col = this._hslToRgb((1 - t) * 240, 1.0, 0.5);
            grad.addColorStop(t, `rgb(${Math.round(col.r*255)},${Math.round(col.g*255)},${Math.round(col.b*255)})`);
        }
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, cb.width, cb.height);
    }

    setSlice(axis, index) {
        this.sliceAxis = axis;
        this.sliceIndex = parseInt(index, 10);
        if (this._lastHeatmapData && this._lastMeshInfo) {
            this.render3DHeatmap(this._lastHeatmapData, this._lastMeshInfo);
        }
    }

    _animate() {
        requestAnimationFrame(() => this._animate());
        this.renderer.render(this.scene, this.camera);
    }

    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 500;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
}

let viz3d = null;

function initialize3DVisualization(containerId) {
    if (viz3d) return; // Don't reinitialize
    viz3d = new Visualization3D(containerId);
    window.addEventListener('resize', () => viz3d && viz3d.onWindowResize());
}

function render3DHeatmap(heatmapData, meshInfo) {
    if (!viz3d) initialize3DVisualization('canvas-3d');
    viz3d.render3DHeatmap(heatmapData, meshInfo);
}

function setSlice(axis, index) {
    if (viz3d) viz3d.setSlice(axis, index);
}
