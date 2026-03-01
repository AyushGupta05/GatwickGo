/**
 * Aircraft Detection Web App - Frontend JavaScript
 * 
 * Handles:
 * - Webcam access and video stream
 * - Frame capture from canvas
 * - Burst capture simulation (multiple frames)
 * - API communication with backend
 * - Results display
 */

// Configuration
const CONFIG = {
    NUM_FRAMES: 8,           // Number of frames to capture in burst
    FRAME_INTERVAL: 50,      // Milliseconds between frames
    VIDEO_WIDTH: 1280,
    VIDEO_HEIGHT: 720,
    DEFAULT_RADIUS_KM: 40,
};

// State
let state = {
    stream: null,
    isCapturing: false,
    lastClassification: null,
    mode: 'OPENSKY',
    location: null, // {lat, lon, radius_km}
};

// DOM Elements
const elements = {
    video: document.getElementById('webcam-video'),
    canvas: document.getElementById('canvas'),
    captureBtn: document.getElementById('capture-btn'),
    clearBtn: document.getElementById('clear-btn'),
    fileInput: document.getElementById('file-input'),
    resultBox: document.getElementById('result-box'),
    statusMessage: document.getElementById('status-message'),
    frameCounter: document.getElementById('frame-counter'),
    locBtn: document.getElementById('loc-btn'),
    locStatus: document.getElementById('loc-status'),
    modeLive: document.getElementById('mode-live'),
    modeSandbox: document.getElementById('mode-sandbox'),
    matchBox: document.getElementById('match-box'),
};

// ============================================================================
// WEBCAM INITIALIZATION
// ============================================================================

/**
 * Initialize webcam stream
 */
async function initWebcam() {
    try {
        showStatus('Accessing webcam...', 'info');
        
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: CONFIG.VIDEO_WIDTH },
                height: { ideal: CONFIG.VIDEO_HEIGHT },
                facingMode: 'environment',
            },
            audio: false,
        });

        elements.video.srcObject = stream;
        state.stream = stream;

        // Wait for video to load
        await new Promise((resolve) => {
            elements.video.onloadedmetadata = () => {
                elements.video.play();
                resolve();
            };
        });

        showStatus('Webcam ready', 'success');
        elements.captureBtn.disabled = false;
    } catch (error) {
        console.error('Webcam error:', error);
        showStatus(`Webcam error: ${error.message}`, 'error');
        elements.captureBtn.disabled = true;
    }
}

// ============================================================================
// FRAME CAPTURE
// ============================================================================

/**
 * Capture a single frame from the video stream
 */
function captureFrame() {
    const context = elements.canvas.getContext('2d');
    elements.canvas.width = elements.video.videoWidth;
    elements.canvas.height = elements.video.videoHeight;
    
    context.drawImage(elements.video, 0, 0);
    return elements.canvas.toDataURL('image/jpeg', 0.95);
}

/**
 * Capture a burst of frames
 */
async function captureBurst(numFrames, intervalMs) {
    const frames = [];
    
    for (let i = 0; i < numFrames; i++) {
        frames.push(captureFrame());
        updateFrameCounter(i + 1, numFrames);
        
        if (i < numFrames - 1) {
            await sleep(intervalMs);
        }
    }
    
    return frames;
}

/**
 * Sleep for specified milliseconds
 */
function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// ============================================================================
// CLASSIFICATION API
// ============================================================================

/**
 * Send frames to backend for classification
 */
async function classifyFrames(frames) {
    try {
        showStatus('Classifying image...', 'info');

        const body = {
            images: frames.map((data) => ({ data })),
            mode: state.mode,
        };

        if (state.location) {
            body.location = {
                lat: state.location.lat,
                lon: state.location.lon,
                radius_km: state.location.radius_km || CONFIG.DEFAULT_RADIUS_KM,
            };
        }

        const response = await fetch('/api/classify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Classification failed');
        }

        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || 'Unknown error');
        }

        state.lastClassification = result.result;
        displayResults(result.result, result.frames_processed);
        displayMatch(result.match, result.feed);
        showStatus(
            `Classification successful (${result.frames_processed} frames processed)`,
            'success'
        );
    } catch (error) {
        console.error('Classification error:', error);
        showStatus(`Error: ${error.message}`, 'error');
        displayError(error.message);
    }
}

// ============================================================================
// UI UPDATES
// ============================================================================

/**
 * Display classification results
 */
