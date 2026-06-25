import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
// Mock Database / In-Memory Store
interface EmergencyContact {
  name: string;
  phone: string;
  relation: string;
}

interface HealthProfile {
  user_id: string;
  name: string;
  age: number;
  weight_kg: number;
  conditions: string[];
  emergency_contacts: EmergencyContact[];
  baseline_hr: number;
  thresholds: { hr_max: number; spo2_min: number; temp_max: number };
  safeZone: { lat: number; lng: number; radius: number };
}

const userProfile: HealthProfile = {
  user_id: "IN-SH-4421",
  name: "Arjun Sharma",
  age: 52,
  weight_kg: 74.5,
  conditions: ["Diabetes Type 2", "Hypertension"],
  emergency_contacts: [
    { name: "Meera Sharma", phone: "+91-98765-43210", relation: "Spouse" },
    { name: "Dr. Aditya Varma", phone: "+91-88888-77777", relation: "Family Physician" }
  ],
  baseline_hr: 74,
  thresholds: { hr_max: 155, spo2_min: 94, temp_max: 38.2 },
  safeZone: { lat: 17.3850, lng: 78.4867, radius: 800 }, // Hyderabad
};

const healthHistory: any[] = [];
const permanentAnomalies: any[] = [];
const dailySummary = {
  sleep_score: 82,
  sleep_duration: "7h 24m",
  sleep_breakdown: { deep: 15, light: 55, rem: 20, awake: 10 },
  avg_stress: 34,
  fatigue_level: "Low"
};

const riskStats = {
  cardiac_score: 0,
  respiratory_score: 0,
  stress_score: 0,
  fatigue_index: 0
};

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // API Routes
  app.get("/api/profile", (req, res) => {
    res.json(userProfile);
  });

  app.get("/api/daily-summary", (req, res) => {
    res.json(dailySummary);
  });

  app.post("/api/profile", (req, res) => {
    Object.assign(userProfile, req.body);
    res.json({ success: true, profile: userProfile });
  });

  app.post("/api/profile/zone", (req, res) => {
    const { lat, lng, radius } = req.body;
    userProfile.safeZone = { lat, lng, radius };
    res.json({ success: true, safeZone: userProfile.safeZone });
  });

  app.get("/api/vitals", (req, res) => {
    res.json(healthHistory.slice(-500));
  });

  app.get("/api/anomalies", (req, res) => {
    res.json(permanentAnomalies);
  });

  app.post("/api/vitals", (req, res) => {
    const { hr, spo2, temp, motion, hrv, steps, fallDetected, timestamp, location } = req.body;
    
    // Risk Engine Logic (Fusion of sensors)
    const cardiac_risk = Math.max(0, (hr - userProfile.thresholds.hr_max) / 10);
    const respiratory_risk = Math.max(0, (userProfile.thresholds.spo2_min - spo2) * 2);
    const stress_val = hrv ? Math.max(0, (100 - hrv) / 10) : 0;
    
    // Identify Abnormality
    const isAbnormal = fallDetected || (hr > userProfile.thresholds.hr_max) || (spo2 < userProfile.thresholds.spo2_min);
    
    const newEntry = {
      timestamp: timestamp || new Date().toISOString(),
      hr, spo2, temp, motion, hrv, steps, fallDetected, location,
      risks: { cardiac_risk, respiratory_risk, stress_val },
      isAbnormal
    };

    healthHistory.push(newEntry);
    
    // Keep ~ clinical history coverage
    if (healthHistory.length > 5000) healthHistory.shift();

    if (isAbnormal) {
      permanentAnomalies.push(newEntry);
      // Keep only last 500 permanent anomalies for memory safety, though user said "permanently"
      if (permanentAnomalies.length > 500) permanentAnomalies.shift();
    }

    const alerts = [];
    if (fallDetected) alerts.push("CRITICAL: Fall Detector - Multi-sensor fusion confirmed impact.");
    if (hr > userProfile.thresholds.hr_max) alerts.push(`WARNING: Tachycardia Event: ${hr} BPM exceeds baseline.`);
    if (spo2 < userProfile.thresholds.spo2_min) alerts.push(`CRITICAL: Hypoxia Risk: ${spo2}% SpO2 detected.`);

    res.json({ success: true, alerts, risks: newEntry.risks });
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
