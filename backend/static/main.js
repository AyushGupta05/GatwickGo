/**
 * Aircraft Detection Web App - Frontend JavaScript
 * * Handles:
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
    lastFrames: [],
    mode: 'OPENSKY',
    location: null, // {lat, lon, radius_km}
};

// DOM Elements
const elements = {
    video: document.getElementById('webcam-video'),
    previewImage: document.getElementById('preview-image'),
    canvas: document.getElementById('canvas'),
    captureBtn: document.getElementById('capture-btn'),
    clearBtn: document.getElementById('clear-btn'),
    fileInput: document.getElementById('file-input'),
    statusMessage: document.getElementById('status-message'),
    frameCounter: document.getElementById('frame-counter'),
    locBtn: document.getElementById('loc-btn'),
    locStatus: document.getElementById('loc-status'),
    modeLive: document.getElementById('mode-live'),
    modeSandbox: document.getElementById('mode-sandbox'),
    
    // New UI Elements
    loadingOverlay: document.getElementById('loading-overlay'),
    resultsSection: document.getElementById('results-section'),
    resAirline: document.getElementById('resAirline'),
    resFamily: document.getElementById('resFamily'),
    resFlightMatch: document.getElementById('resFlightMatch'),
    resFactCard: document.getElementById('fact-card'),
    resFactText: document.getElementById('resFactText'),
    resFactSource: document.getElementById('resFactSource'),
    
    // Modal UI Elements
    modalConfidence: document.getElementById('modalConfidence'),
    barConfidence: document.getElementById('barConfidence'),
    modalPhase: document.getElementById('modalPhase'),
    modalPhaseConf: document.getElementById('modalPhaseConf'),
    barPhaseConf: document.getElementById('barPhaseConf'),
    modalCues: document.getElementById('modalCues'),
    modalFeedData: document.getElementById('modalFeedData'),
    modalFrames: document.getElementById('modalFrames'),
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
        state.lastFrames = frames; // keep local copies for preview

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
        displayMatch(result.match, result.feed, result.result, result.enrichment);
        displayFact(result.enrichment);
        updatePreviewFromResult(result.result);
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
    elements.resultsSection.classList.remove('hidden');
    // ensure preview shows current best frame once results are ready
    updatePreviewFromResult(result);
    
    // 1. Primary Data (UI View)
    const confidencePercent = Math.round((result.confidence || 0) * 100);
    const confMeta = getConfidenceMeta(confidencePercent);

    elements.resAirline.innerHTML = `
        ${escapeHtml(result.airline || "Unknown Airline")}
        <span class="ml-2 text-[10px] font-semibold px-2 py-0.5 rounded-full inline-flex items-center ${confMeta.pill}">
            ${confMeta.level} ${confidencePercent}%
        </span>
    `;
    elements.resFamily.innerHTML = `<i class="fa-solid fa-plane-up mr-2 text-xs"></i> ${result.aircraft_family || "Unknown Aircraft"}`;

    // 2. Modal Data (Advanced Info)
    elements.modalConfidence.innerText = `${confidencePercent}% (${confMeta.level})`;
    elements.barConfidence.style.width = `${confidencePercent}%`;
    elements.barConfidence.className = `h-2 rounded-full transition-all duration-500 ${confMeta.bar}`;

    const phase = result.phase || 'Unknown';
    const phaseConf = Math.round((result.phase_confidence || 0) * 100);
    elements.modalPhase.innerText = phase;
    elements.modalPhaseConf.innerText = `${phaseConf}%`;
    elements.barPhaseConf.style.width = `${phaseConf}%`;

    // Populate Cues
    if (result.cues && result.cues.length > 0) {
        elements.modalCues.innerHTML = result.cues.map(cue => 
            `<li class="border-b border-slate-200/60 pb-2 last:border-0 last:pb-0"><span class="text-gatwick-blue font-bold mr-2">→</span>${escapeHtml(cue)}</li>`
        ).join('');
    } else {
        elements.modalCues.innerHTML = '<li class="text-slate-500 italic">No visual cues extracted</li>';
    }

    elements.modalFrames.innerText = framesProcessed;
}

/**
 * Update the preview image after classification.
 */
