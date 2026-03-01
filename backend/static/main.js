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

// Auth / layout elements
const authElements = {
    screen: document.getElementById('auth-screen'),
    email: document.getElementById('auth-email'),
    password: document.getElementById('auth-password'),
    loginBtn: document.getElementById('auth-login-btn'),
    signupBtn: document.getElementById('auth-signup-btn'),
    error: document.getElementById('auth-error'),
    signoutBtn: document.getElementById('signout-btn'),
    userChip: document.getElementById('user-chip'),
    appShell: document.getElementById('app-shell'),
};

let supabaseClient = null;
let authState = { session: null };
let appInitialized = false;

function readStoredSupabaseToken(storage) {
    if (!storage) return null;
    try {
        for (let i = 0; i < storage.length; i += 1) {
            const key = storage.key(i);
            if (!key || !key.startsWith('sb-') || !key.endsWith('-auth-token')) {
                continue;
            }

            const raw = storage.getItem(key);
            if (!raw) continue;

            const parsed = JSON.parse(raw);
            const token =
                parsed?.access_token ||
                parsed?.currentSession?.access_token ||
                parsed?.session?.access_token ||
                parsed?.data?.session?.access_token ||
                null;
            if (token) {
                return token;
            }
        }
    } catch (err) {
        console.warn('Could not read Supabase token from storage', err);
    }
    return null;
}

function getBrowserStorage(kind) {
    try {
        return window[kind];
    } catch (err) {
        console.warn(`Could not access ${kind}`, err);
        return null;
    }
}

function getStoredSupabaseToken() {
    return readStoredSupabaseToken(getBrowserStorage('localStorage')) || readStoredSupabaseToken(getBrowserStorage('sessionStorage'));
}

const PROGRESS_STORAGE_KEYS = {
    USER_ID: 'gatwick-go-user-id',
    POINTS: 'gatwick-go-points',
    COLLECTION: 'gatwick-go-collection',
    REDEEMED: 'gatwick-go-redeemed',
    TICKET_SESSION: 'gatwick-go-ticket-session',
};
const SHARED_PROGRESS_COOKIE = 'gatwick-go-session-progress';
const SHARED_COLLECTION_LIMIT = 24;

function readCookie(name) {
    if (typeof document === 'undefined') return null;
    const prefix = `${name}=`;
    const cookies = document.cookie.split(';').map((entry) => entry.trim());
    for (const cookie of cookies) {
        if (cookie.startsWith(prefix)) {
            return cookie.slice(prefix.length);
        }
    }
    return null;
}

function writeCookie(name, value) {
    if (typeof document === 'undefined') return;
    document.cookie = `${name}=${value}; path=/; SameSite=Lax`;
}

