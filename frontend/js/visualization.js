class VisualizationEngine {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.data = null;
    }

    renderHeatmap(heatmapData) {
        if (!heatmapData || !heatmapData.data || heatmapData.data.length === 0) {
            console.error('Invalid heatmap data:', heatmapData);
            this.ctx.fillStyle = '#ccc';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            this.ctx.fillStyle = '#000';
            this.ctx.font = '14px Arial';
            this.ctx.fillText('No data', 10, 30);
            return;
        }
        
        const { data, min, max } = heatmapData;
        const rows = data.length;
        const cols = data[0] ? data[0].length : 0;
        
        if (cols === 0) {
            console.error('Empty data array');
            return;
        }
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        const cellWidth = this.canvas.width / cols;
        const cellHeight = this.canvas.height / rows;
        
        const range = max - min;

        for (let i = 0; i < rows; i++) {
            for (let j = 0; j < cols; j++) {
                const value = data[i][j];
                const normalized = range > 0.001 ? (value - min) / range : 0.5;
                
                const color = this.getColor(normalized);
                this.ctx.fillStyle = color;
                this.ctx.fillRect(j * cellWidth, i * cellHeight, cellWidth, cellHeight);
            }
        }

        this.drawColorBar(min, max);
    }

    getColor(normalized) {
        const hue = (1 - normalized) * 240;
        const saturation = 100;
        const lightness = 40 + (normalized * 10);
        
        return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
    }

    drawColorBar(min, max) {
        const barWidth = 30;
        const barHeight = 200;
        const x = this.canvas.width - 50;
        const y = (this.canvas.height - barHeight) / 2;

        for (let i = 0; i < barHeight; i++) {
            const normalized = 1 - (i / barHeight);
            const color = this.getColor(normalized);
            this.ctx.fillStyle = color;
            this.ctx.fillRect(x, y + i, barWidth, 1);
        }

        this.ctx.strokeStyle = '#333';
        this.ctx.lineWidth = 1.5;
        this.ctx.strokeRect(x, y, barWidth, barHeight);

        this.ctx.fillStyle = '#333';
        this.ctx.font = 'bold 12px Arial';
        this.ctx.textAlign = 'left';
        this.ctx.fillText(max.toFixed(1), x + barWidth + 8, y + 12);
        this.ctx.fillText(min.toFixed(1), x + barWidth + 8, y + barHeight - 2);
    }

    clear() {
        this.ctx.fillStyle = 'white';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
}

let vizEngine = null;

function initializeVisualization() {
    vizEngine = new VisualizationEngine('canvas-viz');
}

function renderHeatmap(heatmapData) {
    if (!vizEngine) initializeVisualization();
    vizEngine.renderHeatmap(heatmapData);
}

document.addEventListener('DOMContentLoaded', initializeVisualization);
