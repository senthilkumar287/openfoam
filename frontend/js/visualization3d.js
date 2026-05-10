// 3D Visualization with Three.js

class Visualization3D {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.sliceIndex = 0;
        this.sliceAxis = 'z';
        this.init();
    }
    
    init() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 400;
        
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xffffff);
        
        // Camera
        this.camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        this.camera.position.z = 1.5;
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);
        
        // Lights
        const light = new THREE.DirectionalLight(0xffffff, 1);
        light.position.set(1, 1, 1);
        this.scene.add(light);
        
        const ambientLight = new THREE.AmbientLight(0x808080);
        this.scene.add(ambientLight);
        
        // Animation loop
        this.animate();
    }
    
    render3DHeatmap(heatmapData, meshInfo) {
        // Clear previous objects
        this.scene.children.forEach(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
            this.scene.remove(obj);
        });
        
        const { data, min, max } = heatmapData;
        const { nx, ny, nz } = meshInfo;
        
        // Create voxel grid
        const geometry = new THREE.BufferGeometry();
        const vertices = [];
        const colors = [];
        
        const cellSize = 1.0 / Math.max(nx, ny, nz);
        
        // Generate vertices for visible slice
        const slice = this.getSliceData(data, nx, ny, nz);
        
        let idx = 0;
        for (let i = 0; i < slice.length; i++) {
            const val = slice[i];
            const normalized = max > min ? (val - min) / (max - min) : 0.5;
            
            // Get position from index
            let x, y;
            if (this.sliceAxis === 'z') {
                x = (i % nx) * cellSize;
                y = Math.floor(i / nx) * cellSize;
            }
            
            // Create quad for this cell
            vertices.push(x, y, 0, x + cellSize, y, 0, x, y + cellSize, 0);
            
            const color = this.hslToRgb((1 - normalized) * 240, 100, 50);
            for (let j = 0; j < 3; j++) {
                colors.push(color.r, color.g, color.b);
            }
        }
        
        geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(vertices), 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(colors), 3));
        
        const material = new THREE.MeshBasicMaterial({
            vertexColors: true,
            wireframe: false
        });
        
        const mesh = new THREE.Mesh(geometry, material);
        this.scene.add(mesh);
        
        // Add lighting back
        const light = new THREE.DirectionalLight(0xffffff, 1);
        light.position.set(1, 1, 1);
        this.scene.add(light);
        const ambientLight = new THREE.AmbientLight(0x808080);
        this.scene.add(ambientLight);
    }
    
    getSliceData(data, nx, ny, nz) {
        const flatData = data.flat();
        
        if (this.sliceAxis === 'z') {
            const sliceStart = this.sliceIndex * nx * ny;
            return flatData.slice(sliceStart, sliceStart + nx * ny);
        } else if (this.sliceAxis === 'x') {
            const slice = [];
            for (let k = 0; k < nz; k++) {
                for (let j = 0; j < ny; j++) {
                    const idx = k * ny * nx + j * nx + this.sliceIndex;
                    slice.push(flatData[idx]);
                }
            }
            return slice;
        } else {
            const slice = [];
            for (let k = 0; k < nz; k++) {
                for (let i = 0; i < nx; i++) {
                    const idx = k * ny * nx + this.sliceIndex * nx + i;
                    slice.push(flatData[idx]);
                }
            }
            return slice;
        }
    }
    
    hslToRgb(h, s, l) {
        h = h / 360;
        s = s / 100;
        l = l / 100;
        
        let r, g, b;
        
        if (s === 0) {
            r = g = b = l;
        } else {
            const hue2rgb = (p, q, t) => {
                if (t < 0) t += 1;
                if (t > 1) t -= 1;
                if (t < 1/6) return p + (q - p) * 6 * t;
                if (t < 1/2) return q;
                if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
                return p;
            };
            
            const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            const p = 2 * l - q;
            r = hue2rgb(p, q, h + 1/3);
            g = hue2rgb(p, q, h);
            b = hue2rgb(p, q, h - 1/3);
        }
        
        return { r: Math.round(r * 255) / 255, g: Math.round(g * 255) / 255, b: Math.round(b * 255) / 255 };
    }
    
    setSlice(axis, index) {
        this.sliceAxis = axis;
        this.sliceIndex = index;
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        this.renderer.render(this.scene, this.camera);
    }
    
    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
}

let viz3d = null;

function initialize3DVisualization(containerId) {
    viz3d = new Visualization3D(containerId);
    window.addEventListener('resize', () => viz3d.onWindowResize());
}

function render3DHeatmap(heatmapData, meshInfo) {
    if (!viz3d) initialize3DVisualization('canvas-3d');
    viz3d.render3DHeatmap(heatmapData, meshInfo);
}

function setSlice(axis, index) {
    if (viz3d) viz3d.setSlice(axis, index);
}