function clearCookie(name) {
    if (typeof document === 'undefined') return;
    document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax`;
}

function readSharedProgressCookie() {
    const raw = readCookie(SHARED_PROGRESS_COOKIE);
    if (!raw) return null;
    try {
        return JSON.parse(decodeURIComponent(raw));
    } catch (err) {
        console.warn('Could not parse shared progress cookie', err);
        return null;
    }
}

function sanitizeSharedCard(card) {
    if (!card || typeof card !== 'object') return null;
    return {
        id: card.id,
        airline: card.airline,
        planeType: card.planeType,
        flightNumber: card.flightNumber,
        rarity: card.rarity,
        capturedAt: card.capturedAt,
    };
}

function writeSharedProgressCookie(pointsTotal, card) {
    const current = readSharedProgressCookie() || {};
    const currentCollection = Array.isArray(current.collection) ? current.collection : [];
    const nextCollection = card
        ? [sanitizeSharedCard(card), ...currentCollection.filter((entry) => entry?.id !== card.id)].filter(Boolean).slice(0, SHARED_COLLECTION_LIMIT)
        : currentCollection.slice(0, SHARED_COLLECTION_LIMIT);

    writeCookie(
        SHARED_PROGRESS_COOKIE,
        encodeURIComponent(JSON.stringify({
            points: Number.isFinite(pointsTotal) ? Number(pointsTotal) : 0,
            collection: nextCollection,
            updatedAt: Date.now(),
        }))
    );
}

function getProgressStorage() {
    return getBrowserStorage('sessionStorage') || getBrowserStorage('localStorage');
}

function readProgressItem(key, fallback) {
    const sessionStore = getBrowserStorage('sessionStorage');
    const localStore = getBrowserStorage('localStorage');
    try {
        const sessionValue = sessionStore?.getItem(key);
        if (sessionValue) {
            return JSON.parse(sessionValue);
        }

        const localValue = localStore?.getItem(key);
        if (!localValue) return fallback;

        const parsed = JSON.parse(localValue);
        sessionStore?.setItem(key, localValue);
        return parsed;
    } catch (err) {
        console.warn(`Could not read progress key ${key}`, err);
        return fallback;
    }
}

function writeProgressItem(key, value) {
    const storage = getProgressStorage();
    if (!storage) return;
    try {
        storage.setItem(key, JSON.stringify(value));
        getBrowserStorage('localStorage')?.removeItem(key);
    } catch (err) {
        console.warn(`Could not write progress key ${key}`, err);
    }
}

function clearProgressStorage() {
    Object.values(PROGRESS_STORAGE_KEYS).forEach((key) => {
        getBrowserStorage('sessionStorage')?.removeItem(key);
        getBrowserStorage('localStorage')?.removeItem(key);
    });
    clearCookie(SHARED_PROGRESS_COOKIE);
}

function upsertProgressCard(card) {
    const current = readProgressItem(PROGRESS_STORAGE_KEYS.COLLECTION, []);
    const collection = Array.isArray(current) ? current.filter((entry) => entry?.id !== card.id) : [];
    const isNewCard = collection.length === (Array.isArray(current) ? current.length : 0);
    collection.unshift(card);
    writeProgressItem(PROGRESS_STORAGE_KEYS.COLLECTION, collection);
    return isNewCard;
}

function syncSessionPoints(apiResult) {
    const awarded = Number.isFinite(apiResult?.points_awarded) ? Number(apiResult.points_awarded) : 50;
    if (Number.isFinite(apiResult?.points_total)) {
        writeProgressItem(PROGRESS_STORAGE_KEYS.POINTS, Number(apiResult.points_total));
        return Number(apiResult.points_total);
    }

    const currentPoints = Number(readProgressItem(PROGRESS_STORAGE_KEYS.POINTS, 0)) || 0;
    const nextPoints = currentPoints + Math.max(0, awarded);
    writeProgressItem(PROGRESS_STORAGE_KEYS.POINTS, nextPoints);
    return nextPoints;
}

function notifyParentOfSessionProgress(payload) {
    if (!window.parent || window.parent === window) return;
    try {
        window.parent.postMessage(
            {
                type: 'gatwick-go-session-progress',
                payload,
            },
            '*'
        );
    } catch (err) {
        console.warn('Failed to post session progress to parent window', err);
    }
}

const AIRLINE_CARD_META = {
    'British Airways': { id: 'ba', logo: '🇬🇧', color: '#2E3092', country: 'United Kingdom' },
    'easyJet': { id: 'ej', logo: '🟠', color: '#FF6600', country: 'United Kingdom' },
    'Wizz Air': { id: 'wz', logo: '💜', color: '#CE0E71', country: 'Hungary' },
    'TUI Airways': { id: 'tom', logo: '🟦', color: '#00A0E1', country: 'United Kingdom' },
    'Vueling': { id: 'vlg', logo: '🟡', color: '#FFC72C', country: 'Spain' },
    'Emirates': { id: 'ek', logo: '✈️', color: '#D71A21', country: 'United Arab Emirates' },
    'Qatar Airways': { id: 'qtr', logo: '🇶🇦', color: '#5C0D34', country: 'Qatar' },
    'Turkish Airlines': { id: 'tk', logo: '🇹🇷', color: '#E31837', country: 'Turkey' },
    'Norse Atlantic Airways': { id: 'n0', logo: '🛫', color: '#1C4FA1', country: 'Norway' },
    'Delta Air Lines': { id: 'dal', logo: '🔺', color: '#C8102E', country: 'United States' },
};

// ============================================================================
// AUTHENTICATION
// ============================================================================

function ensureSupabase() {
    if (!window.supabase || !window.SUPABASE_URL || !window.SUPABASE_ANON_KEY) {
        console.warn('Supabase env missing');
        return false;
    }
    if (!supabaseClient) {
        supabaseClient = window.supabase.createClient(window.SUPABASE_URL, window.SUPABASE_ANON_KEY);
    }
    return true;
}

function showAuth(message) {
    if (authElements.error) {
        authElements.error.textContent = message || '';
        authElements.error.classList.toggle('hidden', !message);
    }
    authElements.screen.classList.remove('hidden');
    authElements.appShell.classList.add('hidden');
}

function hideAuth() {
    authElements.screen.classList.add('hidden');
    authElements.appShell.classList.remove('hidden');
}

function setUserChip(email) {
    if (!authElements.userChip) return;
    if (email) {
        authElements.userChip.textContent = email;
        authElements.userChip.classList.remove('hidden');
    } else {
        authElements.userChip.classList.add('hidden');
    }
}

async function handleLogin(isSignup = false) {
    if (!ensureSupabase()) {
        showAuth('Supabase configuration missing.');
        return;
    }
    const email = (authElements.email?.value || '').trim();
    const password = authElements.password?.value || '';
    if (!email || !password) {
        showAuth('Enter email and password.');
        return;
    }
    const btn = isSignup ? authElements.signupBtn : authElements.loginBtn;
    btn.disabled = true;
    showAuth('');
    try {
        if (isSignup) {
            const { error } = await supabaseClient.auth.signUp({ email, password });
            if (error) throw error;
        }
        const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
        if (error) throw error;
        authState.session = data.session;
        onSessionReady(data.session);
    } catch (err) {
        console.error(err);
        showAuth(err.message || 'Authentication failed.');
    } finally {
        btn.disabled = false;
    }
}

async function handleSignout() {
    if (supabaseClient) {
        await supabaseClient.auth.signOut();
    }
    authState.session = null;
    setUserChip(null);
    clearProgressStorage();
    window.location.href = '/signin';
}

function bindAuthHandlers() {
    authElements.loginBtn?.addEventListener('click', () => handleLogin(false));
    authElements.signupBtn?.addEventListener('click', () => handleLogin(true));
    authElements.signoutBtn?.addEventListener('click', handleSignout);
}

async function restoreSession() {
    if (!ensureSupabase()) {
        showAuth('Supabase configuration missing.');
        return;
    }
    try {
        const { data } = await supabaseClient.auth.getSession();
        if (data?.session) {
            authState.session = data.session;
            onSessionReady(data.session);
        } else {
            showAuth();
        }
    } catch (err) {
        console.error('Failed to restore auth session', err);
        showAuth('Could not restore your session. Please sign in again.');
    }
    supabaseClient.auth.onAuthStateChange((_event, session) => {
        if (session) {
            authState.session = session;
            onSessionReady(session);
        } else {
            authState.session = null;
            setUserChip(null);
            clearProgressStorage();
            showAuth();
        }
    });
}

function onSessionReady(session) {
    hideAuth();
    setUserChip(session?.user?.email || 'Signed in');
    if (!appInitialized) {
        appInitialized = true;
        init(); // start app setup once
    }
}

function slugifyAirlineName(name) {
    return String(name || 'unknown')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'unknown';
}

function getAirlineCardMeta(name) {
    return AIRLINE_CARD_META[name] || {
        id: slugifyAirlineName(name),
        logo: '✈️',
        color: '#003DA5',
        country: 'Unknown',
    };
}

function buildCachedCaptureCard(apiResult) {
    const classification = apiResult?.result || {};
    const airlineName = classification.airline || apiResult?.captured_airline;
    const planeType =
        apiResult?.captured_model ||
        apiResult?.captured_family_display_name ||
        classification.aircraft_family;

    if (!airlineName || airlineName === 'UNKNOWN' || !planeType || planeType === 'UNKNOWN') {
        return null;
    }

    const confidence = Number(classification.confidence || 0);
    let rarity = 'common';
    if (confidence >= 0.85) {
        rarity = 'shiny';
    } else if (confidence >= 0.65) {
        rarity = 'rare';
    }

    const bestFlight = apiResult?.match?.best?.flight || {};
    const meta = getAirlineCardMeta(airlineName);
    const stableId = `capture-${apiResult.collection_item_key || 'session'}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    return {
        id: stableId,
        airline: {
            id: meta.id,
            name: airlineName,
            logo: meta.logo,
            color: meta.color,
            country: meta.country,
        },
        planeType,
        flightNumber: bestFlight.flight_number || bestFlight.callsign || 'UNKNOWN',
        rarity,
        capturedAt: new Date().toISOString(),
        imageUrl: Array.isArray(state.lastFrames) && state.lastFrames.length > 0 ? state.lastFrames[0] : undefined,
    };
}

