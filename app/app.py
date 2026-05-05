import io
import base64
import uvicorn
import numpy as np
import torch
import os
import sys
import cv2

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image

try:
    from simple_lama_inpainting import SimpleLama
    from mobile_sam import sam_model_registry, SamPredictor
except ImportError:
    print("Dependencies missing!")
    sys.exit(1)

app = FastAPI()
device = "cuda" if torch.cuda.is_available() else "cpu"
lama = SimpleLama()

sam_checkpoint = "mobile_sam.pt"
model_type = "vit_t"
sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
sam.to(device=device)
predictor = SamPredictor(sam)

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html style="overflow: hidden; touch-action: none;">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>AI Eraser Ultimate</title>
        <style>
            /* Жесткая блокировка системных жестов iOS */
            * { 
                touch-action: none; 
                -webkit-tap-highlight-color: transparent; 
                -webkit-user-select: none; 
                user-select: none; 
            }
            body { 
                margin: 0; background: #111; color: white; font-family: sans-serif; 
                display: flex; flex-direction: column; height: 100vh; 
                overflow: hidden; position: fixed; width: 100%;
            }
            .toolbar { 
                padding: 10px; background: #222; display: flex; gap: 8px; 
                align-items: center; justify-content: center; border-bottom: 1px solid #333; 
                flex-wrap: wrap; z-index: 100;
            }
            #canvas-container { 
                flex-grow: 1; position: relative; background: #000; 
                overflow: hidden; touch-action: none;
            }
            canvas { position: absolute; top: 0; left: 0; touch-action: none; }
            button { padding: 8px 12px; border-radius: 6px; border: 1px solid #444; background: #333; color: white; cursor: pointer; font-size: 13px; }
            button.active { background: #3498db; border-color: #2980b9; }
            .btn-run { background: #27ae60; font-weight: bold; border: none; }
            .btn-hist { background: #8e44ad; border: none; }
            #status { 
                position: absolute; top: 70px; left: 50%; transform: translateX(-50%); 
                background: #3498db; padding: 8px 20px; border-radius: 20px; 
                display: none; z-index: 1000; font-weight: bold; 
            }
            .controls { display: flex; align-items: center; gap: 10px; border-left: 1px solid #444; padding-left: 10px; font-size: 12px; }
            .divider { width: 1px; height: 25px; background: #444; margin: 0 5px; }
        </style>
    </head>
    <body>
        <div id="status">AI IS WORKING...</div>
        <div class="toolbar">
            <button onclick="document.getElementById('fileInput').click()">📁 Open</button>
            <input type="file" id="fileInput" accept="image/*" style="display:none">
            
            <button id="modeBox" class="active" onclick="setMode('box')">📦 Box</button>
            <button id="modeSamLasso" onclick="setMode('samLasso')">🎯 Lasso</button>
            <button id="modeBrush" onclick="setMode('brush')">🖌️ Brush</button>
            <button id="modePan" onclick="setMode('pan')">✋ Pan</button>

            <div class="controls">
                <input type="range" id="brushSize" min="5" max="150" value="40">
            </div>

            <div class="divider"></div>
            <button onclick="undoMask()">↩</button>
            <button onclick="redoMask()">↪</button>

            <div class="divider"></div>
            <button class="btn-hist" onclick="undoImage()">↩ Undo</button>
            <button class="btn-hist" onclick="redoImage()">Redo ↪</button>
            
            <button id="processBtn" class="btn-run" onclick="process()" disabled>ERASE</button>
            <button id="downloadBtn" style="background:#f39c12; border:none; display:none" onclick="downloadImage()">💾 Save</button>
        </div>

        <div id="canvas-container"><canvas id="canvas"></canvas></div>

        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <script>
            // Инициализация Telegram WebApp
            if (window.Telegram && window.Telegram.WebApp) {
                const tg = window.Telegram.WebApp;
                tg.expand();
                tg.ready();
                // ГЛАВНЫЙ ФИКС ДЛЯ СВАЙПОВ ВНИЗ
                tg.disableVerticalSwipes();
            }

            const canvas = document.getElementById('canvas'), ctx = canvas.getContext('2d');
            const container = document.getElementById('canvas-container');
            let mainImg = new Image(), mode = 'box', scale = 1, offsetX = 0, offsetY = 0;
            let paths = [], maskRedoStack = [], imgHistory = [], imgRedoStack = []; 
            let isDown = false, currentPath = null, isPinching = false;
            let lastX = 0, lastY = 0, lastDist = 0;

            // Полная блокировка скролла страницы на уровне JS
            document.addEventListener('touchmove', (e) => { if(e.touches.length === 1) e.preventDefault(); }, { passive: false });

            function setMode(m) {
                mode = m;
                document.querySelectorAll('.toolbar button').forEach(b => b.id && b.id.startsWith('mode') && b.classList.remove('active'));
                document.getElementById('mode' + m.charAt(0).toUpperCase() + m.slice(1)).classList.add('active');
            }

            function getCoords(e) {
                const rect = canvas.getBoundingClientRect();
                const clientX = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
                const clientY = e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
                return { x: (clientX - rect.left - offsetX) / scale, y: (clientY - rect.top - offsetY) / scale };
            }

            document.getElementById('fileInput').onchange = (e) => {
                const reader = new FileReader();
                reader.onload = (ev) => {
                    mainImg = new Image();
                    mainImg.onload = () => {
                        scale = Math.min(container.clientWidth/mainImg.width, container.clientHeight/mainImg.height)*0.8;
                        offsetX = (container.clientWidth - mainImg.width*scale)/2;
                        offsetY = (container.clientHeight - mainImg.height*scale)/2;
                        paths = []; maskRedoStack = []; imgHistory = []; imgRedoStack = [];
                        render();
                        document.getElementById('processBtn').disabled = false;
                    };
                    mainImg.src = ev.target.result;
                };
                reader.readAsDataURL(e.target.files[0]);
            };

            function render() {
                canvas.width = container.clientWidth; canvas.height = container.clientHeight;
                ctx.save();
                ctx.translate(offsetX, offsetY);
                ctx.scale(scale, scale);
                if(mainImg.src) ctx.drawImage(mainImg, 0, 0);
                
                paths.concat(currentPath ? [currentPath] : []).forEach(p => {
                    ctx.fillStyle = ctx.strokeStyle = "rgba(255, 40, 80, 0.5)";
                    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
                    if (p.type === 'brush' || p.type === 'samLasso') {
                        ctx.lineWidth = p.size;
                        ctx.beginPath(); ctx.moveTo(p.points[0].x, p.points[0].y);
                        p.points.forEach(pt => ctx.lineTo(pt.x, pt.y));
                        ctx.stroke();
                    } else if (p.type === 'box') {
                        ctx.lineWidth = 2/scale; ctx.strokeRect(p.x1, p.y1, p.x2-p.x1, p.y2-p.y1);
                    } else if (p.type === 'mask') {
                        if (!p.img) { p.img = new Image(); p.img.onload = render; p.img.src = p.src; }
                        else ctx.drawImage(p.img, 0, 0);
                    }
                });
                ctx.restore();
            }

            // УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК (PointerEvents для Desktop и Одиночного касания)
            container.onpointerdown = (e) => {
                if (!mainImg.src || isPinching || e.buttons > 1 && e.pointerType === 'mouse') return;
                isDown = true;
                const c = getCoords(e);
                lastX = e.clientX; lastY = e.clientY;
                if (mode !== 'pan') {
                    currentPath = { type: mode, points: [c], x1: c.x, y1: c.y, x2: c.x, y2: c.y, size: document.getElementById('brushSize').value/scale };
                }
                // Для iOS важно зафиксировать фокус
                if (e.pointerType === 'touch') canvas.setPointerCapture(e.pointerId);
            };

            window.onpointermove = (e) => {
                if (!isDown || isPinching) return;
                const c = getCoords(e);
                if (mode === 'pan') {
                    offsetX += e.clientX - lastX;
                    offsetY += e.clientY - lastY;
                } else if (mode === 'box') {
                    currentPath.x2 = c.x; currentPath.y2 = c.y;
                } else if (currentPath) {
                    currentPath.points.push(c);
                }
                lastX = e.clientX; lastY = e.clientY;
                render();
            };

            window.onpointerup = async (e) => {
                if (!isDown) return;
                isDown = false;
                if (currentPath) {
                    if (mode === 'box') {
                        sendSegment({ box: [Math.min(currentPath.x1, currentPath.x2), Math.min(currentPath.y1, currentPath.y2), Math.max(currentPath.x1, currentPath.x2), Math.max(currentPath.y1, currentPath.y2)] });
                    } else if (mode === 'samLasso') {
                        sendSegment({ points: currentPath.points.filter((_,i) => i % 5 === 0) });
                    } else if (mode === 'brush') {
                        paths.push(currentPath);
                        maskRedoStack = [];
                    }
                }
                currentPath = null; render();
            };

            // МУЛЬТИТАЧ (Зум) - отдельный блок для предотвращения конфликтов
            container.addEventListener('touchstart', (e) => {
                if (e.touches.length >= 2) {
                    isPinching = true; isDown = false; currentPath = null;
                    lastDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
                    lastX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                    lastY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                }
            }, {passive: false});

            container.addEventListener('touchmove', (e) => {
                if (e.touches.length >= 2 && isPinching) {
                    e.preventDefault();
                    const dist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
                    const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                    const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                    const zoom = dist / lastDist;
                    scale *= zoom;
                    offsetX = midX - (midX - offsetX) * zoom + (midX - lastX);
                    offsetY = midY - (midY - offsetY) * zoom + (midY - lastY);
                    lastDist = dist; lastX = midX; lastY = midY;
                    render();
                }
            }, {passive: false});

            container.addEventListener('touchend', (e) => { if (e.touches.length < 2) isPinching = false; });

            // КОЛЕСИКО
            container.addEventListener('wheel', (e) => {
                e.preventDefault();
                const zoom = Math.exp(-e.deltaY * 0.001);
                const rect = canvas.getBoundingClientRect();
                const mx = e.clientX - rect.left, my = e.clientY - rect.top;
                offsetX = mx - (mx - offsetX) * zoom;
                offsetY = my - (my - offsetY) * zoom;
                scale *= zoom;
                render();
            }, {passive: false});

            async function sendSegment(payload) {
                document.getElementById('status').style.display = 'block';
                const res = await fetch('/segment', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ image: mainImg.src, ...payload })
                });
                const data = await res.json();
                paths.push({ type: 'mask', src: data.mask });
                maskRedoStack = []; document.getElementById('status').style.display = 'none'; render();
            }

            function undoMask() { if(paths.length) maskRedoStack.push(paths.pop()); render(); }
            function redoMask() { if(maskRedoStack.length) paths.push(maskRedoStack.pop()); render(); }
            function undoImage() { if (imgHistory.length > 0) { imgRedoStack.push(mainImg.src); updateMainImage(imgHistory.pop()); } }
            function redoImage() { if (imgRedoStack.length > 0) { imgHistory.push(mainImg.src); updateMainImage(imgRedoStack.pop()); } }
            function updateMainImage(src) { const i = new Image(); i.onload = () => { mainImg = i; render(); }; i.src = src; }

            async function process() {
                document.getElementById('status').style.display = 'block';
                imgHistory.push(mainImg.src); imgRedoStack = [];
                const mCanvas = document.createElement('canvas');
                mCanvas.width = mainImg.width; mCanvas.height = mainImg.height;
                const mctx = mCanvas.getContext('2d');
                mctx.fillStyle = 'black'; mctx.fillRect(0,0, mCanvas.width, mCanvas.height);
                for (const p of paths) {
                    mctx.fillStyle = mctx.strokeStyle = 'white';
                    if (p.type === 'mask') {
                        const mi = await new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = p.src; });
                        mctx.drawImage(mi, 0, 0);
                    } else if (p.type === 'brush') {
                        mctx.lineWidth = p.size; mctx.lineCap = 'round';
                        mctx.beginPath(); mctx.moveTo(p.points[0].x, p.points[0].y);
                        p.points.forEach(pt => mctx.lineTo(pt.x, pt.y)); mctx.stroke();
                    }
                }
                const res = await fetch('/process', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ image: mainImg.src, mask: mCanvas.toDataURL() })
                });
                const data = await res.json();
                updateMainImage(data.result);
                paths = []; maskRedoStack = [];
                document.getElementById('status').style.display = 'none';
                document.getElementById('downloadBtn').style.display='inline-block';
            }

            function downloadImage() { const a = document.createElement('a'); a.href = mainImg.src; a.download = 'ai_edit.jpg'; a.click(); }
        </script>
    </body>
    </html>
    """

@app.post("/segment")
async def segment(data: dict):
    img = Image.open(io.BytesIO(base64.b64decode(data['image'].split(",")[1]))).convert("RGB")
    predictor.set_image(np.array(img))
    if 'box' in data:
        masks, _, _ = predictor.predict(box=np.array(data['box']), multimask_output=False)
    elif 'points' in data:
        pts = np.array([[p['x'], p['y']] for p in data['points']])
        masks, _, _ = predictor.predict(point_coords=pts, point_labels=np.ones(len(pts)), multimask_output=False)
    mask_np = (masks[0] * 255).astype(np.uint8)
    mask_np = cv2.dilate(mask_np, np.ones((5, 5), np.uint8), iterations=2)
    h, w = mask_np.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, 0] = 255
    rgba[:, :, 3] = (mask_np > 0) * 160
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    return {"mask": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"}

@app.post("/process")
async def process_image(data: dict):
    img = Image.open(io.BytesIO(base64.b64decode(data['image'].split(",")[1]))).convert("RGB")
    mask = Image.open(io.BytesIO(base64.b64decode(data['mask'].split(",")[1]))).convert("L")
    res = lama(img, mask)
    buf = io.BytesIO()
    res.save(buf, format="JPEG", quality=95)
    return JSONResponse({"result": f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
