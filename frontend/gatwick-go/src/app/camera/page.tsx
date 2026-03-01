"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  generatePlaneCard,
  validateTicket,
  matchAirlineFromText,
  POINTS_PER_CAPTURE,
  RARITY_LABELS,
  RARITY_COLORS,
} from "@/lib/data";
import type { PlaneCard, BoardingPassTicket } from "@/lib/data";
import {
  addToCollection,
  addPoints,
  getTicketSession,
  startTicketSession,
  getSessionTimeRemaining,
} from "@/lib/store";
import Tesseract from "tesseract.js";

type CameraStep = "ticket" | "capture" | "result";

function formatTimeRemaining(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

// --- Image preprocessing helpers for robust QR detection ---

function grayscaleImageData(src: ImageData): ImageData {
  const pixels = new Uint8ClampedArray(src.data);
  for (let i = 0; i < pixels.length; i += 4) {
    const gray = Math.round(
      pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114
    );
    pixels[i] = gray;
    pixels[i + 1] = gray;
    pixels[i + 2] = gray;
  }
  return new ImageData(pixels, src.width, src.height);
}

function binarizeImageData(src: ImageData, threshold = 128): ImageData {
  const pixels = new Uint8ClampedArray(src.data);
  for (let i = 0; i < pixels.length; i += 4) {
    const gray = Math.round(
      pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114
    );
    const val = gray > threshold ? 255 : 0;
    pixels[i] = val;
    pixels[i + 1] = val;
    pixels[i + 2] = val;
  }
  return new ImageData(pixels, src.width, src.height);
}

export default function CameraPage() {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scanIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const planeFileInputRef = useRef<HTMLInputElement>(null);
  const nativeCameraInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<CameraStep>("ticket");
  const [facingMode, setFacingMode] = useState<"environment" | "user">(
    "environment"
  );
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraErrorType, setCameraErrorType] = useState<"permission" | "notfound" | "generic" | null>(null);
  const [showFlash, setShowFlash] = useState(false);
  const [capturedCard, setCapturedCard] = useState<PlaneCard | null>(null);
  const [pointsEarned, setPointsEarned] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState<string>("");
  const [detecting, setDetecting] = useState(false);
  const [detectError, setDetectError] = useState<string | null>(null);
  const [capturedImageUrl, setCapturedImageUrl] = useState<string | null>(null);
  const [activeTicket, setActiveTicket] = useState<BoardingPassTicket | null>(
    null
  );
  const [timeRemaining, setTimeRemaining] = useState<number>(0);

  // --------------- Check for existing session on mount ---------------
  useEffect(() => {
    const session = getTicketSession();
    if (session) {
      setActiveTicket(session.ticket);
      setStep("capture");
    }
  }, []);

  // --------------- Countdown timer ---------------
  useEffect(() => {
    if (!activeTicket) return;

    const updateTimer = () => {
      const remaining = getSessionTimeRemaining();
      setTimeRemaining(remaining);
      if (remaining <= 0) {
        setActiveTicket(null);
        if (step === "capture") {
          setStep("ticket");
          setScanStatus("");
        }
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [activeTicket, step]);

  // --------------- Camera management ---------------

  const stopCamera = useCallback(() => {
    if (scanIntervalRef.current) {
      clearInterval(scanIntervalRef.current);
      scanIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setCameraReady(false);
  }, []);

  const startCamera = useCallback(
    async (mode: "environment" | "user" = facingMode) => {
      try {
        // Stop any existing stream first
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }
        setCameraError(null);
        setCameraErrorType(null);
        setCameraReady(false);

        // Try exact facingMode first (ensures actual camera switch on iOS),
        // then fall back to ideal if device doesn't support exact constraint
        let stream: MediaStream;
        try {
          stream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: { exact: mode },
              width: { ideal: 1920 },
              height: { ideal: 1080 },
            },
            audio: false,
          });
        } catch (constraintErr) {
          // OverconstrainedError means the exact facingMode isn't available
          // (e.g. device has only one camera) — fall back to ideal
          if (
            constraintErr instanceof DOMException &&
            constraintErr.name === "OverconstrainedError"
          ) {
            stream = await navigator.mediaDevices.getUserMedia({
              video: {
                facingMode: { ideal: mode },
                width: { ideal: 1920 },
                height: { ideal: 1080 },
              },
              audio: false,
            });
          } else {
            throw constraintErr;
          }
        }

        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          setCameraReady(true);
        }
      } catch (err) {
        console.error("Camera error:", err);
        const domErr = err instanceof DOMException ? err : null;
        if (domErr?.name === "NotAllowedError") {
          setCameraErrorType("permission");
          setCameraError(
            "Camera permission was denied. On iPhone, tap the \"Aa\" (or ⓘ) button in Safari's address bar, then tap \"Website Settings\" and set Camera to \"Allow\". Or reload this page to be asked again."
          );
        } else if (domErr?.name === "NotFoundError") {
          setCameraErrorType("notfound");
          setCameraError("No camera found on this device.");
        } else {
          setCameraErrorType("generic");
          setCameraError(
            "Unable to access camera. Please make sure no other app is using it and try again."
          );
        }
      }
    },
    [facingMode]
  );

  const toggleCamera = useCallback(() => {
    const newMode = facingMode === "environment" ? "user" : "environment";
    setFacingMode(newMode);
    startCamera(newMode);
  }, [facingMode, startCamera]);

  // Start camera on mount
  useEffect(() => {
    startCamera();
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --------------- QR Code Scanning (Step 1) ---------------

  useEffect(() => {
    if (step !== "ticket" || !cameraReady) {
      if (scanIntervalRef.current) {
        clearInterval(scanIntervalRef.current);
        scanIntervalRef.current = null;
      }
      return;
    }

    let stopped = false;
    setScanning(true);
    setScanStatus("Looking for QR code...");

    const scanFrame = async () => {
      if (stopped || !videoRef.current || !canvasRef.current) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;

      if (video.readyState !== video.HAVE_ENOUGH_DATA) return;

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

      try {
        const jsQR = (await import("jsqr")).default;
        // Try multiple preprocessing passes for robust detection
        const attempts: ImageData[] = [
          imageData,
          grayscaleImageData(imageData),
          binarizeImageData(imageData, 128),
          binarizeImageData(imageData, 90),
          binarizeImageData(imageData, 180),
        ];

        let code = null;
        for (const attempt of attempts) {
          code = jsQR(attempt.data, attempt.width, attempt.height, {
            inversionAttempts: "attemptBoth",
          });
          if (code && code.data) break;
        }

        if (code && code.data) {
          const ticket = validateTicket(code.data);
          if (ticket) {
            setScanStatus("✅ Ticket validated!");
            setScanning(false);
            if (scanIntervalRef.current) {
              clearInterval(scanIntervalRef.current);
              scanIntervalRef.current = null;
            }
            // Start 30-minute session
            startTicketSession(ticket);
            setActiveTicket(ticket);
            setTimeout(() => {
              setStep("capture");
              setScanStatus("");
            }, 800);
          } else {
            setScanStatus(
              "❌ Invalid ticket — not a valid Gatwick GO boarding pass"
            );
          }
        }
      } catch {
        // jsQR import failed — should not happen
      }
    };

    scanIntervalRef.current = setInterval(scanFrame, 300);

    return () => {
      stopped = true;
      if (scanIntervalRef.current) {
        clearInterval(scanIntervalRef.current);
        scanIntervalRef.current = null;
      }
    };
  }, [step, cameraReady]);

  // --------------- Plane Capture with OCR (Step 2) ---------------

  const handleCapture = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current) return;

    setShowFlash(true);
    setTimeout(() => setShowFlash(false), 300);

    const video = videoRef.current;
    const canvas = canvasRef.current;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
    setCapturedImageUrl(dataUrl);

    setDetecting(true);
    setDetectError(null);

    try {
      const result = await Tesseract.recognize(dataUrl, "eng", {
        logger: () => {},
      });

      const extractedText = result.data.text;
      console.log("OCR extracted text:", extractedText);

      const matchedAirline = matchAirlineFromText(extractedText);

      if (matchedAirline) {
        const card = generatePlaneCard(matchedAirline, dataUrl);
        const earned = POINTS_PER_CAPTURE[card.rarity];

        addToCollection(card);
        addPoints(card);

        setCapturedCard(card);
        setPointsEarned(earned);
        setDetecting(false);
        setStep("result");
        stopCamera();
      } else {
        setDetecting(false);
        setDetectError(
          "No airline name detected. Try getting a clearer shot of the airline branding on the plane."
        );
      }
    } catch (err) {
      console.error("OCR error:", err);
      setDetecting(false);
      setDetectError(
        "Detection failed. Please try again with a clearer image."
      );
    }
  }, [stopCamera]);

  // --------------- Image Import QR Scanning (multi-pass) ---------------

  const handleImageFile = useCallback(async (file: File) => {
    setScanStatus("Processing image...");

    const objectUrl = URL.createObjectURL(file);
    const img = new Image();

    img.onload = async () => {
      // Use an offscreen canvas so we don't interfere with the camera canvas
      const offscreen = document.createElement("canvas");
      offscreen.width = img.naturalWidth;
      offscreen.height = img.naturalHeight;
      const ctx = offscreen.getContext("2d", { willReadFrequently: true });
      if (!ctx) {
        URL.revokeObjectURL(objectUrl);
        setScanStatus("❌ Failed to process image.");
        return;
      }

      ctx.drawImage(img, 0, 0, offscreen.width, offscreen.height);
      const imageData = ctx.getImageData(0, 0, offscreen.width, offscreen.height);
      URL.revokeObjectURL(objectUrl);

      try {
        const jsQR = (await import("jsqr")).default;

        // Pass 1: Raw image with attemptBoth
        let code = jsQR(imageData.data, imageData.width, imageData.height, {
          inversionAttempts: "attemptBoth",
        });

        // Pass 2: Grayscale
        if (!code) {
          const gray = grayscaleImageData(imageData);
          code = jsQR(gray.data, gray.width, gray.height, {
            inversionAttempts: "attemptBoth",
          });
        }

        // Pass 3: Binarize with threshold 128
        if (!code) {
          const bin = binarizeImageData(imageData, 128);
          code = jsQR(bin.data, bin.width, bin.height, {
            inversionAttempts: "attemptBoth",
          });
        }

        // Pass 4: Binarize with lower threshold (for dark/low-contrast images)
        if (!code) {
          const bin2 = binarizeImageData(imageData, 90);
          code = jsQR(bin2.data, bin2.width, bin2.height, {
            inversionAttempts: "attemptBoth",
          });
        }

        // Pass 5: Binarize with higher threshold (for washed-out images)
        if (!code) {
          const bin3 = binarizeImageData(imageData, 180);
          code = jsQR(bin3.data, bin3.width, bin3.height, {
            inversionAttempts: "attemptBoth",
          });
        }

        // Pass 6: Try downscaled if image is very large
        if (!code && (imageData.width > 1000 || imageData.height > 1000)) {
          const scale = 0.5;
          const sw = Math.round(imageData.width * scale);
          const sh = Math.round(imageData.height * scale);
          offscreen.width = sw;
          offscreen.height = sh;
          ctx.drawImage(img, 0, 0, sw, sh);
          const smallData = ctx.getImageData(0, 0, sw, sh);
          code = jsQR(smallData.data, smallData.width, smallData.height, {
            inversionAttempts: "attemptBoth",
          });
          // Also try binarized downscale
          if (!code) {
            const binSmall = binarizeImageData(smallData, 128);
            code = jsQR(binSmall.data, binSmall.width, binSmall.height, {
              inversionAttempts: "attemptBoth",
            });
          }
        }

        if (code && code.data) {
          console.log("QR decoded data:", code.data);
          const ticket = validateTicket(code.data);
          if (ticket) {
            setScanStatus("✅ Ticket validated!");
            setScanning(false);
            if (scanIntervalRef.current) {
              clearInterval(scanIntervalRef.current);
              scanIntervalRef.current = null;
            }
            startTicketSession(ticket);
            setActiveTicket(ticket);
            setTimeout(() => {
              setStep("capture");
              setScanStatus("");
            }, 800);
          } else {
            setScanStatus(
              "QR code found but it's not a valid Gatwick GO boarding pass."
            );
          }
        } else {
          setScanStatus(
            "No QR code found in the image. Try a clearer, well-lit photo of the QR code."
          );
        }
      } catch (err) {
        console.error("QR scan error:", err);
        setScanStatus("❌ Failed to process image. Please try again.");
      }
    };

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      setScanStatus("❌ Could not load the image. Try a different file.");
    };

    img.src = objectUrl;
  }, []);

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleImageFile(file);
      }
      // Reset input so the same file can be re-selected
      e.target.value = "";
    },
    [handleImageFile]
  );

  // --------------- Plane Image Import (Step 2 OCR) ---------------

  const handlePlaneImageFile = useCallback(
    async (file: File) => {
      setDetecting(true);
      setDetectError(null);

      const reader = new FileReader();
      reader.onload = async () => {
        const dataUrl = reader.result as string;
        setCapturedImageUrl(dataUrl);

        try {
          const result = await Tesseract.recognize(dataUrl, "eng", {
            logger: () => {},
          });

          const extractedText = result.data.text;
          console.log("OCR extracted text:", extractedText);

          const matchedAirline = matchAirlineFromText(extractedText);

          if (matchedAirline) {
            const card = generatePlaneCard(matchedAirline, dataUrl);
            const earned = POINTS_PER_CAPTURE[card.rarity];

            addToCollection(card);
            addPoints(card);

            setCapturedCard(card);
            setPointsEarned(earned);
            setDetecting(false);
            setStep("result");
            stopCamera();
          } else {
            setDetecting(false);
            setDetectError(
              "No airline name detected. Try a clearer image with the airline name visible."
            );
          }
        } catch (err) {
          console.error("OCR error:", err);
          setDetecting(false);
          setDetectError(
            "Detection failed. Please try again with a clearer image."
          );
        }
      };

      reader.onerror = () => {
        setDetecting(false);
        setDetectError("Could not read the image file.");
      };

      reader.readAsDataURL(file);
    },
    [stopCamera]
  );

  const handlePlaneFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handlePlaneImageFile(file);
      }
      e.target.value = "";
    },
    [handlePlaneImageFile]
  );

  // --------------- Paste buttons ---------------

  const handlePasteButton = useCallback(async () => {
    try {
      const clipboardItems = await navigator.clipboard.read();
      for (const item of clipboardItems) {
        const imageType = item.types.find((t) => t.startsWith("image/"));
        if (imageType) {
          const blob = await item.getType(imageType);
          const file = new File([blob], "pasted-image.png", {
            type: imageType,
          });
          if (step === "capture") {
            handlePlaneImageFile(file);
          } else {
            handleImageFile(file);
          }
          return;
        }
      }
      if (step === "capture") {
        setDetectError("No image found in clipboard. Copy an image first.");
      } else {
        setScanStatus("❌ No image found in clipboard. Copy an image first.");
      }
    } catch {
      if (step === "capture") {
        setDetectError(
          "Could not read clipboard. Try pasting with Ctrl+V / ⌘V instead."
        );
      } else {
        setScanStatus(
          "❌ Could not read clipboard. Try pasting with Ctrl+V / ⌘V instead."
        );
      }
    }
  }, [step, handleImageFile, handlePlaneImageFile]);

  // --------------- Paste Event Listener (both steps) ---------------

  useEffect(() => {
    if (step !== "ticket" && step !== "capture") return;

    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith("image/")) {
          e.preventDefault();
          const file = items[i].getAsFile();
          if (file) {
            if (step === "capture") {
              handlePlaneImageFile(file);
            } else {
              handleImageFile(file);
            }
          }
          return;
        }
      }
    };

    document.addEventListener("paste", handlePaste);
    return () => document.removeEventListener("paste", handlePaste);
  }, [step, handleImageFile, handlePlaneImageFile]);

  const handleRetake = () => {
    setDetectError(null);
    setCapturedImageUrl(null);
  };

  const handleDone = () => {
    router.push("/collection");
  };

  const handleCaptureAnother = () => {
    setCapturedCard(null);
    setPointsEarned(0);
    setCapturedImageUrl(null);
    setDetectError(null);
    setDetecting(false);
    // Session is still active — go straight to capture, not ticket
    setStep("capture");
    startCamera();
  };

  return (
    <div className="fixed inset-0 bg-black z-40 flex flex-col">
      {/* Camera viewfinder */}
      <div className="relative flex-1 overflow-hidden">
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full object-cover"
          autoPlay
          playsInline
          muted
        />
        <canvas ref={canvasRef} className="hidden" />

        {/* Flash overlay */}
        {showFlash && (
          <div className="absolute inset-0 bg-white capture-flash z-50" />
        )}

        {/* Camera error fallback */}
        {cameraError && (
          <div className="absolute inset-0 flex items-center justify-center bg-gatwick-dark p-8 z-10">
            <div className="text-center">
              <span className="text-5xl block mb-4">📷</span>
              <p className="text-white text-sm mb-4 leading-relaxed">{cameraError}</p>
              <div className="flex flex-col gap-3">
                {/* Native camera fallback — opens the iOS camera app directly */}
                <button
                  onClick={() => {
                    if (nativeCameraInputRef.current) {
                      // Set capture attribute based on current facing mode
                      nativeCameraInputRef.current.setAttribute(
                        "capture",
                        facingMode === "user" ? "user" : "environment"
                      );
                      nativeCameraInputRef.current.click();
                    }
                  }}
                  className="bg-gatwick-blue text-white px-6 py-3 rounded-full text-sm font-bold"
                >
                  📸 Open Camera
                </button>
                {cameraErrorType === "permission" && (
                  <button
                    onClick={() => window.location.reload()}
                    className="bg-white/20 text-white px-6 py-3 rounded-full text-sm font-medium"
                  >
                    🔄 Reload Page
                  </button>
                )}
                <button
                  onClick={() => startCamera()}
                  className="bg-white/10 text-white px-6 py-3 rounded-full text-sm font-medium"
                >
                  Try Again
                </button>
                <button
                  onClick={() => router.push("/")}
                  className="bg-white/10 text-white px-6 py-3 rounded-full text-sm font-medium"
                >
                  Go Back
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Detecting overlay */}
        {detecting && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center z-30">
            <div className="text-center">
              <div className="w-16 h-16 border-4 border-gatwick-blue border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-white font-bold text-lg">
                Detecting airline...
              </p>
              <p className="text-white/60 text-xs mt-1">
                Analyzing image for airline branding
              </p>
            </div>
          </div>
        )}

        {/* Detect error overlay */}
        {detectError && (
          <div className="absolute inset-0 bg-black/80 flex items-center justify-center z-30 p-8">
            <div className="text-center">
              <span className="text-5xl block mb-4">🔍</span>
              <p className="text-red-400 font-bold text-lg mb-2">
                Airline Not Found
              </p>
              <p className="text-white/70 text-sm mb-6">{detectError}</p>
              {capturedImageUrl && (
                <div className="mb-4 rounded-xl overflow-hidden mx-auto w-48 h-32">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={capturedImageUrl}
                    alt="Captured"
                    className="w-full h-full object-cover"
                  />
                </div>
              )}
              <button
                onClick={handleRetake}
                className="bg-gatwick-blue text-white px-8 py-3 rounded-full font-bold text-sm"
              >
                📸 Retake Photo
              </button>
            </div>
          </div>
        )}

        {/* Viewfinder overlay */}
        {step !== "result" && cameraReady && !detecting && !detectError && (
          <div className="absolute inset-0 flex items-center justify-center">
            {step === "ticket" && (
              <div className="relative">
                {/* QR viewfinder square */}
                <div className="w-64 h-64 relative">
                  {/* Corner brackets */}
                  <div className="absolute top-0 left-0 w-8 h-8 border-t-4 border-l-4 border-white rounded-tl-lg" />
                  <div className="absolute top-0 right-0 w-8 h-8 border-t-4 border-r-4 border-white rounded-tr-lg" />
                  <div className="absolute bottom-0 left-0 w-8 h-8 border-b-4 border-l-4 border-white rounded-bl-lg" />
                  <div className="absolute bottom-0 right-0 w-8 h-8 border-b-4 border-r-4 border-white rounded-br-lg" />

                  {/* Scanning line animation */}
                  {scanning && (
                    <div className="absolute left-2 right-2 h-0.5 bg-gatwick-blue animate-bounce opacity-80" />
                  )}

                  <div className="flex items-center justify-center h-full">
                    <p className="text-white/70 text-sm font-medium text-center px-4">
                      Point camera at your
                      <br />
                      ticket QR code
                    </p>
                  </div>
                </div>
              </div>
            )}
            {step === "capture" && (
              <div className="border-2 border-gatwick-blue/70 rounded-full w-64 h-64 flex items-center justify-center">
                <p className="text-white/70 text-sm font-medium text-center px-4">
                  Point at the aircraft
                  <br />& tap capture
                </p>
              </div>
            )}
          </div>
        )}

        {/* Top bar */}
        <div className="absolute top-0 left-0 right-0 safe-top bg-gradient-to-b from-black/60 to-transparent p-4 pt-12 flex items-center justify-between">
          <button
            onClick={() => {
              stopCamera();
              router.back();
            }}
            className="text-white font-medium text-sm bg-white/20 backdrop-blur-sm px-4 py-2 rounded-full"
          >
            ✕ Close
          </button>

          <div className="flex items-center gap-2">
            {/* Session timer badge */}
            {activeTicket && timeRemaining > 0 && (
              <div className="bg-green-500/20 backdrop-blur-sm px-3 py-1.5 rounded-full">
                <span className="text-green-400 text-xs font-bold">
                  ⏱ {formatTimeRemaining(timeRemaining)}
                </span>
              </div>
            )}

            <div className="bg-white/20 backdrop-blur-sm px-3 py-1.5 rounded-full">
              <span className="text-white text-xs font-medium">
                {step === "ticket"
                  ? "Step 1: Scan Ticket"
                  : step === "capture"
                  ? "Step 2: Capture Plane"
                  : "Captured!"}
              </span>
            </div>

            {/* Camera swap button */}
            {step !== "result" && (
              <button
                onClick={toggleCamera}
                className="bg-white/20 backdrop-blur-sm w-10 h-10 rounded-full flex items-center justify-center text-white text-xl active:scale-90 transition-transform"
                aria-label="Switch camera"
              >
                🔄
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Hidden file inputs */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileInputChange}
      />
      <input
        ref={planeFileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handlePlaneFileInputChange}
      />
      {/* Native camera input — used as fallback when getUserMedia is denied */}
      <input
        ref={nativeCameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            if (step === "capture") {
              handlePlaneImageFile(file);
            } else {
              handleImageFile(file);
            }
          }
          e.target.value = "";
        }}
      />

      {/* Bottom controls */}
      {step === "ticket" && (
        <div className="bg-gatwick-dark p-6 safe-bottom">
          <div className="text-center mb-2">
            <p className="text-white font-bold text-lg">Scan Your Ticket</p>
            <p className="text-white/60 text-xs mt-1">
              Point your camera at the QR code on your boarding pass
            </p>
          </div>
          <div className="text-center">
            <p
              className={`text-sm font-medium py-2 ${
                scanStatus.includes("✅")
                  ? "text-green-400"
                  : scanStatus.includes("❌")
                  ? "text-red-400"
                  : "text-white/50"
              }`}
            >
              {scanStatus || (scanning ? "Scanning..." : "Initializing camera...")}
            </p>
            {scanning && (
              <div className="flex items-center justify-center gap-1.5 mt-1">
                <div className="w-1.5 h-1.5 rounded-full bg-gatwick-blue animate-pulse" />
                <div
                  className="w-1.5 h-1.5 rounded-full bg-gatwick-blue animate-pulse"
                  style={{ animationDelay: "0.2s" }}
                />
                <div
                  className="w-1.5 h-1.5 rounded-full bg-gatwick-blue animate-pulse"
                  style={{ animationDelay: "0.4s" }}
                />
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3 my-3">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-white/40 text-xs">or import an image</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Import / Paste buttons */}
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="bg-white/10 text-white px-4 py-2.5 rounded-full text-sm font-medium active:scale-95 transition-transform"
            >
              📁 Import Photo
            </button>
            <button
              onClick={handlePasteButton}
              className="bg-white/10 text-white px-4 py-2.5 rounded-full text-sm font-medium active:scale-95 transition-transform"
            >
              📋 Paste Image
            </button>
          </div>
        </div>
      )}

      {step === "capture" && (
        <div className="bg-gatwick-dark p-6 safe-bottom">
          <div className="text-center mb-4">
            <p className="text-green-400 font-bold text-sm">
              ✅ Ticket validated!
              {activeTicket && (
                <span className="text-white/50 font-normal">
                  {" "}
                  — {activeTicket.flight} to {activeTicket.destination}
                </span>
              )}
            </p>
            <p className="text-white/60 text-xs mt-1">
              Point your camera at a plane — make sure the airline name is
              visible
            </p>
            {timeRemaining > 0 && (
              <p className="text-white/40 text-[10px] mt-1">
                Session expires in {formatTimeRemaining(timeRemaining)}
              </p>
            )}
          </div>
          <div className="flex justify-center">
            <button
              onClick={handleCapture}
              disabled={!cameraReady || detecting}
              className="w-20 h-20 rounded-full border-4 border-white flex items-center justify-center active:scale-95 transition-transform disabled:opacity-50"
            >
              <div className="w-16 h-16 rounded-full bg-gatwick-red" />
            </button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3 my-3">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-white/40 text-xs">or import a plane image</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Import / Paste buttons for plane capture */}
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => planeFileInputRef.current?.click()}
              disabled={detecting}
              className="bg-white/10 text-white px-4 py-2.5 rounded-full text-sm font-medium active:scale-95 transition-transform disabled:opacity-50"
            >
              📁 Import Photo
            </button>
            <button
              onClick={handlePasteButton}
              disabled={detecting}
              className="bg-white/10 text-white px-4 py-2.5 rounded-full text-sm font-medium active:scale-95 transition-transform disabled:opacity-50"
            >
              📋 Paste Image
            </button>
          </div>
        </div>
      )}

      {step === "result" && capturedCard && (
        <div className="bg-gatwick-dark p-6 safe-bottom">
          <div className="text-center mb-4">
            {/* Show captured image thumbnail */}
            {capturedCard.imageUrl && (
              <div className="mb-3 rounded-xl overflow-hidden mx-auto w-40 h-24">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={capturedCard.imageUrl}
                  alt="Captured plane"
                  className="w-full h-full object-cover"
                />
              </div>
            )}
            <p className="text-2xl mb-2">
              {capturedCard.rarity === "shiny"
                ? "🌟"
                : capturedCard.rarity === "rare"
                ? "💎"
                : "✈️"}
            </p>
            <p className="text-white font-bold text-xl">
              {capturedCard.airline.name}
            </p>
            <p className="text-white/70 text-sm">{capturedCard.planeType}</p>
            <p className="text-white/50 text-xs mt-1">
              {capturedCard.flightNumber}
            </p>

            <div className="flex items-center justify-center gap-2 mt-3">
              <span
                className="px-3 py-1 rounded-full text-xs font-bold text-white"
                style={{
                  backgroundColor: RARITY_COLORS[capturedCard.rarity],
                }}
              >
                {RARITY_LABELS[capturedCard.rarity]}
              </span>
              <span className="text-gatwick-gold font-bold text-sm">
                +{pointsEarned} pts
              </span>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleCaptureAnother}
              className="flex-1 bg-white/10 text-white py-3 rounded-2xl font-medium text-sm"
            >
              Capture Another
            </button>
            <button
              onClick={handleDone}
              className="flex-1 bg-gatwick-blue text-white py-3 rounded-2xl font-bold text-sm"
            >
              View Collection
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