function syncLocalProgressCache(apiResult) {
    if (typeof window === 'undefined' || !apiResult) return;

    const nextPointsTotal = syncSessionPoints(apiResult);
    const card = buildCachedCaptureCard(apiResult);
    let cardCached = false;
    if (card) {
        cardCached = upsertProgressCard(card);
    }

    writeSharedProgressCookie(nextPointsTotal, card);

    notifyParentOfSessionProgress({
        pointsAwarded: Number.isFinite(apiResult?.points_awarded) ? Number(apiResult.points_awarded) : 50,
        pointsTotal: nextPointsTotal,
        card,
        capturedAirline: apiResult?.captured_airline || apiResult?.result?.airline || null,
        capturedModel: apiResult?.captured_model || apiResult?.result?.aircraft_model || apiResult?.result?.aircraft_family || null,
        flightNumber: apiResult?.match?.best?.flight?.flight_number || apiResult?.match?.best?.flight?.callsign || null,
        imageUrl: card?.imageUrl || null,
        confidence: Number.isFinite(apiResult?.result?.confidence) ? Number(apiResult.result.confidence) : null,
        capturedAt: card?.capturedAt || new Date().toISOString(),
    });

    return { cardCached, pointsTotal: nextPointsTotal };
}

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

        // Attempt to include Supabase session JWT so backend RLS works
        const authToken = getStoredSupabaseToken();

        const headers = { 'Content-Type': 'application/json' };
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch('/api/classify', {
            method: 'POST',
            headers,
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

        const sessionProgress = syncLocalProgressCache(result) || {};
        state.lastClassification = result.result;
        displayResults(result.result, result.frames_processed);
        displayMatch(result.match, result.feed, result.result, result.enrichment);
        displayFact(result.enrichment);
        updatePreviewFromResult(result.result);
        const rewardSuffix = Number.isFinite(result.points_awarded) && result.points_awarded > 0
            ? ` and +${result.points_awarded} points saved`
            : '';
        const storageWarnings = Array.isArray(result.storage_warnings) ? result.storage_warnings : [];
        if (storageWarnings.length > 0) {
            console.warn('Persistence warnings:', storageWarnings);
        }
        const matchPercent = Number.isFinite(result.match_score)
            ? Math.round(result.match_score * 100)
            : null;
        const collectionSuffix = sessionProgress.cardCached
            ? ', session updated'
            : result.collection_saved
            ? ', collection updated'
            : result.already_in_collection
            ? ', already in collection'
            : buildCachedCaptureCard(result)
            ? ', session updated'
            : matchPercent !== null
            ? `, match ${matchPercent}% did not qualify`
            : '';
        showStatus(
            `Classification successful (${result.frames_processed} frames processed${rewardSuffix}${collectionSuffix}${storageWarnings.length ? ', check storage warnings' : ''})`,
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
    if (!authState.session) {
        showStatus('Please sign in first.', 'error');
        return;
    }
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

async function boot() {
    bindAuthHandlers();
    if (!ensureSupabase()) {
        showAuth('Supabase configuration missing.');
        return;
    }
    // Keep capture disabled until session arrives
    elements.captureBtn.disabled = true;
    await restoreSession();
}

document.addEventListener('DOMContentLoaded', boot);