function updatePreviewFromResult(result) {
    if (!result) return;
    const bestIdx = getBestFrameIndex(result, state.lastFrames);
    const bestFrame = state.lastFrames[bestIdx];
    if (bestFrame) {
        showPreview(bestFrame);
    }
}

/**
 * Display provider + match info
 */
function displayMatch(match, feed, classification = null, enrichment = null) {
    const detectedAirline = (classification?.airline && classification.airline !== 'UNKNOWN') ? classification.airline : null;
    const detectionPercent = Math.round(((classification?.confidence) || 0) * 100);
    const detectionMeta = getConfidenceMeta(detectionPercent);
    const originData = enrichment?.origin || null;
    const originCity = originData?.city || match?.best?.flight?.origin_city || match?.best?.flight?.origin;
    const originIata = originData?.iata || match?.best?.flight?.origin_iata;
    const originIcao = originData?.icao || match?.best?.flight?.origin_icao;
    const originText = formatOrigin(originCity, originIata, originIcao);

    if (!match || !match.best) {
        let fallbackText = detectedAirline
            ? `Gemini: ${escapeHtml(detectedAirline)} (${detectionMeta.level} ${detectionPercent}%)`
            : 'No matching flights found nearby.';
        if (originText) {
            fallbackText += `<br><span class="text-[11px] text-slate-600">Coming from: ${originText}</span>`;
        }
        elements.resFlightMatch.innerHTML = `<span class="text-slate-500 font-normal">${fallbackText}</span>`;
    } else {
        const best = match.best.flight || {};
        const score = Math.round((match.best.score || 0) * 100);
        const airlineLabel = best.airline || detectedAirline || 'Unknown';
        
        let subtitle = `
            ${escapeHtml(airlineLabel)} • Match Score: ${score}%
        `;
        if (originText) {
            subtitle += `<br><span class="text-[11px] text-slate-600">Coming from: ${originText}</span>`;
        }
        if (detectedAirline) {
            subtitle += `<br><span class="text-[10px] font-semibold px-2 py-0.5 rounded-full inline-flex items-center ${detectionMeta.pill}">
                Gemini: ${escapeHtml(detectedAirline)} (${detectionMeta.level} ${detectionPercent}%)
            </span>`;
        } else if (classification) {
            subtitle += `<br><span class="text-[10px] text-slate-500">Gemini confidence ${detectionPercent}% (${detectionMeta.level})</span>`;
        }

        elements.resFlightMatch.innerHTML = `
            Flight <span class="text-gatwick-blue">${escapeHtml(best.flight_number || best.callsign || 'N/A')}</span>
            <br>
            <span class="text-[11px] font-normal text-slate-500 mt-0.5 block">
                ${subtitle}
            </span>
        `;
    }

    // Modal Feed Data Population
    const provider = feed?.provider || 'unknown';
    const flightCount = feed?.flight_count ?? '0';
    const observer = feed?.observer || null;

    elements.modalFeedData.innerHTML = `
        <div class="mb-1"><span class="text-slate-400">Provider:</span> ${escapeHtml(provider)} ${feed?.mode ? '(' + escapeHtml(feed.mode) + ')' : ''}</div>
        <div class="mb-1"><span class="text-slate-400">Flights Fetched:</span> ${flightCount}</div>
        ${observer ? `<div><span class="text-slate-400">Observer Data:</span> ${observer.lat.toFixed(4)}, ${observer.lon.toFixed(4)} (Radius: ${observer.radius_km || '—'}km)</div>` : ''}
    `;
}

/**
 * Display grounded aircraft fact if available.
 */
function displayFact(enrichment) {
    const card = elements.resFactCard;
    if (!card) return;
    const fact = enrichment?.fact;
    if (!fact || !fact.text) {
        card.classList.add('hidden');
        return;
    }
    elements.resFactText.textContent = fact.text;

    const src = (fact.sources && fact.sources[0]) || null;
    if (src && src.url) {
        elements.resFactSource.textContent = src.title || src.url;
        elements.resFactSource.href = src.url;
        elements.resFactSource.classList.remove('hidden');
    } else {
        elements.resFactSource.classList.add('hidden');
    }
    card.classList.remove('hidden');
}

