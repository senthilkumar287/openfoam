/* 3D Heatmap Visualization using Three.js r128 */

class Visualization3D {
  constructor(containerId) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    this.sliceIndex = 0;
    this.sliceAxis  = 'z';
    this._lastHm = null;
    this._lastInfo = null;
    if (this.container) this._init();
  }

  _init() {
    const W = this.container.clientWidth  || 600;
    const H = this.container.clientHeight || 400;

    this.scene    = new THREE.Scene();
    this.scene.background = new THREE.Color(0x080b0e);
    this.camera   = new THREE.PerspectiveCamera(55, W/H, 0.01, 100);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(W, H);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.innerHTML = '';
    this.container.appendChild(this.renderer.domElement);

    // Lights
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dl = new THREE.DirectionalLight(0xffffff, 0.6);
    dl.position.set(2, 3, 2); this.scene.add(dl);

    // Axes
    this.scene.add(new THREE.AxesHelper(0.3));

    // Orbit controls (manual, no import needed)
    this._spherical = { theta: 0.5, phi: 1.1, radius: 2.5 };
    this._target    = new THREE.Vector3(0.5, 0.5, 0.1);
    this._setupOrbit();
    this._updateCamera();
    this._animate();
  }

  _setupOrbit() {
    let drag = false, px = 0, py = 0;
    const el = this.renderer.domElement;
    el.addEventListener('mousedown', e => { drag=true; px=e.clientX; py=e.clientY; });
    el.addEventListener('mouseup',   () => drag=false);
    el.addEventListener('mouseleave',() => drag=false);
    el.addEventListener('mousemove', e => {
      if (!drag) return;
      this._spherical.theta -= (e.clientX-px)*0.005;
      this._spherical.phi    = Math.max(.1, Math.min(Math.PI-.1, this._spherical.phi+(e.clientY-py)*0.005));
      px=e.clientX; py=e.clientY;
      this._updateCamera();
    });
    el.addEventListener('wheel', e => {
      this._spherical.radius = Math.max(.5, Math.min(8, this._spherical.radius+e.deltaY*.002));
      this._updateCamera(); e.preventDefault();
    }, {passive:false});
    // Touch
    let lastDist = null;
    el.addEventListener('touchstart', e => { if(e.touches.length===1){px=e.touches[0].clientX;py=e.touches[0].clientY;drag=true;} });
    el.addEventListener('touchend', () => { drag=false; lastDist=null; });
    el.addEventListener('touchmove', e => {
      if(e.touches.length===1 && drag){
        this._spherical.theta-=(e.touches[0].clientX-px)*0.005;
        this._spherical.phi=Math.max(.1,Math.min(Math.PI-.1,this._spherical.phi+(e.touches[0].clientY-py)*0.005));
        px=e.touches[0].clientX; py=e.touches[0].clientY;
        this._updateCamera();
      }
      e.preventDefault();
    }, {passive:false});
  }

  _updateCamera() {
    const {theta, phi, radius} = this._spherical;
    const t = this._target;
    this.camera.position.set(
      t.x + radius*Math.sin(phi)*Math.sin(theta),
      t.y + radius*Math.cos(phi),
      t.z + radius*Math.sin(phi)*Math.cos(theta)
    );
    this.camera.lookAt(t);
  }

  _animate() {
    if (!this.renderer) return;
    requestAnimationFrame(() => this._animate());
    this.renderer.render(this.scene, this.camera);
  }

  // ── Colormap ──
  _color(t) {
    t = Math.max(0, Math.min(1, t));
    const cm = (typeof document !== 'undefined' && document.getElementById('colormap'))
      ? document.getElementById('colormap').value : 'rainbow';
    if (cm === 'coolwarm') {
      return new THREE.Color(
        t < .5 ? .13+t*1.74 : 1,
        .08+t*.64,
        t > .5 ? 1-(t-.5)*1.74 : 1
      );
    }
    if (cm === 'turbo') {
      return new THREE.Color(
        Math.max(0,Math.min(1, t<.5?2*t:2-2*t+.5)),
        Math.max(0,Math.min(1, t<.25?4*t:t<.75?1:4-4*t)),
        Math.max(0,Math.min(1, t<.5?1-2*t:0))
      );
    }
    if (cm === 'viridis') {
      return new THREE.Color(
        Math.max(0,Math.min(1,.267+.005*t+2.33*t*t-1.52*t*t*t)),
        Math.max(0,Math.min(1,.005+1.1*t-.3*t*t)),
        Math.max(0,Math.min(1,.33+.78*t-.78*t*t))
      );
    }
    // rainbow (OpenFOAM default)
    const h = (1-t)*0.667;
    return new THREE.Color().setHSL(h, 1.0, 0.5);
  }

  // ── Get 2D slice from 3D data ──
  _getSlice(data) {
    const isDeep3d = Array.isArray(data[0]) && Array.isArray(data[0][0]);
    if (!isDeep3d) return data.flat();

    const nz = data.length, ny = data[0].length, nx = data[0][0].length;
    const si = Math.min(this.sliceIndex, (this.sliceAxis==='z'?nz:this.sliceAxis==='y'?ny:nx) - 1);

    if (this.sliceAxis === 'z') return data[si].flat();
    if (this.sliceAxis === 'y') {
      const out = [];
      for (let k=0;k<nz;k++) for (let i=0;i<nx;i++) out.push(data[k][Math.min(si,ny-1)][i]);
      return out;
    }
    const out = [];
    for (let k=0;k<nz;k++) for (let j=0;j<ny;j++) out.push(data[k][j][Math.min(si,nx-1)]);
    return out;
  }

  render3DHeatmap(hm, info) {
    this._lastHm = hm; this._lastInfo = info;
    if (!this.scene) return;

    // Clear old mesh objects
    const rem = [];
    this.scene.children.forEach(o => { if(o.isMesh||o.type==='Points') rem.push(o); });
    rem.forEach(o => { o.geometry?.dispose(); o.material?.dispose(); this.scene.remove(o); });

    const data = hm.data;
    const {nx, ny, nz} = info;
    const vmin = hm.min, vmax = hm.max, range = vmax - vmin || 1;

    // Build voxel-based point cloud (efficient for large grids)
    const total = nx * ny * nz;
    const positions = new Float32Array(total * 3);
    const colors    = new Float32Array(total * 3);

    let idx = 0;
    const is3d = Array.isArray(data[0]) && Array.isArray(data[0][0]);

    for (let k=0; k<nz; k++) {
      for (let j=0; j<ny; j++) {
        for (let i=0; i<nx; i++) {
          let v;
          if (is3d)  v = (data[k]?.[j]?.[i]) ?? vmin;
          else        v = vmin;
          v = isFinite(v) ? v : vmin;

          const t = (v - vmin) / range;
          const c = this._color(t);

          positions[idx*3]   = i/(nx-1||1);
          positions[idx*3+1] = j/(ny-1||1);
          positions[idx*3+2] = k/(Math.max(nz-1,1));
          colors[idx*3]   = c.r;
          colors[idx*3+1] = c.g;
          colors[idx*3+2] = c.b;
          idx++;
        }
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color',    new THREE.BufferAttribute(colors, 3));

    const mat = new THREE.PointsMaterial({
      size: Math.max(0.01, 1.2 / Math.max(nx, ny, nz)),
      vertexColors: true, sRGBEncoding: true
    });
    const pts = new THREE.Points(geo, mat);
    this.scene.add(pts);
    this.currentMesh = pts;

    // Bounding box wireframe
    const boxGeo = new THREE.BoxGeometry(1, 1, nz/(Math.max(nx,ny))||0.05);
    const boxMat = new THREE.MeshBasicMaterial({color:0x334455, wireframe:true, opacity:.3, transparent:true});
    const box = new THREE.Mesh(boxGeo, boxMat);
    box.position.set(.5,.5, nz/(2*Math.max(nx,ny))||0.025);
    this.scene.add(box);
  }

  _redrawSlice() {
    if (this._lastHm && this._lastInfo) this.render3DHeatmap(this._lastHm, this._lastInfo);
  }

  resetCamera() {
    this._spherical = { theta: 0.5, phi: 1.1, radius: 2.5 };
    this._target = new THREE.Vector3(0.5, 0.5, 0.1);
    this._updateCamera();
  }

  setViewAngle(angle) {
    const views = {
      iso:   [0.5, 1.1, 2.5],
      front: [0, Math.PI/2, 2.0],
      top:   [0, 0.05, 2.5]
    };
    const [theta, phi, radius] = views[angle] || [0.5, 1.1, 2.5];
    this._spherical = { theta, phi, radius };
    this._updateCamera();
  }

  onResize() {
    if (!this.container || !this.renderer) return;
    const W = this.container.clientWidth || 600;
    const H = this.container.clientHeight || 400;
    this.camera.aspect = W/H; this.camera.updateProjectionMatrix();
    this.renderer.setSize(W, H);
  }
}

let viz3dMain = null;
function initialize3DVisualization(id) {
  viz3dMain = new Visualization3D(id);
  return viz3dMain;
}
function render3DHeatmap(hm, info) {
  if (!viz3dMain) viz3dMain = new Visualization3D('canvas-3d');
  viz3dMain.render3DHeatmap(hm, info);
}
