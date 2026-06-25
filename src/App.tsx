/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'motion/react';
import { 
  Heart, 
  Wind, 
  Thermometer, 
  Activity, 
  ShieldCheck, 
  MapPin, 
  Brain, 
  User, 
  RefreshCw,
  LogOut,
  Zap,
  Clock,
  AlertTriangle,
  Moon,
  Coffee
} from 'lucide-react';
import { GoogleGenAI } from "@google/genai";
import Markdown from 'react-markdown';
import { VitalsChart } from './components/VitalsChart.tsx';
import { AlertPanel } from './components/AlertPanel.tsx';
import { MapZone } from './components/MapZone.tsx';
import { RiskGauge } from './components/RiskGauge.tsx';

// Initialize Gemini at Module Level
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });

interface Vital {
  timestamp: string;
  hr: number;
  spo2: number;
  temp: number;
  motion: number;
  hrv?: number;
  steps?: number;
  fallDetected: boolean;
  location?: { lat: number; lng: number };
  risks?: {
    cardiac_risk: number;
    respiratory_risk: number;
    stress_val: number;
  };
}

interface Alert {
  id: string;
  message: string;
  type: 'emergency' | 'warning' | 'info';
  timestamp: Date;
}

export default function App() {
  const [vitals, setVitals] = useState<Vital[]>([]);
  const [anomalies, setAnomalies] = useState<Vital[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isSimulating, setIsSimulating] = useState(true);
  const [profile, setProfile] = useState<any>(null);
  const [dailySummary, setDailySummary] = useState<any>(null);
  const [aiInsight, setAiInsight] = useState<string>("");
  const [healthRoadmap, setHealthRoadmap] = useState<string>("");
  const [isRefreshingInsight, setIsRefreshingInsight] = useState(false);
  const [isGeneratingRoadmap, setIsGeneratingRoadmap] = useState(false);
  const [userLocation, setUserLocation] = useState<[number, number]>([17.3850, 78.4867]);

  // ... (existing code)

  const generateHealthRoadmap = async () => {
    if (!ai || isGeneratingRoadmap) return;
    setIsGeneratingRoadmap(true);
    try {
      const historySummary = vitals.slice(-100).map(v => `HR:${v.hr},SpO2:${v.spo2}`).join("|");
      const prompt = `
        As a senior clinical health strategist, analyze this patient data:
        Profile: Age ${profile?.age}, Conditions: ${profile?.conditions?.join(", ")}
        Recent Vitals Trend (last 100 samples): ${historySummary}
        Anomalies recorded: ${anomalies.length}
        Sleep Score: ${dailySummary?.sleep_score}

        Provide a "Weekly Health Improvement Roadmap" with:
        1. "Improvement Path": 3 specific steps to optimize cardiovascular stability.
        2. "Risk Forecast": Probabilistic assessment for the next 7 days based on current trends.
        3. "Nutritional/Lifestyle Shift": One Indian-context specific dietary adjustment.
        Keep it professional, concise, and structured in Markdown.
      `;

      const response = await ai.models.generateContent({
        model: "gemini-1.5-flash",
        contents: prompt
      });

      setHealthRoadmap(response.text());
    } catch (e: any) {
      console.error("Roadmap Error:", e);
      setHealthRoadmap("Roadmap generation paused due to high demand. Please try again soon.");
    } finally {
      setIsGeneratingRoadmap(false);
    }
  };
  
  // Advanced State
  const [manualSteps, setManualSteps] = useState(5000);
  const [activePortal, setActivePortal] = useState<'user' | 'doctor' | 'family' | 'system'>('user');
  const [manualHr, setManualHr] = useState(75);
  const [manualSpo2, setManualSpo2] = useState(98);
  const [manualTemp, setManualTemp] = useState(36.6);
  const [manualHrv, setManualHrv] = useState(70);
  const [newAgeInput, setNewAgeInput] = useState<number>(0);
  const [newConditionInput, setNewConditionInput] = useState("");

  const simInterval = useRef<any>(null);

  useEffect(() => {
    fetchProfile();
    fetchDailySummary();
    fetchInitialVitals();
    fetchAnomalies();
  }, []);

  const fetchAnomalies = async () => {
    try {
      const res = await fetch('/api/anomalies');
      const data = await res.json();
      setAnomalies(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchDailySummary = async () => {
    try {
      const res = await fetch('/api/daily-summary');
      const data = await res.json();
      setDailySummary(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (isSimulating) {
      simInterval.current = setInterval(simulateReading, 3000);
    } else {
      clearInterval(simInterval.current);
    }
    return () => clearInterval(simInterval.current);
  }, [isSimulating]);

  const fetchProfile = async () => {
    try {
      const res = await fetch('/api/profile');
      const data = await res.json();
      setProfile(data);
      if (data.safeZone) {
        setUserLocation([data.safeZone.lat, data.safeZone.lng]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const updateProfile = async (newAge?: number, conditions?: string[]) => {
    try {
      const res = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ age: newAge, conditions })
      });
      const data = await res.json();
      setProfile(data.profile);
      setAlerts(prev => [{
        id: Math.random().toString(36),
        message: 'Patient profile updated successfully.',
        type: 'info',
        timestamp: new Date()
      }, ...prev]);
    } catch (e) {
      console.error(e);
    }
  };

  const postManualReading = async () => {
    const dr = {
      hr: manualHr,
      spo2: manualSpo2,
      temp: manualTemp,
      hrv: manualHrv,
      steps: manualSteps,
      motion: 0.1,
      fallDetected: false,
      timestamp: new Date().toISOString(),
      location: { lat: userLocation[0], lng: userLocation[1] }
    };

    try {
      const res = await fetch('/api/vitals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dr)
      });
      const result = await res.json();
      setVitals(prev => [...prev.slice(-19), dr]);

      if (result.alerts && result.alerts.length > 0) {
        result.alerts.forEach((msg: string) => {
          setAlerts(prev => [{
            id: Math.random().toString(36),
            message: msg,
            type: msg.includes('CRITICAL') ? 'emergency' : 'warning',
            timestamp: new Date()
          }, ...prev]);
        });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const updateSafeZone = async (lat: number, lng: number) => {
    try {
      const res = await fetch('/api/profile/zone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat, lng, radius: profile?.safeZone?.radius || 500 })
      });
      const data = await res.json();
      setProfile((prev: any) => ({ ...prev, safeZone: data.safeZone }));
      
      const newAlert: Alert = {
        id: Math.random().toString(36),
        message: `Safe Zone updated to: ${lat.toFixed(4)}, ${lng.toFixed(4)}`,
        type: 'info',
        timestamp: new Date()
      };
      setAlerts(prev => [newAlert, ...prev]);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchInitialVitals = async () => {
    try {
      const res = await fetch('/api/vitals');
      const data = await res.json();
      setVitals(data);
    } catch (e) {
      console.error(e);
    }
  };

  const simulateReading = async () => {
    const shouldSpike = Math.random() > 0.95;
    const fallChance = Math.random() > 0.996;

    const newLat = userLocation[0] + (Math.random() - 0.5) * 0.002;
    const newLng = userLocation[1] + (Math.random() - 0.5) * 0.002;
    setUserLocation([newLat, newLng]);

    const dr = {
      hr: shouldSpike ? Math.floor(145 + Math.random() * 20) : Math.floor(65 + Math.random() * 15),
      spo2: shouldSpike ? Math.floor(88 + Math.random() * 5) : Math.floor(96 + Math.random() * 4),
      temp: 36.5 + (Math.random() * 0.5),
      hrv: Math.floor(40 + Math.random() * 40),
      steps: manualSteps + Math.floor(Math.random() * 10),
      motion: Math.random(),
      fallDetected: fallChance,
      timestamp: new Date().toISOString(),
      location: { lat: newLat, lng: newLng }
    };
    setManualSteps(dr.steps);

    try {
      const res = await fetch('/api/vitals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dr)
      });
      const result = await res.json();
      
      setVitals(prev => [...prev.slice(-49), { ...dr, risks: result.risks }]);
      if (dr.hr > (profile?.thresholds?.hr_max || 155) || dr.spo2 < (profile?.thresholds?.spo2_min || 94) || dr.fallDetected) {
        fetchAnomalies();
      }

      if (result.alerts && result.alerts.length > 0) {
        result.alerts.forEach((msg: string) => {
          let enhancedMsg = msg;
          if (msg.includes('Fall') && profile?.safeZone) {
            const dist = getDistance(newLat, newLng, profile.safeZone.lat, profile.safeZone.lng);
            if (dist > profile.safeZone.radius) {
              enhancedMsg = `CRITICAL: Fall detected OUTSIDE protected zone. Alerting Emergency Dispatch.`;
            }
          }
          setAlerts(prev => [{
            id: Math.random().toString(36),
            message: enhancedMsg,
            type: enhancedMsg.includes('CRITICAL') ? 'emergency' : 'warning',
            timestamp: new Date()
          }, ...prev]);
        });
      }
    } catch (e) { console.error(e); }
  };

  const getDistance = (lat1: number, lon1: number, lat2: number, lon2: number) => {
    const R = 6371e3; // metres
    const r1 = lat1 * Math.PI / 180;
    const r2 = lat2 * Math.PI / 180;
    const dr = (lat2 - lat1) * Math.PI / 180;
    const dl = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(dr / 2) * Math.sin(dr / 2) +
      Math.cos(r1) * Math.cos(r2) *
      Math.sin(dl / 2) * Math.sin(dl / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c; // in metres
  };

  const getAIInsight = async () => {
    setIsRefreshingInsight(true);
    try {
      const recentData = vitals.slice(-10);
      const prompt = `
        Analyze this recent smartwatch health data and provide a concise (2-sentence) "Smart Coaching" insight.
        User Profile: Age ${profile?.age}, Conditions: ${profile?.conditions?.join(", ")}.
        Recent Data (Last 10 readings): ${JSON.stringify(recentData)}
        
        Focus on trends: Are they stable? Is there a risk of fatigue? 
        If data is missing, suggest keeping the watch on.
        Return ONLY the two sentences.
      `;

      const response = await ai.models.generateContent({
        model: "gemini-3-flash-preview",
        contents: prompt
      });
      
      setAiInsight(response.text || "Unable to generate insight at this time.");
    } catch (e: any) {
      console.error("AI Insight Error:", e);
      const errorMsg = e.message || "";
      if (errorMsg.includes("429") || errorMsg.includes("RESOURCE_EXHAUSTED")) {
        setAiInsight("AI insights are temporarily unavailable due to high demand. Please try again in a few moments.");
      } else if (errorMsg.includes("404") || errorMsg.includes("NOT_FOUND")) {
        setAiInsight("AI model configuration error. Using the latest available model.");
      } else {
        setAiInsight("AI synchronization failed. Please check your connection or API configuration.");
      }
    } finally {
      setIsRefreshingInsight(false);
    }
  };

  const currentReading = vitals[vitals.length - 1] || {
    hr: 0, spo2: 0, temp: 0, motion: 0, hrv: 0, steps: 0, risks: { cardiac_risk: 0, respiratory_risk: 0, stress_val: 0 }
  };

  const [activeDoctorMetric, setActiveDoctorMetric] = useState<'hr' | 'spo2' | 'hrv'>('hr');

  return (
    <div className="min-h-screen p-6 md:p-10 font-sans bg-[#0a0c10]">
      <AlertPanel alerts={alerts} onDismiss={(id) => setAlerts(prev => prev.filter(a => a.id !== id))} />

      {/* Navigation Layer */}
      <nav className="max-w-7xl mx-auto flex gap-4 mb-8 overflow-x-auto pb-2 no-scrollbar">
        {[
          { id: 'user', label: 'User Terminal', icon: User },
          { id: 'doctor', label: 'Doctor Portal', icon: Activity },
          { id: 'family', label: 'Family Status', icon: ShieldCheck },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActivePortal(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all border ${
              activePortal === tab.id 
                ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-900/20' 
                : 'bg-slate-900/50 border-white/5 text-slate-500 hover:border-white/10'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Header */}
      <header className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
        <div>
          <div className="flex items-center gap-2 text-blue-400 mb-2">
            <ShieldCheck className="w-5 h-5" />
            <span className="text-xs font-bold tracking-widest uppercase">Secured Health Grid</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tight text-white mb-2">
            GuardianWatch <span className="text-slate-500"></span>
          </h1>
          <p className="text-slate-400 max-w-md">
            AI-Enhanced Smartwatch Telemetry. Monitoring {profile?.conditions?.join(", ")} markers in real-time.
          </p>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-medium text-white">{profile?.age} Years Old</p>
            <p className="text-xs text-slate-500 flex items-center justify-end gap-1">
              <MapPin className="w-3 h-3" /> Hyderabad, India
            </p>
          </div>
          <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center border-2 border-white/10">
            <User className="text-white w-6 h-6" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto flex flex-col gap-6">
        
        {activePortal === 'user' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 flex flex-col gap-6">
              {/* Manual Entry Panel (Now featured at top for easy access) */}
              <div className="glass-card p-6 border-blue-500/30">
                <h3 className="text-sm font-bold uppercase tracking-widest text-blue-400 mb-6 flex items-center gap-2">
                  <Activity className="w-4 h-4" /> Manual Patient Data Injection
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase block mb-2">Heart Rate: {manualHr} BPM</label>
                    <input 
                      type="range" min="40" max="220" value={manualHr} 
                      onChange={(e) => setManualHr(parseInt(e.target.value))}
                      className="w-full accent-red-500"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase block mb-2">SpO2: {manualSpo2}%</label>
                    <input 
                      type="range" min="80" max="100" value={manualSpo2} 
                      onChange={(e) => setManualSpo2(parseInt(e.target.value))}
                      className="w-full accent-blue-500"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase block mb-2">HRV: {manualHrv} ms</label>
                    <input 
                      type="range" min="10" max="150" value={manualHrv} 
                      onChange={(e) => setManualHrv(parseInt(e.target.value))}
                      className="w-full accent-emerald-500"
                    />
                  </div>
                  <button 
                    onClick={postManualReading}
                    className="h-10 self-end bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold text-xs uppercase tracking-widest transition-all"
                  >
                    Inject Vitals
                  </button>
                </div>
              </div>

              {/* Profile Management Section */}
              <div className="glass-card p-6 border-indigo-500/30">
                <h3 className="text-sm font-bold uppercase tracking-widest text-indigo-400 mb-6 flex items-center gap-2">
                  <User className="w-4 h-4" /> Patient Profile Management
                </h3>
                <div className="space-y-6">
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <label className="text-[10px] text-slate-500 uppercase block mb-2">Update Age</label>
                      <input 
                        type="number" 
                        value={newAgeInput || profile?.age || ""} 
                        onChange={(e) => setNewAgeInput(parseInt(e.target.value))}
                        placeholder={profile?.age?.toString()}
                        className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-indigo-500 outline-none transition-all"
                      />
                    </div>
                    <button 
                      onClick={() => updateProfile(newAgeInput || profile?.age, profile?.conditions)}
                      className="h-10 self-end px-6 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-bold text-xs uppercase tracking-widest transition-all"
                    >
                      Update Age
                    </button>
                  </div>

                  <div>
                    <label className="text-[10px] text-slate-500 uppercase block mb-2">Medical Conditions</label>
                    <div className="flex flex-wrap gap-2 mb-4 min-h-[32px]">
                      {profile?.conditions?.map((c: string) => (
                        <span key={c} className="bg-indigo-500/10 text-indigo-400 text-[10px] font-bold px-2 py-1 rounded border border-indigo-500/20 flex items-center gap-2">
                          {c}
                          <button 
                            onClick={() => updateProfile(profile.age, profile.conditions.filter((cond: string) => cond !== c))}
                            className="hover:text-red-400 transition-colors"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <input 
                        type="text" 
                        value={newConditionInput}
                        onChange={(e) => setNewConditionInput(e.target.value)}
                        placeholder="Add medical condition (e.g. Hypertension)..."
                        className="flex-1 bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-indigo-500 outline-none transition-all"
                      />
                      <button 
                        onClick={() => {
                          if (newConditionInput.trim()) {
                            updateProfile(profile.age, [...(profile.conditions || []), newConditionInput.trim()]);
                            setNewConditionInput("");
                          }
                        }}
                        className="px-6 bg-slate-800 hover:bg-slate-700 text-white rounded-lg font-bold text-xs uppercase tracking-widest transition-all border border-white/5"
                      >
                        Add
                      </button>
                    </div>
                  </div>
                </div>
              </div>
              {/* Quick Stats Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                <div className="vital-card">
                  <div className="flex justify-between items-start mb-4">
                    <div className="p-2 bg-red-500/10 rounded-lg">
                      <Heart className="w-6 h-6 text-red-500" />
                    </div>
                    <div className="text-xs font-mono text-slate-500">PPG HR</div>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-display font-bold">{currentReading.hr}</span>
                    <span className="text-xs text-slate-500">BPM</span>
                  </div>
                  <VitalsChart data={vitals} dataKey="hr" color="#ef4444" label="Heart Rate" unit="BPM" domain={[40, 200]} />
                </div>

                <div className="vital-card">
                  <div className="flex justify-between items-start mb-4">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                      <Wind className="w-6 h-6 text-blue-500" />
                    </div>
                    <div className="text-xs font-mono text-slate-500">PPG SPO2</div>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-display font-bold">{currentReading.spo2}</span>
                    <span className="text-xs text-slate-500">%</span>
                  </div>
                  <VitalsChart data={vitals} dataKey="spo2" color="#3b82f6" label="Oxygen" unit="%" domain={[80, 100]} />
                </div>

                <div className="vital-card">
                  <div className="flex justify-between items-start mb-4">
                    <div className="p-2 bg-amber-500/10 rounded-lg">
                      <Thermometer className="w-6 h-6 text-amber-500" />
                    </div>
                    <div className="text-xs font-mono text-slate-500">TEMP</div>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-display font-bold">{currentReading.temp.toFixed(1)}</span>
                    <span className="text-xs text-slate-500">°C</span>
                  </div>
                  <VitalsChart data={vitals} dataKey="temp" color="#f59e0b" label="Temp" unit="°C" domain={[35, 40]} />
                </div>

                <div className="vital-card">
                  <div className="flex justify-between items-start mb-4">
                    <div className="p-2 bg-emerald-500/10 rounded-lg">
                      <RefreshCw className="w-6 h-6 text-emerald-500" />
                    </div>
                    <div className="text-xs font-mono text-slate-500">HRV</div>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-display font-bold">{currentReading.hrv || 0}</span>
                    <span className="text-xs text-slate-500">MS</span>
                  </div>
                  <VitalsChart data={vitals} dataKey="hrv" color="#10b981" label="HRV" unit="ms" domain={[0, 100]} />
                </div>
              </div>

              {/* Health Insights: Sleep & Stress */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass-card p-6 border-indigo-500/20">
                  <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
                    <Moon className="w-4 h-4 text-indigo-400" /> Neural Sleep Analysis
                  </h3>
                  <div className="flex items-center gap-8">
                    <div className="relative w-24 h-24 flex items-center justify-center">
                      <svg className="w-full h-full -rotate-90">
                        <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-800" />
                        <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="8" fill="transparent" strokeDasharray={251} strokeDashoffset={251 * (1 - (dailySummary?.sleep_score || 0) / 100)} className="text-indigo-500 transition-all duration-1000" />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-xl font-display font-bold">{dailySummary?.sleep_score}</span>
                        <span className="text-[8px] text-slate-500 uppercase">Qual</span>
                      </div>
                    </div>
                    <div className="flex-1 space-y-3">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400 font-mono uppercase tracking-widest">Efficiency</span>
                        <span className="text-white font-bold">{dailySummary?.sleep_duration}</span>
                      </div>
                      <div className="flex gap-1 h-3 rounded-full overflow-hidden border border-white/5 bg-slate-800/50">
                        <div className="bg-indigo-600 h-full" style={{ width: '15%' }} />
                        <div className="bg-blue-400 h-full" style={{ width: '55%' }} />
                        <div className="bg-emerald-400 h-full" style={{ width: '20%' }} />
                        <div className="bg-amber-400 h-full" style={{ width: '10%' }} />
                      </div>
                      <div className="flex justify-between text-[8px] text-slate-500 uppercase tracking-widest">
                        <span>Deep</span>
                        <span>Light</span>
                        <span>REM</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="glass-card p-6 border-amber-500/20">
                  <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
                    <Coffee className="w-4 h-4 text-amber-400" /> Stress Monitoring
                  </h3>
                  <div className="space-y-6">
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-[10px] text-slate-400 uppercase tracking-widest font-mono">Current Stress Index</span>
                        <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                          (currentReading.risks?.stress_val || 0) > 0.5 ? 'bg-amber-500/20 text-amber-400' : 'bg-emerald-500/20 text-emerald-400'
                        }`}>
                          {(currentReading.risks?.stress_val || 0) > 0.5 ? 'High Stress' : 'Balanced'}
                        </span>
                      </div>
                      <div className="h-6 w-full flex items-end gap-[2px]">
                        {vitals.slice(-20).map((v, i) => (
                          <div 
                            key={i} 
                            className={`flex-1 rounded-t-sm transition-all duration-500 ${
                              (v.risks?.stress_val || 0) > 0.5 ? 'bg-amber-500' : 'bg-slate-700'
                            }`}
                            style={{ height: `${(v.risks?.stress_val || 0) * 100 + 10}%` }}
                          />
                        ))}
                      </div>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-slate-800/30 rounded-xl">
                      <span className="text-xs text-slate-400 font-mono uppercase tracking-widest">Fatigue Label</span>
                      <span className="text-xs font-bold text-white uppercase">{dailySummary?.fatigue_level}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Coaching & Activity */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass-card p-6 border-indigo-500/20">
                  <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
                    <Brain className="w-4 h-4 text-indigo-400" /> AI Smart Coaching
                  </h3>
                  <div className="min-h-[100px]">
                    {aiInsight ? (
                      <p className="text-slate-300 italic leading-relaxed">"{aiInsight}"</p>
                    ) : (
                      <div className="flex flex-col items-center justify-center text-center py-4">
                        <Brain className="w-12 h-12 text-slate-800 mb-4" />
                        <p className="text-sm text-slate-500">Generating personalized insights...</p>
                        <button onClick={getAIInsight} className="mt-4 px-4 py-2 bg-indigo-600/20 text-indigo-400 rounded-lg text-xs font-bold font-mono">ANALYZE NOW</button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="glass-card p-6 border-emerald-500/20">
                  <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-emerald-400" /> Daily Activity Progress
                  </h3>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Step Goal</span>
                      <span className="font-mono text-emerald-400">{currentReading.steps} / 10,000</span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div className="bg-emerald-500 h-full w-[54%]" />
                    </div>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wider">Estimated 4.2km covered today</p>
                  </div>
                </div>
              </div>

              {/* Weekly Health Strategy & Improvement Roadmap */}
              <div className="glass-card p-8 border-indigo-500/30 bg-gradient-to-br from-indigo-500/5 to-transparent">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                  <div>
                    <h3 className="text-xl font-display font-bold text-white flex items-center gap-2">
                      <Zap className="w-5 h-5 text-indigo-400" /> Wellness Transformation Roadmap
                    </h3>
                    <p className="text-xs text-slate-500 font-mono uppercase tracking-widest mt-1">AI-Powered Weekly Health Forecast & Strategic Improvement</p>
                  </div>
                  <button 
                    onClick={generateHealthRoadmap}
                    disabled={isGeneratingRoadmap}
                    className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 text-white rounded-xl font-bold text-xs uppercase tracking-widest transition-all shadow-lg shadow-indigo-900/40 flex items-center gap-2"
                  >
                    {isGeneratingRoadmap ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" /> Sequencing Logic...
                      </>
                    ) : (
                      <>
                        <Brain className="w-4 h-4" /> Generate Weekly Strategy
                      </>
                    )}
                  </button>
                </div>

                <div className="min-h-[200px] relative">
                  {healthRoadmap ? (
                    <div className="markdown-body prose prose-invert prose-slate max-w-none prose-sm prose-headings:text-indigo-400 prose-strong:text-white prose-p:text-slate-300">
                      <Markdown>{healthRoadmap}</Markdown>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-16 border-2 border-dashed border-white/5 rounded-2xl">
                      <Zap className="w-12 h-12 text-slate-800 mb-4 animate-pulse" />
                      <p className="text-sm text-slate-500 font-medium">Click above to synthesize your 7-day clinical strategy</p>
                      <p className="text-[10px] text-slate-600 mt-2 font-mono uppercase">Analyzing trends from {vitals.length} data nodes</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="lg:col-span-4 flex flex-col gap-6">
              <div className="glass-card p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500">Device Status</h3>
                  <div className={`p-1 rounded-md ${isSimulating ? 'bg-emerald-500/10 text-emerald-500' : 'bg-slate-800 text-slate-500'}`}>
                    <Zap className="w-4 h-4" />
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-white/5">
                    <span className="text-xs font-medium">Wearable Synced</span>
                    <button onClick={() => setIsSimulating(!isSimulating)} className={`text-[10px] font-bold px-3 py-1 rounded ${isSimulating ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
                      {isSimulating ? 'DISCONNECT' : 'RECONNECT'}
                    </button>
                  </div>
                  <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl">
                    <p className="text-[10px] font-bold text-blue-400 uppercase mb-1">Encrypted Link Active</p>
                    <p className="text-xs text-blue-200/70">DataVault (AES-256) is securing current telemetry stream.</p>
                  </div>
                </div>
              </div>

              <div className="glass-card p-6">
                <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-4">Manual Override</h3>
                <div className="space-y-4">
                  <div className="flex flex-col gap-2">
                    <label className="text-[10px] text-slate-500 uppercase">HR Simulator: {manualHr} BPM</label>
                    <input type="range" min="40" max="200" value={manualHr} onChange={e => setManualHr(parseInt(e.target.value))} className="accent-red-500" />
                  </div>
                  <button onClick={postManualReading} className="w-full py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-bold uppercase tracking-widest">Inject Packet</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activePortal === 'doctor' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
             <div className="lg:col-span-3 flex flex-col gap-6">
               <div className="glass-card p-6 bg-slate-900/80">
                 <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6">Patient Risk Profile</h3>
                 <div className="space-y-8">
                   <RiskGauge label="Cardiac Risk" value={currentReading.risks?.cardiac_risk || 0} color="#ef4444" />
                   <RiskGauge label="Respiratory Risk" value={currentReading.risks?.respiratory_risk || 0} color="#3b82f6" />
                   <RiskGauge label="Stress Index" value={currentReading.risks?.stress_val || 0} color="#10b981" />
                 </div>
                 <div className="mt-8 pt-6 border-t border-white/5">
                   <h4 className="text-[10px] font-bold text-slate-400 uppercase mb-2">Conditions</h4>
                   <div className="flex flex-wrap gap-2">
                     {profile?.conditions?.map((c: string) => (
                       <span key={c} className="px-2 py-1 bg-slate-800 text-[10px] text-slate-300 rounded border border-white/5 uppercase">{c}</span>
                     ))}
                   </div>
                 </div>
               </div>

               <div className="glass-card p-6 border-red-500/10">
                 <h3 className="text-sm font-bold uppercase tracking-widest text-red-500 mb-6 flex items-center gap-2">
                   <AlertTriangle className="w-4 h-4" /> Clinical History
                 </h3>
                 <div className="space-y-3 max-h-[300px] overflow-y-auto no-scrollbar">
                   {anomalies.length === 0 && <p className="text-[10px] text-slate-500 italic">No permanent anomalies recorded.</p>}
                   {anomalies.slice().reverse().map((a, i) => (
                     <div key={i} className="p-3 bg-red-500/5 border border-red-500/10 rounded-lg">
                       <div className="flex justify-between items-center mb-1">
                         <span className="text-[10px] text-slate-400 font-mono italic">
                           {new Date(a.timestamp).toLocaleDateString()} {new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                         </span>
                         <span className="text-[8px] bg-red-600 text-white px-1 rounded uppercase font-bold">EVENT</span>
                       </div>
                       <p className="text-xs text-red-400 font-bold">
                         {a.fallDetected ? 'Fall Detected' : `${a.hr} BPM | ${a.spo2}% SpO2`}
                       </p>
                     </div>
                   ))}
                 </div>
               </div>
             </div>
             
             <div className="lg:col-span-9 glass-card p-6 flex flex-col h-[700px]">
               <div className="flex items-center justify-between mb-8">
                 <div>
                   <h3 className="text-lg font-bold">Comprehensive Long-Term Trends</h3>
                   <p className="text-xs text-slate-500 font-mono">STABLE_STORAGE: REACHED (~24H) | ANOMALIES: {anomalies.length}</p>
                 </div>
                 <div className="flex gap-2">
                   {[
                     { id: 'hr', label: 'HR', color: '#ef4444' },
                     { id: 'spo2', label: 'SPO2', color: '#3b82f6' },
                     { id: 'hrv', label: 'HRV', color: '#10b981' }
                   ].map(m => (
                     <button 
                       key={m.id} 
                       onClick={() => setActiveDoctorMetric(m.id as any)}
                       className={`px-3 py-1 text-[10px] rounded font-bold uppercase transition-all ${
                         activeDoctorMetric === m.id ? 'bg-white text-black' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                       }`}
                     >
                       {m.label}
                     </button>
                   ))}
                 </div>
               </div>
               <div className="flex-1 h-full min-h-0">
                  <VitalsChart 
                    data={vitals} 
                    dataKey={activeDoctorMetric} 
                    color={activeDoctorMetric === 'hr' ? '#ef4444' : activeDoctorMetric === 'spo2' ? '#3b82f6' : '#10b981'} 
                    label={`Global ${activeDoctorMetric.toUpperCase()} Trend`} 
                    unit={activeDoctorMetric === 'hr' ? 'BPM' : activeDoctorMetric === 'spo2' ? '%' : 'ms'} 
                  />
               </div>
             </div>
          </div>
        )}

        {activePortal === 'family' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 glass-card overflow-hidden h-[600px] flex flex-col relative">
               <div className="absolute top-4 left-4 z-[1000] p-4 bg-slate-900/90 border border-white/10 rounded-xl backdrop-blur-md">
                 <h3 className="text-sm font-bold">Live Tracker</h3>
                 <p className="text-[10px] text-slate-500 uppercase">Updates every movement</p>
               </div>
               <div className="flex-1">
                 {profile?.safeZone && (
                   <MapZone 
                     center={[profile.safeZone.lat, profile.safeZone.lng]} 
                     userLocation={userLocation} 
                     radius={profile.safeZone.radius}
                     onZoneChange={updateSafeZone}
                   />
                 )}
               </div>
            </div>

            <div className="lg:col-span-4 flex flex-col gap-6">
              <div className="glass-card p-6">
                <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6">Emergency Contacts</h3>
                <div className="space-y-4">
                  {profile?.emergency_contacts?.map((c: any) => (
                    <div key={c.phone} className="p-4 bg-slate-800/50 rounded-xl border border-white/5 flex justify-between items-center">
                      <div>
                        <p className="text-sm font-bold">{c.name}</p>
                        <p className="text-[10px] text-slate-500 uppercase tracking-widest">{c.relation}</p>
                      </div>
                      <a href={`tel:${c.phone}`} className="p-2 bg-emerald-500/10 text-emerald-500 rounded-lg hover:bg-emerald-500/20 transition-colors">
                        <User className="w-4 h-4" />
                      </a>
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass-card p-6 bg-red-600/5 border-red-600/20">
                <h3 className="text-sm font-bold uppercase tracking-widest text-red-500 mb-6">SOS Dispatch Protocols</h3>
                <p className="text-xs text-slate-400 leading-relaxed mb-4">In the event of an impact (fall) detected outside the geofence, we automatically dispatch GPS coordinates to 108 and all listed family members.</p>
                <button onClick={() => setAlerts([{ id: 'sos', message: 'SOS protocol initiated. Live location being shared.', type: 'emergency', timestamp: new Date() }])} className="w-full py-4 bg-red-600 text-white rounded-xl font-bold uppercase tracking-widest shadow-xl shadow-red-900/30">Force SOS Alert</button>
              </div>
            </div>
          </div>
        )}

        {/* Removed System Logic Portal */}
      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto mt-12 pb-10 flex flex-col md:flex-row justify-between items-center gap-4 text-slate-600 border-t border-white/5 pt-10">
        <p className="text-sm font-mono tracking-tighter">© 2026 GUARDIAN SYSTEMS • HIPAA COMPLIANT AES-256</p>
        <div className="flex items-center gap-6">
          <a href="#" className="hover:text-blue-400 transition-colors">Documentation</a>
          <a href="#" className="hover:text-blue-400 transition-colors">Emergency Protocol</a>
          <a href="#" className="text-slate-400 flex items-center gap-2">
            <LogOut className="w-4 h-4" /> Sign Out
          </a>
        </div>
      </footer>
    </div>
  );
}