/**
 * Display error in results section
 */
function displayError(errorMessage) {
    elements.resultsSection.classList.remove('hidden');
    elements.resAirline.innerText = "Error";
    elements.resFamily.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-2 text-xs"></i> ${escapeHtml(errorMessage)}`;
    elements.resFlightMatch.innerHTML = `<span class="text-gatwick-red font-normal">Classification failed.</span>`;
}

/**
 * Update frame counter display
 */
function updateFrameCounter(current, total) {
    elements.frameCounter.textContent = `Processing frame ${current}/${total}...`;
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

    elements.resultsSection.classList.add('hidden');
    hidePreview();
    elements.loadingOverlay.classList.remove('hidden');
    elements.loadingOverlay.classList.add('flex');
    showStatus(`Classifying ${file.name}...`, 'info');

    try {
        const dataUrl = await readFileAsDataURL(file);
        state.lastFrames = [dataUrl];
        await classifyFrames([dataUrl]);
    } catch (error) {
        console.error('Upload classify error:', error);
        showStatus(`Error: ${error.message}`, 'error');
        displayError(error.message);
    } finally {
        elements.fileInput.value = '';
        elements.loadingOverlay.classList.add('hidden');
        elements.loadingOverlay.classList.remove('flex');
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
 * Show status message (Toast UI update)
 */
function showStatus(message, type = 'info') {
    const msg = elements.statusMessage;
    msg.textContent = message;
    
    // Reset classes
    msg.className = 'absolute top-20 left-4 right-4 z-50 text-center py-2 px-4 rounded-lg text-sm font-semibold shadow-md toast-enter';
    
    if (type === 'error') {
        msg.classList.add('bg-red-100', 'text-red-800', 'border', 'border-red-200');
    } else if (type === 'success') {
        msg.classList.add('bg-green-100', 'text-green-800', 'border', 'border-green-200');
    } else {
        msg.classList.add('bg-blue-100', 'text-blue-800', 'border', 'border-blue-200');
    }

    // Trigger animation
    msg.classList.remove('hidden');
    setTimeout(() => {
        msg.classList.remove('toast-enter');
        msg.classList.add('toast-active');
    }, 10);
    
    // Auto-clear
    if (type !== 'error') {
        setTimeout(() => {
            msg.classList.remove('toast-active');
            msg.classList.add('toast-enter');
            setTimeout(() => msg.classList.add('hidden'), 300);
        }, 4000);
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show captured frame preview over the video area.
 */
function showPreview(dataUrl) {
    if (!dataUrl) return;
    elements.previewImage.src = dataUrl;
    elements.previewImage.classList.remove('hidden');
    elements.video.classList.add('opacity-0');
}

/**
 * Hide preview and reveal live video.
 */
function hidePreview() {
    elements.previewImage.classList.add('hidden');
    elements.previewImage.src = '';
    elements.video.classList.remove('opacity-0');
}

/**
 * Map a 0-100 confidence score to UI styles and labels.
 */
function getConfidenceMeta(percent) {
    if (percent >= 75) {
        return { level: 'High', pill: 'bg-green-100 text-green-800', bar: 'bg-green-500' };
    }
    if (percent >= 50) {
        return { level: 'Medium', pill: 'bg-amber-100 text-amber-800', bar: 'bg-amber-500' };
    }
    return { level: 'Low', pill: 'bg-red-100 text-red-800', bar: 'bg-red-500' };
}

/**
 * Decide which captured frame to display using sharpness scores/source frame indices.
 */
function getBestFrameIndex(result, frames) {
    if (!frames || frames.length === 0) return 0;
    if (result && result.sharpness_scores) {
        let bestIdx = 0;
        let bestScore = -Infinity;
        Object.entries(result.sharpness_scores).forEach(([k, v]) => {
            const idx = parseInt(k, 10);
            const score = Number(v) || 0;
            if (score > bestScore) {
                bestScore = score;
                bestIdx = idx;
            }
        });
        if (bestIdx < frames.length) return bestIdx;
    }
    if (result && Array.isArray(result.source_frames) && result.source_frames.length > 0) {
        const idx = result.source_frames[0];
        if (Number.isInteger(idx) && idx < frames.length) return idx;
    }
    return 0;
}

/**
 * Format origin display text.
 */
function formatOrigin(origin, iata, icao) {
    if (!origin && !iata && !icao) return '';
    const code = iata || icao || '';
    if (origin && code) return `${escapeHtml(origin)} (${escapeHtml(code)})`;
    if (origin) return escapeHtml(origin);
    return escapeHtml(code);
}

// ============================================================================
// EVENT HANDLERS
// ============================================================================

function setMode(mode) {
    state.mode = mode;
    
    if (mode === 'OPENSKY') {
        elements.modeLive.className = 'flex-1 py-1.5 text-sm font-semibold rounded-md bg-white shadow-sm text-gatwick-blue transition-all';
        elements.modeSandbox.className = 'flex-1 py-1.5 text-sm font-medium rounded-md text-slate-500 hover:text-slate-700 transition-all bg-transparent';
    } else {
        elements.modeSandbox.className = 'flex-1 py-1.5 text-sm font-semibold rounded-md bg-white shadow-sm text-gatwick-blue transition-all';
        elements.modeLive.className = 'flex-1 py-1.5 text-sm font-medium rounded-md text-slate-500 hover:text-slate-700 transition-all bg-transparent';
    }
    
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
            updateLocationStatus(`GPS: ${latitude.toFixed(3)}, ${longitude.toFixed(3)}`);
            elements.locStatus.classList.replace("text-slate-400", "text-gatwick-blue");
            showStatus('Location set successfully.', 'success');
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
        updateLocationStatus(`Default: ${state.location.lat.toFixed(3)}, ${state.location.lon.toFixed(3)}`);
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
    hidePreview();
    
    // Show loading UI
    elements.resultsSection.classList.add('hidden');
    elements.loadingOverlay.classList.remove('hidden');
    elements.loadingOverlay.classList.add('flex');
    
    try {
        showStatus(`Capturing ${CONFIG.NUM_FRAMES} frames...`, 'info');
        const frames = await captureBurst(CONFIG.NUM_FRAMES, CONFIG.FRAME_INTERVAL);
        clearFrameCounter();
        
        await classifyFrames(frames);
    } catch (error) {
        console.error('Capture error:', error);
        showStatus(`Capture error: ${error.message}`, 'error');
        displayError(error.message);
    } finally {
        state.isCapturing = false;
        elements.captureBtn.disabled = false;
        elements.clearBtn.disabled = false;
        elements.loadingOverlay.classList.add('hidden');
        elements.loadingOverlay.classList.remove('flex');
    }
}

/**
 * Handle clear button click
 */
function handleClear() {
    state.lastClassification = null;
    state.lastFrames = [];
    elements.resultsSection.classList.add('hidden');
    clearFrameCounter();
    hidePreview();
    if (elements.resFactCard) elements.resFactCard.classList.add('hidden');
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
    elements.captureBtn.addEventListener('click', handleCapture);
    elements.clearBtn.addEventListener('click', handleClear);
    elements.fileInput.addEventListener('change', handleFileUpload);
    elements.locBtn.addEventListener('click', useGeolocation);
    elements.modeLive.addEventListener('click', () => setMode('OPENSKY'));
    elements.modeSandbox.addEventListener('click', () => setMode('SANDBOX'));
    window.addEventListener('beforeunload', handleUnload);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showStatus('Your browser does not support webcam access', 'error');
        elements.captureBtn.disabled = true;
        return;
    }

    await initWebcam();

    setMode('OPENSKY');
    ensureDefaultLocation();
    if (!state.location) {
        updateLocationStatus('No location set');
    }
}

document.addEventListener('DOMContentLoaded', init);