function displayResults(result, framesProcessed) {
    const resultBox = elements.resultBox;
    
    const confidencePercent = Math.round(result.confidence * 100);
    const phase = result.phase || 'unknown';
    const phaseConf = Math.round((result.phase_confidence || 0) * 100);
    const cuesHtml = result.cues && result.cues.length > 0
        ? `<ul class="cues-list">${result.cues.map((cue) => `<li>${cue}</li>`).join('')}</ul>`
        : '<p style="color: #999; font-size: 13px;">No visual cues extracted</p>';

    resultBox.innerHTML = `
        <div class="result-content">
            <div class="result-item">
                <div class="result-label">🚁 Airline</div>
                <div class="result-value">${escapeHtml(result.airline)}</div>
            </div>
            
            <div class="result-item">
                <div class="result-label">✈️ Aircraft Family</div>
                <div class="result-value">${escapeHtml(result.aircraft_family)}</div>
            </div>
            
            <div class="result-item">
                <div class="result-label">🎯 Confidence</div>
                <div class="result-value">${confidencePercent}%</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${result.confidence * 100}%"></div>
                </div>
            </div>

            <div class="result-item">
                <div class="result-label">🛫/🛬 Phase</div>
                <div class="result-value">${phase}</div>
                <div class="result-subtext">Confidence: ${phaseConf}%</div>
            </div>
            
            <div class="result-item">
                <div class="result-label">💡 Visual Cues</div>
                ${cuesHtml}
            </div>
            
            <div class="frame-display">
                📷 Processed from ${framesProcessed} frame(s)
            </div>
        </div>
    `;
    
    resultBox.classList.remove('empty-state', 'loading');
}

/**
 * Display provider + match info
 */
function displayMatch(match, feed) {
    const box = elements.matchBox;
    if (!box) return;

    if (!match || !match.best) {
        box.innerHTML = `<p style="color:#666;">No match yet.</p>`;
        box.classList.remove('loading');
        return;
    }

    const best = match.best.flight || {};
    const score = match.best.score || 0;
    const provider = feed?.provider || 'unknown';
    const flightCount = feed?.flight_count ?? '—';
    const observer = feed?.observer || null;

    box.innerHTML = `
        <div class="result-content">
            <div class="result-item">
                <div class="result-label">Feed</div>
                <div class="result-value">${provider} ${feed?.mode ? '(' + feed.mode + ')' : ''}</div>
                <div class="result-subtext">Flights fetched: ${flightCount}</div>
            </div>
            <div class="result-item">
                <div class="result-label">Best Match</div>
                <div class="result-value">${best.flight_number || 'N/A'} — ${best.airline || ''}</div>
                <div class="result-subtext">
                    Family: ${best.aircraft_family || 'unknown'} · Score: ${(score * 100).toFixed(1)}%
                </div>
            </div>
            ${observer ? `
            <div class="result-item">
                <div class="result-label">Observer</div>
                <div class="result-value">${observer.lat.toFixed(3)}, ${observer.lon.toFixed(3)}</div>
                <div class="result-subtext">radius ${observer.radius_km || '—'} km</div>
            </div>` : ''}
        </div>
    `;
    box.classList.remove('empty-state', 'loading');
}

/**
 * Display error in results box
 */
function displayError(errorMessage) {
    const resultBox = elements.resultBox;
    resultBox.innerHTML = `
        <div class="empty-state">
            <p style="color: #d32f2f; font-weight: 600; margin-bottom: 8px;">⚠️ Error</p>
            <p>${escapeHtml(errorMessage)}</p>
        </div>
    `;
    resultBox.classList.remove('loading');
}

/**
 * Update frame counter display
 */
function updateFrameCounter(current, total) {
    elements.frameCounter.textContent = `Capturing frame ${current}/${total}...`;
}

/**
 * Clear frame counter
 */
function clearFrameCounter() {
    elements.frameCounter.textContent = '';
}

/**
 * Handle file upload and classification
 */
async function handleFileUpload(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    elements.resultBox.innerHTML = `
        <div>
            <div class="spinner"></div>
            <p>Uploading and classifying...</p>
        </div>
    `;
    elements.resultBox.classList.add('loading');
    showStatus(`Classifying ${file.name}...`, 'info');

    try {
        const dataUrl = await readFileAsDataURL(file);
        await classifyFrames([dataUrl]);
    } catch (error) {
        console.error('Upload classify error:', error);
        showStatus(`Error: ${error.message}`, 'error');
        displayError(error.message);
    } finally {
        elements.fileInput.value = '';
    }
}

function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

/**
 * Show status message
 */
