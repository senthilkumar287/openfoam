/* ============================================================
   OpenFOAM Clone — 3D Visualization Engine
   ParaView-style rendering with Three.js r128
   Modes: Volume | Surface | Slice | Contour | Vectors | Warp
   ============================================================ */

class Visualization3D {
  constructor(containerId) {
    this.containerId = containerId;
    this.container   = document.getElementById(containerId);
    this.sliceIndex  = 4;
    this.sliceAxis   = 'z';
    this.renderMode  = 'surface'; // surface|slice|volume|contour|vectors|warp
    this._lastHm     = null;
    this._lastInfo   = null;
    this._domainW    = 1; this._domainH = 1; this._domainD = 0.2;
    if (this.container) this._init();
  }

  /* ── Init ── */
  _init() {
    const W = this.container.clientWidth  || 700;
    const H = this.container.clientHeight || 450;

    this.scene    = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0d10);
    this.camera   = new THREE.PerspectiveCamera(50, W/H, 0.001, 200);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(W, H);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.container.innerHTML = '';
    this.container.appendChild(this.renderer.domElement);

    // Lighting (ParaView-style: ambient + 2 directional)
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.5));
    const d1 = new THREE.DirectionalLight(0xffffff, 0.8);
    d1.position.set(3, 5, 3); this.scene.add(d1);
    const d2 = new THREE.DirectionalLight(0x8899bb, 0.3);
    d2.position.set(-3, -2, -3); this.scene.add(d2);

    // Axes + grid
    this.axesHelper = new THREE.AxesHelper(0.5);
    this.scene.add(this.axesHelper);
    this._addGrid();

    // Camera
    this._sph = { theta: 0.7, phi: 0.9, radius: 2.2 };
    this._tgt = new THREE.Vector3(0.5, 0.5, 0.1);
    this._setupOrbit();
    this._updateCamera();
    this._animate();
  }

  _addGrid() {
    const grid = new THREE.GridHelper(2, 20, 0x223344, 0x1a2530);
    grid.position.set(0.5, -0.01, 0.5);
    grid.rotation.x = 0;
    this.scene.add(grid);
  }

  /* ── Orbit (manual, no OrbitControls dependency) ── */
  _setupOrbit() {
    const el = this.renderer.domElement;
    let drag = false, px = 0, py = 0;
    el.addEventListener('mousedown', e => { drag=true; px=e.clientX; py=e.clientY; e.preventDefault(); });
    el.addEventListener('mouseup',   () => drag=false);
    el.addEventListener('mouseleave',() => drag=false);
    el.addEventListener('mousemove', e => {
      if (!drag) return;
      this._sph.theta -= (e.clientX-px)*0.006;
      this._sph.phi = Math.max(0.05, Math.min(Math.PI-0.05, this._sph.phi+(e.clientY-py)*0.006));
      px=e.clientX; py=e.clientY;
      this._updateCamera();
    });
    el.addEventListener('wheel', e => {
      this._sph.radius = Math.max(0.3, Math.min(10, this._sph.radius * (1 + e.deltaY*0.001)));
      this._updateCamera(); e.preventDefault();
    }, {passive:false});
  }

  _updateCamera() {
    const {theta,phi,radius} = this._sph, t = this._tgt;
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

  /* ── Colormap ── */
  _color(t, alpha=1) {
    t = Math.max(0, Math.min(1, t));
    const cm = document.getElementById('colormap')?.value || 'rainbow';
    let r,g,b;
    if (cm === 'coolwarm') {
      if (t < 0.5) { r=0.23+t*1.54; g=0.30+t*0.40; b=0.75-t*0.50; }
      else { r=0.99; g=0.70-((t-0.5)*0.80); b=0.15-((t-0.5)*0.30); }
    } else if (cm === 'turbo') {
      r = Math.sin(t * Math.PI); g = t < 0.5 ? 2*t : 2-2*t; b = Math.cos(t * Math.PI * 0.5);
    } else if (cm === 'viridis') {
      r = 0.267+2.33*t*t-1.52*t*t*t; g = 0.005+1.1*t-0.3*t*t; b = 0.33+0.78*t-0.78*t*t;
    } else { // rainbow — OpenFOAM default
      const h = (1-t)*0.667;
      const c = new THREE.Color().setHSL(h, 1, 0.5);
      return c;
    }
    return new THREE.Color(Math.max(0,Math.min(1,r)), Math.max(0,Math.min(1,g)), Math.max(0,Math.min(1,b)));
  }

  /* ── Data helpers ── */
  _val(data, k, j, i) {
    if (Array.isArray(data[0]?.[0])) return data[k]?.[j]?.[i] ?? 0;
    return data[j]?.[i] ?? 0; // 2D fallback
  }

  _flat(data, nz, ny, nx) {
    const out = new Float32Array(nz*ny*nx);
    let idx=0;
    for (let k=0;k<nz;k++) for (let j=0;j<ny;j++) for (let i=0;i<nx;i++)
      out[idx++] = this._val(data,k,j,i);
    return out;
  }

  /* ── Clear scene objects (keep lights/axes/grid) ── */
  _clear() {
    const keep = new Set([this.axesHelper]);
    const rem = [];
    this.scene.children.forEach(o => {
      if (!keep.has(o) && !(o instanceof THREE.Light) && !(o instanceof THREE.GridHelper)) rem.push(o);
    });
    rem.forEach(o => { o.geometry?.dispose(); if(o.material){[].concat(o.material).forEach(m=>m.dispose());} this.scene.remove(o); });
  }

  /* ══════════════════════════════════════════════════
     MAIN RENDER ENTRY
  ══════════════════════════════════════════════════ */
  render3DHeatmap(hm, info) {
    this._lastHm = hm; this._lastInfo = info;
    if (!this.scene) return;
    this._clear();

    const {nx, ny, nz} = info;
    const vmin = hm.min, vmax = hm.max, range = Math.max(vmax-vmin, 1e-6);
    const data = hm.data;

    switch (this.renderMode) {
      case 'slice':    this._renderSlice(data, nx, ny, nz, vmin, range); break;
      case 'volume':   this._renderVolume(data, nx, ny, nz, vmin, range); break;
      case 'contour':  this._renderContour(data, nx, ny, nz, vmin, range); break;
      case 'vectors':  this._renderVectors(data, nx, ny, nz, vmin, range); break;
      case 'warp':     this._renderWarp(data, nx, ny, nz, vmin, range); break;
      default:         this._renderSurface(data, nx, ny, nz, vmin, range);
    }

    // Always add bounding box
    this._addBBox(nx, ny, nz);
  }

  /* ── SURFACE (default, like ParaView surface mode) ── */
  _renderSurface(data, nx, ny, nz, vmin, range) {
    // Render the 6 faces of the domain as colored quads
    // For 2D mesh: render a flat textured plane showing the field
    const faces = [
      { axis:'z', k:nz-1, label:'top'    },
      { axis:'z', k:0,    label:'bottom' },
      { axis:'y', j:ny-1, label:'back'   },
      { axis:'y', j:0,    label:'front'  },
      { axis:'x', i:nx-1, label:'right'  },
      { axis:'x', i:0,    label:'left'   },
    ];

    // Primary face: z=top (the most useful 2D view)
    this._renderFaceMesh(data, nx, ny, nz, vmin, range, 'z', Math.floor(nz/2));

    // Side faces as semi-transparent outlines
    if (nz > 2) {
      this._renderFaceMesh(data, nx, ny, nz, vmin, range, 'x', Math.floor(nx/2), 0.6);
      this._renderFaceMesh(data, nx, ny, nz, vmin, range, 'y', Math.floor(ny/2), 0.6);
    }
  }

  /* ── Render one face as a vertex-colored PlaneGeometry ── */
  _renderFaceMesh(data, nx, ny, nz, vmin, range, axis, sliceIdx, opacity=1.0) {
    let rows, cols, getV, px_, py_, pz_;

    if (axis === 'z') {
      rows=ny; cols=nx;
      getV = (j,i) => this._val(data, Math.min(sliceIdx,nz-1), j, i);
      px_ = (j,i) => i/(nx-1||1);
      py_ = (j,i) => j/(ny-1||1);
      pz_ = (j,i) => sliceIdx/(Math.max(nz-1,1)) * (nz>2 ? 0.3 : 0);
    } else if (axis === 'y') {
      rows=nz; cols=nx;
      getV = (k,i) => this._val(data, k, Math.min(sliceIdx,ny-1), i);
      px_ = (k,i) => i/(nx-1||1);
      py_ = (k,i) => sliceIdx/(ny-1||1);
      pz_ = (k,i) => k/(Math.max(nz-1,1)) * (nz>2 ? 0.3 : 0);
    } else {
      rows=nz; cols=ny;
      getV = (k,j) => this._val(data, k, j, Math.min(sliceIdx,nx-1));
      px_ = (k,j) => sliceIdx/(nx-1||1);
      py_ = (k,j) => j/(ny-1||1);
      pz_ = (k,j) => k/(Math.max(nz-1,1)) * (nz>2 ? 0.3 : 0);
    }

    const geo = new THREE.PlaneGeometry(1, 1, cols-1, rows-1);
    const pos = geo.attributes.position;
    const colArr = new Float32Array(pos.count * 3);

    for (let r=0; r<rows; r++) {
      for (let c=0; c<cols; c++) {
        const idx = r*cols + c;
        const v = getV(r,c);
        const t = isFinite(v) ? (v-vmin)/range : 0.5;
        const col = this._color(t);
        colArr[idx*3]=col.r; colArr[idx*3+1]=col.g; colArr[idx*3+2]=col.b;
        pos.setXYZ(idx, px_(r,c), py_(r,c), pz_(r,c));
      }
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colArr, 3));
    geo.computeVertexNormals();

    const mat = new THREE.MeshPhongMaterial({
      vertexColors: true, side: THREE.DoubleSide,
      transparent: opacity < 1, opacity,
      shininess: 30, specular: new THREE.Color(0.1,0.1,0.1)
    });
    const mesh = new THREE.Mesh(geo, mat);
    this.scene.add(mesh);
  }

  /* ── SLICE mode — interactive single plane ── */
  _renderSlice(data, nx, ny, nz, vmin, range) {
    const axis = this.sliceAxis;
    const maxIdx = axis==='z' ? nz-1 : axis==='y' ? ny-1 : nx-1;
    const si = Math.max(0, Math.min(this.sliceIndex, maxIdx));
    this._renderFaceMesh(data, nx, ny, nz, vmin, range, axis, si, 1.0);

    // Ghost bounding box faces to show context
    const ghostAxes = ['x','y','z'].filter(a => a !== axis);
    ghostAxes.forEach(a => {
      const midIdx = a==='z' ? Math.floor(nz/2) : a==='y' ? Math.floor(ny/2) : Math.floor(nx/2);
      this._renderFaceMesh(data, nx, ny, nz, vmin, range, a, midIdx, 0.15);
    });

    // Slice position indicator line
    this._addSliceIndicator(axis, si, nx, ny, nz);
  }

  _addSliceIndicator(axis, si, nx, ny, nz) {
    const mat = new THREE.LineBasicMaterial({ color: 0xffffff, opacity: 0.7, transparent: true });
    const points = [];
    if (axis==='z') {
      const z = si/(Math.max(nz-1,1))*0.3;
      points.push(new THREE.Vector3(0,0,z), new THREE.Vector3(1,0,z),
                  new THREE.Vector3(1,1,z), new THREE.Vector3(0,1,z), new THREE.Vector3(0,0,z));
    } else if (axis==='y') {
      const y = si/(ny-1||1);
      points.push(new THREE.Vector3(0,y,0), new THREE.Vector3(1,y,0),
                  new THREE.Vector3(1,y,0.3), new THREE.Vector3(0,y,0.3), new THREE.Vector3(0,y,0));
    } else {
      const x = si/(nx-1||1);
      points.push(new THREE.Vector3(x,0,0), new THREE.Vector3(x,1,0),
                  new THREE.Vector3(x,1,0.3), new THREE.Vector3(x,0,0.3), new THREE.Vector3(x,0,0));
    }
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    this.scene.add(new THREE.Line(geo, mat));
  }

  /* ── VOLUME — semi-transparent voxel point cloud ── */
  _renderVolume(data, nx, ny, nz, vmin, range) {
    const total = nx*ny*nz;
    const pos  = new Float32Array(total*3);
    const cols = new Float32Array(total*3);
    let idx=0;
    for (let k=0;k<nz;k++) for (let j=0;j<ny;j++) for (let i=0;i<nx;i++) {
      const v = this._val(data,k,j,i);
      const t = isFinite(v) ? (v-vmin)/range : 0.5;
      const c = this._color(t);
      pos[idx*3]=i/(nx-1||1); pos[idx*3+1]=j/(ny-1||1); pos[idx*3+2]=k/(Math.max(nz-1,1))*0.3;
      cols[idx*3]=c.r; cols[idx*3+1]=c.g; cols[idx*3+2]=c.b;
      idx++;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos,3));
    geo.setAttribute('color',    new THREE.BufferAttribute(cols,3));
    const mat = new THREE.PointsMaterial({
      size: Math.max(0.008, 0.9/Math.max(nx,ny,nz)),
      vertexColors: true, transparent: true, opacity: 0.85,
      sizeAttenuation: true
    });
    this.scene.add(new THREE.Points(geo, mat));
  }

  /* ── CONTOUR — iso-surface lines on face ── */
  _renderContour(data, nx, ny, nz, vmin, range) {
    // First draw surface
    this._renderFaceMesh(data, nx, ny, nz, vmin, range, 'z', Math.floor(nz/2));
    // Draw iso-lines at 10 contour levels
    const nLevels = 10;
    for (let lvl=0; lvl<nLevels; lvl++) {
      const threshold = vmin + (lvl+0.5)/nLevels * (vmax => vmax)(vmin + range);
      const t = (threshold - vmin)/range;
      const color = this._color(t);
      const lines = this._marchingSquares(data, nx, ny, nz, threshold, Math.floor(nz/2));
      if (!lines.length) continue;
      const geo = new THREE.BufferGeometry().setFromPoints(lines.map(([x,y]) => new THREE.Vector3(x,y,0.001)));
      const mat = new THREE.LineBasicMaterial({ color: color.getHex(), linewidth: 2 });
      this.scene.add(new THREE.LineSegments(geo, mat));
    }
  }

  /* Marching squares for iso-contours */
  _marchingSquares(data, nx, ny, nz, threshold, kSlice) {
    const lines = [];
    const k = Math.min(kSlice, nz-1);
    for (let j=0;j<ny-1;j++) {
      for (let i=0;i<nx-1;i++) {
        const v00=this._val(data,k,j,i),   v10=this._val(data,k,j,i+1);
        const v01=this._val(data,k,j+1,i), v11=this._val(data,k,j+1,i+1);
        const c = ((v00>threshold)?8:0)|((v10>threshold)?4:0)|((v01>threshold)?2:0)|((v11>threshold)?1:0);
        const x0=i/(nx-1||1), x1=(i+1)/(nx-1||1), y0=j/(ny-1||1), y1=(j+1)/(ny-1||1);
        const lx=(x0+x1)/2, ly=(y0+y1)/2;
        if (c===0||c===15) continue;
        // Simplified: draw corners
        if ([1,14].includes(c)) lines.push([x1,ly],[lx,y1]);
        else if ([2,13].includes(c)) lines.push([lx,y1],[x0,ly]);
        else if ([3,12].includes(c)) lines.push([x0,ly],[x1,ly]);
        else if ([4,11].includes(c)) lines.push([lx,y0],[x1,ly]);
        else if ([6,9].includes(c))  lines.push([lx,y0],[lx,y1]);
        else if ([7,8].includes(c))  lines.push([x0,ly],[lx,y0]);
        else if ([5,10].includes(c)) lines.push([lx,y0],[x1,ly],[x0,ly],[lx,y1]);
      }
    }
    return lines;
  }

  /* ── VECTORS — arrow glyphs ── */
  _renderVectors(data, nx, ny, nz, vmin, range) {
    // Draw surface first
    this._renderFaceMesh(data, nx, ny, nz, vmin, range, 'z', Math.floor(nz/2));

    // Sample grid for arrows (every ~5 cells)
    const step = Math.max(2, Math.floor(Math.max(nx,ny)/12));
    const k = Math.floor(nz/2);
    const arrowLen = 0.06;

    for (let j=step; j<ny-step; j+=step) {
      for (let i=step; i<nx-step; i+=step) {
        const v = this._val(data,k,j,i);
        const t = isFinite(v) ? (v-vmin)/range : 0.5;
        const color = this._color(t);

        // Gradient-based pseudo-velocity (dx, dy of field)
        const dvdx = (this._val(data,k,j,Math.min(i+1,nx-1)) - this._val(data,k,j,Math.max(i-1,0))) / 2;
        const dvdy = (this._val(data,k,Math.min(j+1,ny-1),i) - this._val(data,k,Math.max(j-1,0),i)) / 2;
        const mag = Math.sqrt(dvdx*dvdx + dvdy*dvdy) || 1;
        const dx = dvdx/mag * arrowLen, dy = dvdy/mag * arrowLen;

        const x0=i/(nx-1||1), y0=j/(ny-1||1), z=0.002;
        const dir = new THREE.Vector3(dx, dy, 0).normalize();
        const arrow = new THREE.ArrowHelper(dir, new THREE.Vector3(x0,y0,z), arrowLen,
          color.getHex(), arrowLen*0.35, arrowLen*0.25);
        this.scene.add(arrow);
      }
    }
  }

  /* ── WARP BY SCALAR — displace mesh in Z by value ── */
  _renderWarp(data, nx, ny, nz, vmin, range) {
    const k = Math.floor(nz/2);
    const warpScale = 0.4;
    const geo = new THREE.PlaneGeometry(1, 1, nx-1, ny-1);
    const pos = geo.attributes.position;
    const colArr = new Float32Array(pos.count*3);

    for (let j=0;j<ny;j++) {
      for (let i=0;i<nx;i++) {
        const idx = j*nx+i;
        const v = this._val(data,k,j,i);
        const t = isFinite(v) ? (v-vmin)/range : 0;
        const col = this._color(t);
        colArr[idx*3]=col.r; colArr[idx*3+1]=col.g; colArr[idx*3+2]=col.b;
        pos.setXYZ(idx, i/(nx-1||1), j/(ny-1||1), t*warpScale);
      }
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colArr,3));
    geo.computeVertexNormals();
    const mat = new THREE.MeshPhongMaterial({
      vertexColors:true, side:THREE.DoubleSide, shininess:50,
      specular: new THREE.Color(0.15,0.15,0.15)
    });
    this.scene.add(new THREE.Mesh(geo, mat));

    // Wireframe overlay
    const wMat = new THREE.MeshBasicMaterial({color:0x223344, wireframe:true, opacity:0.2, transparent:true});
    const wMesh = new THREE.Mesh(geo.clone(), wMat);
    this.scene.add(wMesh);
  }

  /* ── Bounding box ── */
  _addBBox(nx, ny, nz) {
    const depth = nz>2 ? 0.3 : 0.01;
    const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(1,1,depth));
    const mat   = new THREE.LineBasicMaterial({color:0x3a5070, opacity:0.6, transparent:true});
    const box   = new THREE.LineSegments(edges, mat);
    box.position.set(0.5, 0.5, depth/2);
    this.scene.add(box);
  }

  /* ── Public API ── */
  setMode(mode) {
    this.renderMode = mode;
    this._redrawSlice();
  }

  _redrawSlice() {
    if (this._lastHm && this._lastInfo) this.render3DHeatmap(this._lastHm, this._lastInfo);
  }

  setSlice(axis, index) {
    this.sliceAxis  = axis;
    this.sliceIndex = index;
    if (this.renderMode !== 'slice') this.renderMode = 'slice';
    this._redrawSlice();
  }

  resetCamera() {
    this._sph = { theta:0.7, phi:0.9, radius:2.2 };
    this._tgt = new THREE.Vector3(0.5, 0.5, 0.1);
    this._updateCamera();
  }

  setViewAngle(angle) {
    const v = { iso:[0.7,0.9,2.2], front:[0,Math.PI/2,2.0], top:[0,0.05,2.5], side:[Math.PI/2,Math.PI/2,2.0] };
    const [theta,phi,radius] = v[angle]||v.iso;
    this._sph = {theta,phi,radius};
    this._updateCamera();
  }

  onResize() {
    if (!this.container||!this.renderer) return;
    const W=this.container.clientWidth||700, H=this.container.clientHeight||450;
    this.camera.aspect=W/H; this.camera.updateProjectionMatrix();
    this.renderer.setSize(W,H);
  }
}

/* Global helpers */
let viz3dMain=null, viz3dRight=null;
function getViz3d(id) {
  if (id==='canvas-3d') { if(!viz3dMain) viz3dMain=new Visualization3D(id); return viz3dMain; }
  if(!viz3dRight) viz3dRight=new Visualization3D(id); return viz3dRight;
}
