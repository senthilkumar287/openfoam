/* 2D Heatmap Renderer */
let vizEngine = null;

class VisualizationEngine {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
  }

  renderHeatmap(hm) {
    if (!this.canvas || !this.ctx) return;
    if (!hm || !hm.data || !hm.data.length) {
      this.ctx.fillStyle = '#080b0e';
      this.ctx.fillRect(0,0,this.canvas.width,this.canvas.height);
      this.ctx.fillStyle = '#55666f';
      this.ctx.font = '13px JetBrains Mono,monospace';
      this.ctx.textAlign = 'center';
      this.ctx.fillText('No data', this.canvas.width/2, this.canvas.height/2);
      return;
    }

    let data = hm.data;
    // If 3D, take middle z-slice
    if (Array.isArray(data[0]) && Array.isArray(data[0][0])) {
      data = data[Math.floor(data.length/2)];
    }

    const rows = data.length, cols = data[0]?.length || 0;
    if (!cols) return;

    const W = this.canvas.width, H = this.canvas.height;
    const cw = W/cols, ch = H/rows;
    const range = hm.max - hm.min;
    const colorFn = typeof getColormapFn === 'function' ? getColormapFn() :
      (t) => `hsl(${(1-t)*240},100%,${40+t*15}%)`;

    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        const v = data[i][j];
        const norm = isFinite(v) && range > 1e-6 ? (v - hm.min)/range : 0.5;
        this.ctx.fillStyle = colorFn(Math.max(0, Math.min(1, norm)));
        this.ctx.fillRect(j*cw, i*ch, cw+1, ch+1);
      }
    }

    // Colorbar
    const bx = W-45, by = 20, bH = H-40, bW = 18;
    for (let i=0; i<bH; i++) {
      this.ctx.fillStyle = colorFn(1-i/bH);
      this.ctx.fillRect(bx, by+i, bW, 1);
    }
    this.ctx.strokeStyle='rgba(100,150,180,.5)'; this.ctx.lineWidth=1;
    this.ctx.strokeRect(bx,by,bW,bH);
    this.ctx.fillStyle='rgba(200,220,240,.8)'; this.ctx.font='10px JetBrains Mono,monospace';
    this.ctx.textAlign='left';
    this.ctx.fillText(hm.max.toFixed(1), bx+bW+4, by+10);
    this.ctx.fillText(hm.min.toFixed(1), bx+bW+4, by+bH);
  }
}

function initializeVisualization() {
  vizEngine = new VisualizationEngine('canvas-viz');
}

function renderHeatmap(hm) {
  if (!vizEngine) initializeVisualization();
  vizEngine.renderHeatmap(hm);
}

document.addEventListener('DOMContentLoaded', initializeVisualization);