function showStatus(message, type = 'info') {
    const msg = elements.statusMessage;
    msg.textContent = message;
    msg.className = `status-message show ${type}`;
    
    // Auto-clear after 5 seconds if not error
    if (type !== 'error') {
        setTimeout(() => {
            msg.classList.remove('show');
        }, 5000);
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// EVENT HANDLERS
// ============================================================================

function setMode(mode) {
    state.mode = mode;
    elements.modeLive.classList.toggle('active', mode === 'OPENSKY');
    elements.modeSandbox.classList.toggle('active', mode === 'SANDBOX');
    showStatus(`Mode set to ${mode === 'OPENSKY' ? 'Live (OpenSky)' : 'Sandbox replay'}`, 'info');
}

function updateLocationStatus(text) {
    elements.locStatus.textContent = text;
}

function useGeolocation() {
    if (!navigator.geolocation) {
        showStatus('Geolocation not supported in this browser.', 'error');
        return;
    }
    showStatus('Grabbing your location...', 'info');
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const { latitude, longitude } = pos.coords;
            state.location = { lat: latitude, lon: longitude, radius_km: CONFIG.DEFAULT_RADIUS_KM };
            updateLocationStatus(`Using your location: ${latitude.toFixed(3)}, ${longitude.toFixed(3)}`);
            showStatus('Location set. Capture to classify & match.', 'success');
        },
        (err) => {
            console.error('Geo error', err);
            showStatus(`Location error: ${err.message}`, 'error');
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 10000 }
    );
}

function ensureDefaultLocation() {
    if (state.location) return;
    if (window.DEFAULT_OBSERVER) {
        state.location = {
            lat: window.DEFAULT_OBSERVER.lat,
            lon: window.DEFAULT_OBSERVER.lon,
            radius_km: window.DEFAULT_OBSERVER.radius_km || CONFIG.DEFAULT_RADIUS_KM,
        };
        updateLocationStatus(`Using default: ${state.location.lat.toFixed(3)}, ${state.location.lon.toFixed(3)}`);
    }
}

/**
 * Handle capture button click
 */
async function handleCapture() {
    if (state.isCapturing) return;
    
    state.isCapturing = true;
    elements.captureBtn.disabled = true;
    elements.clearBtn.disabled = true;
    
    // Show loading state
    elements.resultBox.innerHTML = `
        <div>
            <div class="spinner"></div>
            <p>Capturing burst and classifying...</p>
        </div>
    `;
    elements.resultBox.classList.add('loading');
    
    try {
        // Capture burst
        showStatus(`Capturing ${CONFIG.NUM_FRAMES} frames...`, 'info');
        const frames = await captureBurst(CONFIG.NUM_FRAMES, CONFIG.FRAME_INTERVAL);
        clearFrameCounter();
        
        // Classify
        await classifyFrames(frames);
    } catch (error) {
        console.error('Capture error:', error);
        showStatus(`Capture error: ${error.message}`, 'error');
        displayError(error.message);
    } finally {
        state.isCapturing = false;
        elements.captureBtn.disabled = false;
        elements.clearBtn.disabled = false;
    }
}

/**
 * Handle clear button click
 */
function handleClear() {
    state.lastClassification = null;
    elements.resultBox.innerHTML = `
        <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                <circle cx="12" cy="13" r="4"></circle>
            </svg>
            <p>Awaiting classification...</p>
        </div>
    `;
    elements.resultBox.classList.remove('empty-state', 'loading');
    clearFrameCounter();
    showStatus('Results cleared', 'info');
}

/**
 * Handle window unload
 */
function handleUnload() {
    if (state.stream) {
        state.stream.getTracks().forEach((track) => {
            track.stop();
        });
    }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

/**
 * Initialize the application
 */
async function init() {
    // Attach event listeners
    elements.captureBtn.addEventListener('click', handleCapture);
    elements.clearBtn.addEventListener('click', handleClear);
    elements.fileInput.addEventListener('change', handleFileUpload);
    elements.locBtn.addEventListener('click', useGeolocation);
    elements.modeLive.addEventListener('click', () => setMode('OPENSKY'));
    elements.modeSandbox.addEventListener('click', () => setMode('SANDBOX'));
    window.addEventListener('beforeunload', handleUnload);

    // Check browser support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showStatus('Your browser does not support webcam access', 'error');
        elements.captureBtn.disabled = true;
        return;
    }

    // Initialize webcam
    await initWebcam();

    // Default mode and location status
    setMode('OPENSKY');
    ensureDefaultLocation();
    if (!state.location) {
        updateLocationStatus('No location yet; click "Use My Location" or rely on default LGW');
    }
}

// Start the app when the page loads
document.addEventListener('DOMContentLoaded', init);
