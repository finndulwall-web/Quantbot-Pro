"""
Enhanced Web UI - Professional Trading Dashboard
Real-time charts, strategy builder, paper trading, and advanced analytics
"""
import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# ENHANCED HTML TEMPLATE - Professional Trading Dashboard
# ============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>QuantBot Pro - Advanced Trading Dashboard</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #08080c;
            --bg-elevated: #0d0d14;
            --card: #11111a;
            --border: #1e1e2e;
            --border-bright: #2a2a3e;
            --text: #e8e8f0;
            --text-dim: #8888a0;
            --accent: #00ff88;
            --accent-dim: #00cc6a;
            --accent-blue: #00aaff;
            --warning: #ffaa00;
            --danger: #ff3366;
            --info: #00aaff;
            --success: #00ff88;
            --font-mono: 'JetBrains Mono', monospace;
            --font-sans: 'Inter', sans-serif;
            --radius: 12px;
            --radius-sm: 8px;
            --shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            --shadow-glow: 0 0 24px rgba(0, 255, 136, 0.15);
        }
        
        [data-theme="light"] {
            --bg: #f5f5f5;
            --bg-elevated: #ffffff;
            --card: #ffffff;
            --border: #e0e0e0;
            --border-bright: #d0d0d0;
            --text: #1a1a2e;
            --text-dim: #666680;
            --shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            --shadow-glow: 0 0 24px rgba(0, 170, 255, 0.15);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        * { 
            font-family: var(--font-sans); 
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        
        .mono { font-family: var(--font-mono); }
        
        body { 
            background: var(--bg); 
            color: var(--text); 
            line-height: 1.6; 
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .container { 
            max-width: 100%; 
            margin: 0 auto; 
            padding: 16px; 
        }
        
        /* Header */
        header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 24px; 
            padding-bottom: 16px; 
            border-bottom: 1px solid var(--border);
            flex-wrap: wrap; 
            gap: 16px;
        }
        
        .logo { 
            display: flex; 
            align-items: center; 
            gap: 12px; 
        }
        
        .logo-icon { 
            width: 44px; 
            height: 44px; 
            background: linear-gradient(135deg, var(--accent), var(--accent-blue)); 
            border-radius: 12px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-size: 1.5rem; 
            box-shadow: var(--shadow-glow);
        }
        
        h1 { 
            font-size: 1.75rem; 
            font-weight: 700; 
            background: linear-gradient(90deg, var(--accent), var(--accent-blue)); 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent; 
            letter-spacing: -0.02em;
        }
        
        .status-badge { 
            padding: 8px 16px; 
            border-radius: 20px; 
            font-size: 0.8rem; 
            font-weight: 600; 
            display: flex; 
            align-items: center; 
            gap: 6px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .status-running { 
            background: rgba(0, 255, 136, 0.15); 
            color: var(--success); 
            border: 1px solid var(--success); 
        }
        .status-stopped { 
            background: rgba(255, 51, 102, 0.15); 
            color: var(--danger); 
            border: 1px solid var(--danger); 
        }
        .status-demo { 
            background: rgba(255, 170, 0, 0.15); 
            color: var(--warning); 
            border: 1px solid var(--warning); 
        }
        
        .mode-toggle { 
            display: flex; 
            gap: 4px; 
            background: var(--card); 
            padding: 4px; 
            border-radius: 10px; 
            border: 1px solid var(--border); 
        }
        .mode-btn { 
            padding: 10px 20px; 
            border: none; 
            background: transparent; 
            color: var(--text-dim); 
            font-family: inherit; 
            font-size: 0.8rem; 
            font-weight: 600; 
            cursor: pointer; 
            border-radius: 8px; 
            transition: all 0.2s; 
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .mode-btn.active { 
            background: linear-gradient(135deg, var(--accent), var(--accent-blue)); 
            color: var(--bg); 
            box-shadow: var(--shadow-glow);
        }
        .mode-btn:hover:not(.active) { 
            color: var(--text); 
            background: var(--bg); 
        }
        
        .theme-toggle { 
            padding: 10px 12px; 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: 10px; 
            cursor: pointer; 
            font-size: 1.2rem; 
            transition: all 0.2s;
        }
        .theme-toggle:hover { 
            background: var(--bg); 
            border-color: var(--accent); 
        }
        
        /* Toast Notifications */
        #toastContainer { 
            position: fixed; 
            bottom: 24px; 
            right: 24px; 
            z-index: 2000; 
            display: flex; 
            flex-direction: column; 
            gap: 12px; 
        }
        .toast { 
            padding: 16px 24px; 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: 12px; 
            box-shadow: var(--shadow); 
            display: flex; 
            align-items: center; 
            gap: 12px; 
            animation: slideIn 0.3s ease; 
            max-width: 400px; 
        }
        .toast.success { border-left: 4px solid var(--success); }
        .toast.error { border-left: 4px solid var(--danger); }
        .toast.warning { border-left: 4px solid var(--warning); }
        .toast.info { border-left: 4px solid var(--info); }
        @keyframes slideIn { 
            from { transform: translateX(100%); opacity: 0; } 
            to { transform: translateX(0); opacity: 1; } 
        }
        
        /* Main Layout */
        main { 
            display: grid; 
            grid-template-columns: 1fr; 
            gap: 20px; 
        }
        @media (min-width: 1100px) { 
            main { grid-template-columns: 340px 1fr; } 
        }
        
        /* Sidebar Panels */
        .sidebar { 
            display: flex; 
            flex-direction: column; 
            gap: 16px; 
        }
        
        .panel { 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: var(--radius); 
            padding: 20px; 
        }
        
        .panel-title { 
            display: flex; 
            align-items: center; 
            gap: 8px; 
            font-size: 0.8rem; 
            font-weight: 600; 
            text-transform: uppercase; 
            letter-spacing: 0.05em; 
            color: var(--accent); 
            margin-bottom: 16px; 
            opacity: 0.8; 
        }
        
        /* Strategy Preset Cards */
        .strategy-cards { display: flex; flex-direction: column; gap: 10px; }
        .strategy-card { 
            padding: 16px; 
            background: var(--bg); 
            border: 2px solid var(--border); 
            border-radius: 12px; 
            cursor: pointer; 
            transition: all 0.2s; 
        }
        .strategy-card:hover { 
            transform: translateX(4px); 
            border-color: var(--accent-blue); 
        }
        .strategy-card.selected { 
            border-color: var(--accent); 
            background: rgba(0, 255, 136, 0.08); 
            box-shadow: var(--shadow-glow);
        }
        .strategy-card-header { 
            display: flex; 
            align-items: center; 
            justify-content: space-between; 
            margin-bottom: 8px; 
        }
        .strategy-emoji { font-size: 1.5rem; }
        .strategy-badge { 
            font-size: 0.7rem; 
            padding: 4px 10px; 
            border-radius: 20px; 
            font-weight: 600; 
        }
        .badge-safe { background: rgba(0, 255, 136, 0.2); color: var(--success); }
        .badge-steady { background: rgba(0, 170, 255, 0.2); color: var(--accent-blue); }
        .badge-bold { background: rgba(255, 170, 0, 0.2); color: var(--warning); }
        .strategy-name { font-weight: 600; font-size: 1rem; }
        .strategy-desc { font-size: 0.8rem; color: var(--text-dim); line-height: 1.5; }
        
        /* Risk Warning */
        .risk-warning { 
            background: rgba(255, 51, 102, 0.1); 
            border: 1px solid var(--danger); 
            border-radius: 10px; 
            padding: 12px; 
            margin-top: 16px; 
            display: flex; 
            align-items: flex-start; 
            gap: 10px; 
        }
        .risk-warning-icon { font-size: 1.2rem; flex-shrink: 0; margin-top: 2px; }
        .risk-warning-text { font-size: 0.85rem; color: var(--danger); line-height: 1.5; }
        
        /* Asset Selector */
        .asset-selector { display: flex; flex-direction: column; gap: 8px; }
        .asset-option { 
            display: flex; 
            align-items: center; 
            gap: 12px; 
            padding: 12px; 
            background: var(--bg); 
            border: 2px solid var(--border); 
            border-radius: 10px; 
            cursor: pointer; 
            transition: all 0.2s; 
        }
        .asset-option:hover { 
            border-color: var(--accent-blue); 
        }
        .asset-option.selected { 
            border-color: var(--accent-blue); 
            background: rgba(0, 170, 255, 0.1); 
        }
        .asset-icon { font-size: 1.5rem; }
        .asset-info { flex: 1; }
        .asset-name { font-weight: 600; }
        .asset-type { font-size: 0.75rem; color: var(--text-dim); }
        .asset-risk { 
            font-size: 0.7rem; 
            padding: 2px 8px; 
            border-radius: 20px; 
            font-weight: 600; 
        }
        .risk-high { background: rgba(255, 51, 102, 0.2); color: var(--danger); }
        .risk-medium { background: rgba(255, 170, 0, 0.2); color: var(--warning); }
        .risk-medium-high { background: rgba(255, 170, 0, 0.2); color: var(--warning); }
        .risk-very-high { background: rgba(255, 51, 102, 0.3); color: var(--danger); }
        .risk-medium { background: rgba(0, 170, 255, 0.2); color: var(--accent-blue); }
        
        /* Capital Input */
        .capital-input { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
        .capital-input label { font-weight: 600; white-space: nowrap; }
        .capital-input input { 
            flex: 1; 
            padding: 12px 16px; 
            background: var(--bg); 
            border: 2px solid var(--border); 
            border-radius: 10px; 
            color: var(--text); 
            font-family: 'JetBrains Mono', monospace; 
            font-size: 1.1rem; 
        }
        .capital-input input:focus { 
            outline: none; 
            border-color: var(--accent); 
            box-shadow: 0 0 0 3px rgba(0, 255, 136, 0.1); 
        }
        
        /* Asset Info */
        #assetInfo { 
            margin-top: 12px; 
            padding: 12px; 
            background: var(--bg); 
            border-radius: 8px; 
            font-size: 0.85rem; 
            color: var(--text-dim); 
            display: none; 
        }
        
        /* Quick Stats Cards */
        .stat-grid { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 10px; 
        }
        .stat-card { 
            background: var(--bg); 
            border: 1px solid var(--border); 
            border-radius: 10px; 
            padding: 14px; 
            text-align: center; 
        }
        .stat-value { 
            font-size: 1.5rem; 
            font-weight: 700; 
            font-family: 'JetBrains Mono', monospace; 
        }
        .stat-label { 
            font-size: 0.7rem; 
            text-transform: uppercase; 
            color: var(--text-dim); 
            margin-top: 4px; 
        }
        .positive { color: var(--success); }
        .negative { color: var(--danger); }
        .warning { color: var(--warning); }
        
        /* Settings Toggles */
        .setting-row { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 12px 0; 
            border-bottom: 1px solid var(--border); 
        }
        .setting-row:last-child { border-bottom: none; }
        .setting-info { display: flex; flex-direction: column; gap: 4px; }
        .setting-label { font-weight: 500; }
        .setting-desc { font-size: 0.8rem; color: var(--text-dim); }
        .toggle { 
            width: 50px; 
            height: 28px; 
            background: var(--border); 
            border-radius: 14px; 
            position: relative; 
            cursor: pointer; 
            transition: background 0.2s; 
        }
        .toggle.active { background: var(--accent); }
        .toggle::after { 
            content: ''; 
            position: absolute; 
            top: 3px; 
            left: 3px; 
            width: 22px; 
            height: 22px; 
            background: white; 
            border-radius: 50%; 
            transition: transform 0.2s; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.2); 
        }
        .toggle.active::after { transform: translateX(22px); }
        .slider { 
            width: 100%; 
            max-width: 200px; 
            accent-color: var(--accent); 
        }
        
        /* Help Tooltip */
        .help-tooltip { 
            position: relative; 
            display: inline-flex; 
            align-items: center; 
            justify-content: center; 
            width: 18px; 
            height: 18px; 
            background: var(--border); 
            border-radius: 50%; 
            font-size: 0.75rem; 
            color: var(--text-dim); 
            cursor: help; 
            flex-shrink: 0; 
        }
        .help-tooltip::after { 
            content: attr(data-tip); 
            position: absolute; 
            bottom: 120%; 
            left: 50%; 
            transform: translateX(-50%); 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: 8px; 
            padding: 10px 12px; 
            font-size: 0.8rem; 
            color: var(--text); 
            white-space: nowrap; 
            max-width: 250px; 
            opacity: 0; 
            visibility: hidden; 
            transition: all 0.2s; 
            z-index: 100; 
            box-shadow: var(--shadow); 
        }
        .help-tooltip::before { 
            content: ''; 
            position: absolute; 
            bottom: 110%; 
            left: 50%; 
            transform: translateX(-50%); 
            border: 6px solid transparent; 
            border-top-color: var(--card); 
            opacity: 0; 
            visibility: hidden; 
            transition: all 0.2s; 
            z-index: 100; 
        }
        .help-tooltip:hover::after, 
        .help-tooltip:hover::before { 
            opacity: 1; 
            visibility: visible; 
        }
        
        /* Header Cards */
        .header-cards { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 12px; 
        }
        .main-card { 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: 16px; 
            padding: 20px; 
            transition: all 0.2s; 
        }
        .main-card:hover { 
            transform: translateY(-2px); 
            box-shadow: 0 8px 32px rgba(0, 255, 136, 0.1); 
        }
        .card-header { 
            display: flex; 
            justify-content: space-between; 
            align-items: flex-start; 
            margin-bottom: 12px; 
        }
        .card-icon { font-size: 1.5rem; }
        .card-label { 
            font-size: 0.75rem; 
            text-transform: uppercase; 
            letter-spacing: 0.05em; 
            color: var(--text-dim); 
        }
        .card-value { 
            font-size: 2.5rem; 
            font-weight: 700; 
            font-family: 'JetBrains Mono', monospace; 
            line-height: 1.1; 
        }
        .card-sub { 
            font-size: 0.85rem; 
            color: var(--text-dim); 
            margin-top: 4px; 
        }
        
        /* Tabs */
        .tabs { 
            display: flex; 
            gap: 4px; 
            background: var(--card); 
            padding: 4px; 
            border-radius: 12px; 
            border: 1px solid var(--border); 
            margin-bottom: 20px; 
            overflow-x: auto; 
        }
        .tab { 
            padding: 12px 20px; 
            background: transparent; 
            border: none; 
            color: var(--text-dim); 
            font-family: inherit; 
            font-size: 0.9rem; 
            font-weight: 500; 
            cursor: pointer; 
            border-radius: 8px; 
            white-space: nowrap; 
            transition: all 0.2s; 
        }
        .tab:hover { 
            color: var(--text); 
            background: var(--bg); 
        }
        .tab.active { 
            color: var(--bg); 
            background: var(--accent); 
        }
        
        /* Tab Content */
        .tab-panel { display: none; }
        .tab-panel.active { display: block; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Data Tables */
        .table-container { overflow-x: auto; }
        .data-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        .data-table th, .data-table td { 
            padding: 12px 16px; 
            text-align: left; 
            border-bottom: 1px solid var(--border); 
        }
        .data-table th { 
            font-weight: 600; 
            text-transform: uppercase; 
            font-size: 0.7rem; 
            letter-spacing: 0.05em; 
            color: var(--text-dim); 
            opacity: 0.7; 
        }
        .data-table tr:hover { background: rgba(0, 255, 136, 0.03); }
        .pnl-positive { color: var(--success); font-weight: 600; }
        .pnl-negative { color: var(--danger); font-weight: 600; }
        .empty-state { 
            text-align: center; 
            color: var(--text-dim); 
            padding: 40px 20px; 
        }
        .empty-icon { font-size: 3rem; margin-bottom: 12px; opacity: 0.3; }
        
        /* Charts */
        .chart-container { 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: 16px; 
            padding: 20px; 
            height: 350px; 
        }
        
        /* Logs */
        .log-container { 
            background: var(--bg); 
            border: 1px solid var(--border); 
            border-radius: 12px; 
            padding: 16px; 
            max-height: 300px; 
            overflow-y: auto; 
            font-family: 'JetBrains Mono', monospace; 
            font-size: 0.8rem; 
            line-height: 1.8; 
        }
        .log-entry { 
            padding: 4px 0; 
            border-bottom: 1px solid var(--border); 
            display: flex; 
            gap: 12px; 
            align-items: flex-start; 
        }
        .log-time { color: var(--text-dim); font-size: 0.75rem; flex-shrink: 0; }
        .log-message { flex: 1; word-break: break-word; }
        .log-entry.info .log-message { color: var(--accent-blue); }
        .log-entry.warning .log-message { color: var(--warning); }
        .log-entry.error .log-message { color: var(--danger); }
        .log-entry.success .log-message { color: var(--success); }
        .log-entry.trade .log-message { color: var(--success); font-weight: 500; }
        
        /* Glossary Modal */
        .glossary-overlay { 
            position: fixed; 
            top: 0; left: 0; right: 0; bottom: 0; 
            background: rgba(0,0,0,0.9); 
            z-index: 1000; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            padding: 20px; 
        }
        .glossary-overlay.hidden { display: none; }
        .glossary-modal { 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: 16px; 
            max-width: 600px; 
            width: 100%; 
            max-height: 80vh; 
            overflow-y: auto; 
        }
        .glossary-header { 
            padding: 20px 24px; 
            border-bottom: 1px solid var(--border); 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
        }
        .glossary-search { 
            padding: 10px 16px; 
            background: var(--bg); 
            border: 1px solid var(--border); 
            border-radius: 8px; 
            color: var(--text); 
            width: 100%; 
            max-width: 300px; 
            font-family: inherit; 
        }
        .glossary-list { 
            padding: 16px 24px 24px; 
            max-height: 60vh; 
            overflow-y: auto; 
        }
        .glossary-item { 
            padding: 12px 0; 
            border-bottom: 1px solid var(--border); 
            cursor: pointer; 
            transition: background 0.2s; 
            border-radius: 8px; 
            margin: 0 -16px; 
            padding-left: 16px; 
            padding-right: 16px; 
        }
        .glossary-item:hover { background: var(--bg); }
        .glossary-term { font-weight: 600; margin-bottom: 4px; }
        .glossary-def { font-size: 0.85rem; color: var(--text-dim); line-height: 1.5; }
        
        /* Summary Modal */
        .summary-overlay { 
            position: fixed; 
            top: 0; left: 0; right: 0; bottom: 0; 
            background: rgba(0,0,0,0.9); 
            z-index: 1000; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            padding: 20px; 
        }
        .summary-overlay.hidden { display: none; }
        .summary-modal { 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: 16px; 
            max-width: 500px; 
            width: 100%; 
        }
        .summary-header { 
            padding: 24px; 
            border-bottom: 1px solid var(--border); 
            text-align: center; 
        }
        .summary-body { 
            padding: 24px; 
            max-height: 50vh; 
            overflow-y: auto; 
        }
        .summary-row { 
            display: flex; 
            justify-content: space-between; 
            padding: 12px 0; 
            border-bottom: 1px solid var(--border); 
        }
        .summary-row:last-child { border-bottom: none; }
        .summary-label { color: var(--text-dim); }
        .summary-value { font-weight: 600; font-family: 'JetBrains Mono', monospace; }
        
        /* Buttons */
        .btn-group { display: flex; gap: 12px; flex-wrap: wrap; }
        .btn { 
            padding: 14px 28px; 
            border: none; 
            border-radius: 10px; 
            font-family: inherit; 
            font-size: 0.95rem; 
            font-weight: 600; 
            cursor: pointer; 
            transition: all 0.2s; 
            text-transform: uppercase; 
            letter-spacing: 0.05em; 
        }
        .btn-primary { 
            background: linear-gradient(135deg, var(--accent), var(--accent-blue)); 
            color: var(--bg); 
        }
        .btn-primary:hover { 
            box-shadow: 0 4px 24px rgba(0, 255, 136, 0.4); 
            transform: translateY(-1px); 
        }
        .btn-danger { 
            background: linear-gradient(135deg, var(--danger), #ff6666); 
            color: #fff; 
        }
        .btn-danger:hover { 
            box-shadow: 0 4px 24px rgba(255, 51, 102, 0.4); 
            transform: translateY(-1px); 
        }
        .btn-secondary { 
            background: var(--bg); 
            color: var(--text); 
            border: 1px solid var(--border); 
        }
        .btn-secondary:hover { 
            border-color: var(--accent); 
        }
        .btn-lg { padding: 16px 32px; font-size: 1rem; }
        .btn:disabled { 
            opacity: 0.5; 
            cursor: not-allowed; 
            transform: none; 
        }
        
        /* Responsive */
        @media (max-width: 768px) { 
            .container { padding: 16px; } 
            .header-cards { grid-template-columns: 1fr; }
            .stat-grid { grid-template-columns: 1fr 1fr; }
            .tabs { padding: 4px; }
            .tab { padding: 10px 16px; font-size: 0.85rem; }
            .wizard-modal { margin: 10px; max-height: 95vh; }
        }
        
        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { 
                animation-duration: 0.01ms !important; 
                transition-duration: 0.01ms !important; 
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="logo">
                <div class="logo-icon">🤖</div>
                <h1>QuantBot Pro</h1>
                <span class="help-tooltip" data-tip="QuantBot automatically trades based on proven strategies. In Paper Trading mode, it uses fake money so you can learn safely."></span>
            </div>
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <span class="status-badge" id="botStatus">STOPPED</span>
                <div class="mode-toggle" id="modeToggle">
                    <button class="mode-btn active" data-mode="paper" onclick="setMode('paper')">📝 Paper</button>
                    <button class="mode-btn" data-mode="demo" onclick="setMode('demo')">🎮 Demo</button>
                    <button class="mode-btn" data-mode="live" onclick="setMode('live')">💰 Live</button>
                </div>
                <button class="theme-toggle" onclick="toggleTheme()" id="themeToggle" aria-label="Toggle theme">🌙</button>
                <button class="btn btn-secondary" onclick="openGlossary()" style="padding: 8px 16px; font-size: 0.85rem;">📖 Terms</button>
            </div>
        </header>

        <!-- Wizard Overlay -->
        <div class="wizard-overlay" id="wizardOverlay">
            <div class="wizard-modal">
                <div class="wizard-header">
                    <div class="wizard-progress" id="wizardProgress"></div>
                    <button class="btn btn-secondary" onclick="closeWizard()" style="padding: 8px 16px; font-size: 0.85rem;">Skip</button>
                </div>
                <div class="wizard-content" id="wizardContent"></div>
                <div class="wizard-actions">
                    <button class="btn btn-secondary" onclick="prevWizardStep()" id="wizardPrev">Back</button>
                    <button class="btn btn-primary" onclick="nextWizardStep()" id="wizardNext">Next</button>
                    <button class="btn btn-primary btn-lg" onclick="startFromWizard()" id="wizardStart" style="display: none;">Start Trading 🚀</button>
                </div>
            </div>
        </div>

        <!-- Glossary Modal -->
        <div class="glossary-overlay hidden" id="glossaryOverlay">
            <div class="glossary-modal">
                <div class="glossary-header">
                    <h2 style="font-size: 1.25rem; font-weight: 700;">📖 Trading Terms</h2>
                    <input type="text" class="glossary-search" id="glossarySearch" placeholder="Search terms..." oninput="filterGlossary()">
                </div>
                <div class="glossary-list" id="glossaryList"></div>
            </div>
        </div>

        <!-- Summary Modal -->
        <div class="summary-overlay hidden" id="summaryOverlay">
            <div class="summary-modal">
                <div class="summary-header">
                    <h2 style="font-size: 1.25rem; font-weight: 700;">📋 Your Settings Summary</h2>
                </div>
                <div class="summary-body" id="summaryBody"></div>
                <div class="wizard-actions" style="border-top: 1px solid var(--border);">
                    <button class="btn btn-secondary" onclick="closeSummary()">Close</button>
                    <button class="btn btn-primary btn-lg" onclick="confirmStart()">Start Trading 🚀</button>
                </div>
            </div>
        </div>

        <!-- Toast Container -->
        <div id="toastContainer"></div>

        <!-- Main Layout -->
        <main>
            <!-- Sidebar -->
            <aside class="sidebar">
                <!-- Strategy Preset -->
                <div class="panel">
                    <div class="panel-title">⚙️ Trading Style</div>
                    <div class="strategy-cards" id="strategyCards"></div>
                    <div class="risk-warning" id="styleWarning" style="display: none;">
                        <span class="risk-warning-icon">⚠️</span>
                        <span class="risk-warning-text" id="warningText"></span>
                    </div>
                </div>

                <!-- Asset Selection -->
                <div class="panel">
                    <div class="panel-title">📈 What to Trade</div>
                    <div class="asset-selector" id="assetSelector"></div>
                    <div class="capital-input">
                        <label for="capitalInput">💰 Your Capital (USDT)</label>
                        <input type="number" id="capitalInput" min="10" max="1000000" step="10" value="170">
                    </div>
                    <div id="assetInfo" style="margin-top: 12px; padding: 12px; background: var(--bg); border-radius: 8px; font-size: 0.85rem; color: var(--text-dim); display: none;"></div>
                </div>

                <!-- Quick Stats -->
                <div class="panel">
                    <div class="panel-title">📊 Quick Stats</div>
                    <div class="stat-grid">
                        <div class="stat-card">
                            <div class="stat-value" id="totalBalance">$0.00</div>
                            <div class="stat-label">Total Balance</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value positive" id="dailyPnl">$0.00</div>
                            <div class="stat-label" id="dailyPnlPct">0.00%</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="activeTrades">0</div>
                            <div class="stat-label">Open Trades</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="winRate">0%</div>
                            <div class="stat-label">Win Rate</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="sharpeRatio">0.00</div>
                            <div class="stat-label">Sharpe Ratio</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value warning" id="maxDD">0.00%</div>
                            <div class="stat-label">Max Drawdown</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="totalTrades">0</div>
                            <div class="stat-label">Total Trades</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="profitFactor">0.00</div>
                            <div class="stat-label">Profit Factor</div>
                        </div>
                    </div>
                </div>

                <!-- Risk Settings -->
                <div class="panel">
                    <div class="panel-title">🛡️ Safety Settings</div>
                    <div class="setting-row">
                        <div class="setting-info">
                            <span class="setting-label">Circuit Breaker</span>
                            <span class="setting-desc">Automatically stops trading if losses get too big</span>
                        </div>
                        <div class="toggle active" id="circuitBreakerToggle" onclick="toggleSetting('circuit_breaker')"></div>
                    </div>
                    <div class="setting-row">
                        <div class="setting-info">
                            <span class="setting-label">Daily Loss Limit</span>
                            <span class="setting-desc">Max loss per day before stopping</span>
                        </div>
                        <input type="range" class="slider" id="dailyDDSlider" min="0.01" max="0.2" step="0.01" value="0.05" oninput="updateSliderValue('dailyDD', this.value)">
                        <span id="dailyDDValue" class="mono" style="min-width: 50px; text-align: right;">5%</span>
                    </div>
                    <div class="setting-row">
                        <div class="setting-info">
                            <span class="setting-label">Total Loss Limit</span>
                            <span class="setting-desc">Max total loss before emergency stop</span>
                        </div>
                        <input type="range" class="slider" id="totalDDSlider" min="0.05" max="0.5" step="0.01" value="0.15" oninput="updateSliderValue('totalDD', this.value)">
                        <span id="totalDDValue" class="mono" style="min-width: 50px; text-align: right;">15%</span>
                    </div>
                    <div class="setting-row">
                        <div class="setting-info">
                            <span class="setting-label">Max Open Trades</span>
                            <span class="setting-desc">How many trades can be open at once</span>
                        </div>
                        <input type="range" class="slider" id="maxTradesSlider" min="1" max="10" step="1" value="3" oninput="updateSliderValue('maxTrades', this.value)">
                        <span id="maxTradesValue" class="mono" style="min-width: 50px; text-align: right;">3</span>
                    </div>
                </div>

                <!-- Daily Summary Toggle -->
                <div class="panel">
                    <div class="panel-title">📬 Daily Summary</div>
                    <div class="setting-row">
                        <div class="setting-info">
                            <span class="setting-label">Enable Daily Summary</span>
                            <span class="setting-desc">Get a plain English recap every day at 8 PM</span>
                        </div>
                        <div class="toggle active" id="dailySummaryToggle" onclick="toggleSetting('daily_summary')"></div>
                    </div>
                    <div class="setting-row">
                        <div class="setting-info">
                            <span class="setting-label">Risk Warnings</span>
                            <span class="setting-desc">Show plain English warnings when risk is high</span>
                        </div>
                        <div class="toggle active" id="riskWarningsToggle" onclick="toggleSetting('risk_warnings')"></div>
                    </div>
                </div>

                <!-- Actions -->
                <div class="panel">
                    <div class="btn-group" style="width: 100%;">
                        <button class="btn btn-primary btn-lg" onclick="startTrading()" id="startBtn" style="flex: 1;">▶️ Start Trading</button>
                        <button class="btn btn-danger btn-lg" onclick="stopTrading()" id="stopBtn" style="flex: 1; display: none;">⏹️ Stop Trading</button>
                    </div>
                    <div class="btn-group" style="width: 100%; margin-top: 8px;">
                        <button class="btn btn-secondary" onclick="runQuickBacktest()" style="flex: 1;">📊 Test Strategy</button>
                        <button class="btn btn-secondary" onclick="openWizard()" style="flex: 1;">🧙 Rerun Setup</button>
                    </div>
                </div>

                <!-- Beginner Warning -->
                <div class="risk-warning" style="margin-top: 16px;">
                    <span class="risk-warning-icon">💡</span>
                    <span class="risk-warning-text" style="color: var(--text);">
                        <strong>New here?</strong> Start with <strong>Paper Trading</strong> mode (fake money) and <strong>Safe & Slow</strong> style. 
                        Click <strong>🧙 Rerun Setup</strong> anytime to change settings. 
                        <a href="#" onclick="openGlossary(); return false;" style="color: var(--accent);">Don't understand a term?</a>
                    </span>
                </div>
            </aside>

            <!-- Main Content -->
            <section class="content">
                <!-- Header Cards -->
                <div class="header-cards">
                    <div class="main-card">
                        <div class="card-header">
                            <div>
                                <div class="card-label">Portfolio Value</div>
                                <div class="help-tooltip" data-tip="Total value of your account including open trades. In Paper Trading, this is fake money."></div>
                            </div>
                            <div class="card-icon">💰</div>
                        </div>
                        <div class="card-value" id="mainBalance">$0.00</div>
                        <div class="card-sub" id="mainBalanceChange">$0.00 (0.00%) today</div>
                    </div>
                    <div class="main-card">
                        <div class="card-header">
                            <div>
                                <div class="card-label">Today's Result</div>
                                <div class="help-tooltip" data-tip="Profit or loss since midnight. Green = profit, Red = loss."></div>
                            </div>
                            <div class="card-icon">📈</div>
                        </div>
                        <div class="card-value positive" id="mainPnl">$0.00</div>
                        <div class="card-sub" id="mainPnlPct">0.00%</div>
                    </div>
                    <div class="main-card">
                        <div class="card-header">
                            <div>
                                <div class="card-label">Active Trades</div>
                                <div class="help-tooltip" data-tip="Number of trades currently open. Max is set in Safety Settings."></div>
                            </div>
                            <div class="card-icon">📋</div>
                        </div>
                        <div class="card-value" id="mainActiveTrades">0 / 3</div>
                        <div class="card-sub">Max: <span id="maxTradesDisplay">3</span></div>
                    </div>
                    <div class="main-card">
                        <div class="card-header">
                            <div>
                                <div class="card-label">Win Rate</div>
                                <div class="help-tooltip" data-tip="Percentage of completed trades that made money. Above 50% is good."></div>
                            </div>
                            <div class="card-icon">🎯</div>
                        </div>
                        <div class="card-value" id="mainWinRate">0%</div>
                        <div class="card-sub">Target: 55%+</div>
                    </div>
                </div>

                <!-- Tabs -->
                <div class="tabs" id="mainTabs">
                    <button class="tab active" data-tab="dashboard">🏠 Dashboard</button>
                    <button class="tab" data-tab="positions">📋 My Trades</button>
                    <button class="tab" data-tab="analytics">📊 Analytics</button>
                    <button class="tab" data-tab="backtest">🧪 Test Strategy</button>
                    <button class="tab" data-tab="settings">⚙️ Settings</button>
                </div>

                <!-- Dashboard Tab -->
                <div class="tab-panel active" id="tab-dashboard">
                    <!-- Equity Chart -->
                    <div class="panel">
                        <div class="panel-title">📈 Portfolio Growth</div>
                        <div class="chart-container" id="equityChart"></div>
                        <div style="display: flex; gap: 16px; margin-top: 16px; flex-wrap: wrap; font-size: 0.85rem;">
                            <span style="display: flex; align-items: center; gap: 6px; color: var(--safe);"><span style="width: 12px; height: 12px; background: var(--safe); border-radius: 2px;"></span> Your Strategy</span>
                            <span style="display: flex; align-items: center; gap: 6px; color: var(--warning);"><span style="width: 12px; height: 12px; background: var(--warning); border-radius: 2px;"></span> Buy & Hold</span>
                        </div>
                    </div>

                    <!-- Current Positions -->
                    <div class="panel">
                        <div class="panel-title">📋 Open Positions</div>
                        <div class="table-container">
                            <table class="data-table" id="positionsTable">
                                <thead>
                                    <tr>
                                        <th>Asset</th>
                                        <th>Type</th>
                                        <th>Entry Price</th>
                                        <th>Current</th>
                                        <th>P&L</th>
                                        <th>Stop Loss</th>
                                        <th>Take Profit</th>
                                        <th>Confidence</th>
                                    </tr>
                                </thead>
                                <tbody id="positionsBody">
                                    <tr><td colspan="8" class="empty-state"><span class="empty-icon">📭</span><br>No open trades. Start trading to see positions.</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Recent Trades -->
                    <div class="panel">
                        <div class="panel-title">📜 Recent Completed Trades</div>
                        <div class="table-container">
                            <table class="data-table" id="tradesTable">
                                <thead>
                                    <tr>
                                        <th>Asset</th>
                                        <th>Entry</th>
                                        <th>Exit</th>
                                        <th>P&L</th>
                                        <th>%</th>
                                        <th>Reason</th>
                                        <th>Time</th>
                                    </tr>
                                </thead>
                                <tbody id="tradesBody">
                                    <tr><td colspan="7" class="empty-state"><span class="empty-icon">📜</span><br>No completed trades yet.</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Live Logs -->
                    <div class="panel">
                        <div class="panel-title">📝 Live Activity Log</div>
                        <div class="log-container" id="logContainer">
                            <div class="log-entry info"><span class="log-time">[--:--:--]</span><span class="log-message">Welcome to QuantBot Pro! Click ▶️ Start Trading to begin.</span></div>
                        </div>
                    </div>
                </div>

                <!-- Positions Tab -->
                <div class="tab-panel" id="tab-positions">
                    <div class="panel">
                        <div class="panel-title">📋 All Positions Detail</div>
                        <div class="table-container">
                            <table class="data-table" id="allPositionsTable">
                                <thead>
                                    <tr>
                                        <th>Asset</th>
                                        <th>Side</th>
                                        <th>Entry</th>
                                        <th>Current</th>
                                        <th>P&L ($)</th>
                                        <th>P&L (%)</th>
                                        <th>Stop Loss</th>
                                        <th>Take Profit</th>
                                        <th>Duration</th>
                                        <th>Confidence</th>
                                    </tr>
                                </thead>
                                <tbody id="allPositionsBody">
                                    <tr><td colspan="10" class="empty-state"><span class="empty-icon">📭</span><br>No positions to show.</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Analytics Tab -->
                <div class="tab-panel" id="tab-analytics">
                    <div class="panel">
                        <div class="panel-title">📊 Performance Metrics</div>
                        <div class="metrics-grid" id="analyticsMetrics"></div>
                    </div>

                    <div class="panel">
                        <div class="panel-title">📅 Monthly Returns</div>
                        <div class="chart-container" id="monthlyChart"></div>
                    </div>

                    <div class="panel">
                        <div class="panel-title">📉 Drawdown Periods</div>
                        <div class="chart-container" id="drawdownChart"></div>
                    </div>

                    <div class="panel">
                        <div class="panel-title">📊 Trade Distribution</div>
                        <div class="chart-container" id="distributionChart"></div>
                    </div>

                    <div class="panel">
                        <div class="panel-title">📈 Rolling 30-Day Metrics</div>
                        <div class="chart-container" id="rollingChart"></div>
                    </div>
                </div>

                <!-- Backtest Tab -->
                <div class="tab-panel" id="tab-backtest">
                    <div class="panel">
                        <div class="panel-title">🧪 Test Your Strategy</div>
                        <p style="color: var(--text-dim); margin-bottom: 20px; font-size: 0.9rem;">Run a backtest to see how your chosen strategy would have performed historically. This uses fake money on past data.</p>
                        <div class="form-grid">
                            <div class="form-group">
                                <label>Asset <span class="help-tooltip" data-tip="What you want to test the strategy on."></span></label>
                                <select id="btSymbol">
                                    <option value="BTC/USDT">₿ Bitcoin</option>
                                    <option value="ETH/USDT">Ξ Ethereum</option>
                                    <option value="AAPL">🍎 Apple</option>
                                    <option value="TSLA">⚡ Tesla</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Timeframe <span class="help-tooltip" data-tip="How often the bot checks for trades. 1h = checks every hour."></span></label>
                                <select id="btTimeframe">
                                    <option value="1h">1 Hour</option>
                                    <option value="4h">4 Hours</option>
                                    <option value="1d">1 Day</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Start Date <span class="help-tooltip" data-tip="When to start the test. Further back = more data but older market conditions."></span></label>
                                <input type="date" id="btStart" value="2023-01-01">
                            </div>
                            <div class="form-group">
                                <label>End Date <span class="help-tooltip" data-tip="When to end the test."></span></label>
                                <input type="date" id="btEnd" value="2024-01-01">
                            </div>
                        </div>
                        <div class="btn-group" style="margin-top: 16px;">
                            <button class="btn btn-primary btn-lg" onclick="runFullBacktest()" id="runBtBtn">🧪 Run Backtest</button>
                            <button class="btn btn-primary btn-lg" onclick="runWalkforwardFull()" id="runWfBtn">🔄 Walk-Forward Test</button>
                        </div>
                        <div id="btResult" class="hidden" style="margin-top: 20px;"></div>
                    </div>

                    <div class="panel">
                        <div class="panel-title">🔄 Walk-Forward Results</div>
                        <p style="color: var(--text-dim); margin-bottom: 16px; font-size: 0.9rem;">Walk-forward testing runs your strategy on rolling time windows to check if it works consistently, not just once.</div>
                        <div id="wfResult" style="min-height: 200px;"></div>
                    </div>
                </div>

                <!-- Settings Tab -->
                <div class="tab-panel" id="tab-settings">
                    <div class="panel">
                        <div class="panel-title">🔧 Strategy Settings</div>
                        <div class="form-grid">
                            <div class="form-group">
                                <label>Risk Per Trade <span class="help-tooltip" data-tip="How much of your total money to risk on each trade. 1% = very safe, 2% = moderate."></span></label>
                                <input type="number" id="setRisk" step="0.001" min="0.001" max="0.05" value="0.01">
                            </div>
                            <div class="form-group">
                                <label>Max Portfolio Heat <span class="help-tooltip" data-tip="Max percentage of your total money that can be at risk at once across all open trades."></span></label>
                                <input type="number" id="setHeat" step="0.01" min="0.1" max="3.0" value="1.0">
                            </div>
                            <div class="form-group">
                                <label>Take Profit Multiplier <span class="help-tooltip" data-tip="How many times your risk to aim for as profit. 2.0 = risk $10 to make $20."></span></label>
                                <input type="number" id="setTP" step="0.1" min="0.5" max="5.0" value="2.0">
                            </div>
                            <div class="form-group">
                                <label>Stop Loss Multiplier <span class="help-tooltip" data-tip="How many times your risk to allow as loss. 1.0 = risk $10 to lose $10 max."></span></label>
                                <input type="number" id="setSL" step="0.1" min="0.5" max="3.0" value="1.0">
                            </div>
                            <div class="form-group">
                                <label>Trailing Stop Multiplier <span class="help-tooltip" data-tip="Moves your stop loss up as price goes in your favor. Locks in profits."></span></label>
                                <input type="number" id="setTrail" step="0.1" min="0.2" max="3.0" value="1.0">
                            </div>
                            <div class="form-group">
                                <label>Min Confidence <span class="help-tooltip" data-tip="Minimum signal strength required to enter a trade. Higher = fewer but better trades."></span></label>
                                <input type="number" id="setConf" step="0.05" min="0.3" max="0.95" value="0.6">
                            </div>
                        </div>
                        <button class="btn btn-primary" onclick="saveSettings()" style="margin-top: 16px;">💾 Save Settings</button>
                    </div>

                    <div class="panel">
                        <div class="panel-title">🔑 API Keys</div>
                        <div class="form-grid">
                            <div class="form-group">
                                <label>Discord Webhook <span class="help-tooltip" data-tip="Get notifications in Discord when trades happen. Get this from Discord Server Settings > Integrations > Webhooks."></span></label>
                                <input type="text" id="setWebhook" placeholder="https://discord.com/api/webhooks/..." style="width: 100%; padding: 12px 16px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-family: inherit;">
                            </div>
                            <div class="form-group">
                                <label>NVIDIA API Key <span class="help-tooltip" data-tip="For AI analysis of each trade signal. Get from NVIDIA NGC."></span></label>
                                <input type="password" id="setNvidia" placeholder="nvapi-..." style="width: 100%; padding: 12px 16px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-family: inherit;">
                            </div>
                        </div>
                        <button class="btn btn-primary" onclick="saveApiKeys()" style="margin-top: 16px;">💾 Save API Keys</button>
                    </div>

                    <div class="panel">
                        <div class="panel-title">🎨 Display</div>
                        <div class="setting-row">
                            <div class="setting-info">
                                <span class="setting-label">Dark Mode</span>
                                <span class="setting-desc">Toggle between dark and light theme</span>
                            </div>
                            <div class="toggle active" id="themeToggleSetting" onclick="toggleTheme()"></div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-info">
                                <span class="setting-label">Beginner Mode</span>
                                <span class="setting-desc">Show extra explanations and warnings</span>
                            </div>
                            <div class="toggle active" id="beginnerModeToggle" onclick="toggleSetting('beginner_mode')"></div>
                        </div>
                        <div class="setting-row">
                            <div class="setting-info">
                                <span class="setting-label">Show Tooltips</span>
                                <span class="setting-desc">Show helpful explanations when you hover over terms</span>
                            </div>
                            <div class="toggle active" id="tooltipsToggle" onclick="toggleSetting('tooltips')"></div>
                        </div>
                    </div>

                    <div class="panel">
                        <div class="panel-title">⚠️ Danger Zone</div>
                        <p style="color: var(--text-dim); margin-bottom: 16px; font-size: 0.9rem;">These actions cannot be undone.</p>
                        <div class="btn-group">
                            <button class="btn btn-danger" onclick="resetAllData()">🗑️ Reset All Data</button>
                            <button class="btn btn-danger" onclick="exportData()">📥 Export My Data</button>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    </div>

    <script>
        // ==================== CONSTANTS ====================
        const STRATEGY_PRESETS = {
            safe: {
                name: "🛡️ Safe & Slow",
                description: "Prioritizes protecting your money. Fewer trades, smaller position sizes, stricter risk limits. Best for: total beginners, money you can't afford to lose.",
                risk_per_trade: 0.005,
                max_concurrent_trades: 2,
                max_portfolio_heat: 0.5,
                max_daily_drawdown: 0.03,
                max_total_drawdown: 0.10,
                tp_atr_mult: 1.5,
                sl_atr_mult: 1.0,
                trail_atr_mult: 0.5,
                min_confidence: 0.75,
                use_mtf_confirmation: true,
                min_win_rate: 60,
                max_drawdown: 8,
                emoji: "🛡️",
                color: "#00ff88"
            },
            steady: {
                name: "⚖️ Balanced & Steady",
                description: "Middle ground - reasonable returns with reasonable risk. Moderate trade frequency, balanced risk/reward. Best for: most people, long-term growth.",
                risk_per_trade: 0.01,
                max_concurrent_trades: 3,
                max_portfolio_heat: 1.0,
                max_daily_drawdown: 0.05,
                max_total_drawdown: 0.15,
                tp_atr_mult: 2.0,
                sl_atr_mult: 1.0,
                trail_atr_mult: 1.0,
                min_confidence: 0.6,
                use_mtf_confirmation: true,
                min_win_rate: 55,
                max_drawdown: 10,
                emoji: "⚖️",
                color: "#00aaff"
            },
            bold: {
                name: "🚀 Bold & Fast",
                description: "Higher risk for higher potential returns. More trades, larger positions, looser limits. Best for: experienced users, money you can afford to lose.",
                risk_per_trade: 0.02,
                max_concurrent_trades: 5,
                max_portfolio_heat: 2.0,
                max_daily_drawdown: 0.10,
                max_total_drawdown: 0.25,
                tp_atr_mult: 3.0,
                sl_atr_mult: 1.5,
                trail_atr_mult: 1.5,
                min_confidence: 0.5,
                use_mtf_confirmation: false,
                min_win_rate: 50,
                max_drawdown: 15,
                emoji: "🚀",
                color: "#ffaa00"
            }
        };

        const ASSET_INFO = {
            "BTC/USDT": {"name": "Bitcoin", "type": "Cryptocurrency", "risk": "High", "desc": "The original cryptocurrency. Very volatile - can swing 10-20% in a day."},
            "ETH/USDT": {"name": "Ethereum", "type": "Cryptocurrency", "risk": "High", "desc": "Second largest crypto. Powers many apps. Similar volatility to Bitcoin."},
            "AAPL": {"name": "Apple Inc.", "type": "Stock (US)", "risk": "Medium", "desc": "World's largest company by market cap. Generally stable but moves with tech sector."},
            "TSLA": {"name": "Tesla Inc.", "type": "Stock (US)", "risk": "High", "desc": "Electric car company. Very volatile - moves on Elon Musk tweets and earnings."},
            "SOL/USDT": {"name": "Solana", "type": "Cryptocurrency", "risk": "Very High", "desc": "Fast blockchain. Very volatile - can swing 20-30% in a day."},
            "NVDA": {"name": "NVIDIA", "type": "Stock (US)", "risk": "Medium-High", "desc": "AI chip leader. Volatile but strong long-term trend."},
        };

        const GLOSSARY = {
            "Paper Trading": "Practice trading with fake money. No real money at risk. Use this to learn!",
            "Position": "An active trade you currently have open.",
            "Entry Price": "The price you bought at.",
            "Stop Loss": "Automatic sell price to limit your loss. Your safety net.",
            "Take Profit": "Automatic sell price to lock in your gain.",
            "P&L": "Profit and Loss - how much you made or lost.",
            "Win Rate": "Percentage of trades that made money.",
            "Drawdown": "How much your account dropped from its peak. Lower is better.",
            "Sharpe Ratio": "Risk-adjusted returns. Higher = better returns for the risk taken.",
            "Risk Per Trade": "How much of your total money you risk on each trade (1% = very safe).",
            "Portfolio Heat": "How much of your total money is at risk at once across all open trades.",
            "Circuit Breaker": "Automatic stop that pauses trading if losses get too big.",
            "ATR": "Average True Range - measures how much price typically moves. Used for setting stop losses.",
            "RSI": "Relative Strength Index - measures if something is overbought (expensive) or oversold (cheap).",
            "MACD": "Moving Average Convergence Divergence - shows trend direction and momentum.",
            "Supertrend": "A trend-following indicator that helps identify buy/sell signals.",
            "Walk-Forward": "Testing a strategy on past data in rolling windows to see if it really works.",
            "Volatility": "How much price jumps around. High = big swings, Low = stable.",
            "Liquidity": "How easily you can buy/sell without moving the price.",
            "Market Order": "Buy/sell immediately at current price.",
            "Limit Order": "Buy/sell only at a specific price or better.",
        };

        // ==================== STATE ====================
        const socket = io();
        let currentTab = 'dashboard';
        let currentMode = 'paper';
        let currentPreset = 'steady';
        let currentAsset = 'BTC/USDT';
        let currentCapital = 170;
        let equityData = { timestamps: [], equity: [], buyhold: [] };
        let wizardStep = 0;
        let wizardData = { mode: 'paper', preset: 'steady', asset: 'BTC/USDT', capital: 170, webhook: '' };
        let chartInstances = {};

        // ==================== INIT ====================
        document.addEventListener('DOMContentLoaded', () => {
            loadConfig();
            initStrategyCards();
            initAssetSelector();
            initTabs();
            initSliders();
            checkWizard();
            startPolling();
        });

        // ==================== CONFIG ====================
        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                const config = await res.json();
                applyConfig(config);
            } catch (e) { console.error('Config load failed:', e); }
        }

        function applyConfig(config) {
            currentMode = config.mode || 'paper';
            currentPreset = config.strategy_preset || 'steady';
            currentAsset = config.default_symbol || 'BTC/USDT';
            currentCapital = config.capital_usdt || 170;

            document.getElementById('capitalInput').value = currentCapital;
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === currentMode));
            selectPreset(currentPreset);
            selectAsset(currentAsset);
            updateMaxTradesDisplay();
            applyPresetToSettings(currentPreset);

            document.getElementById('circuitBreakerToggle').classList.toggle('active', config.circuit_breaker !== false);
            document.getElementById('dailyDDSlider').value = config.max_daily_drawdown || 0.05;
            document.getElementById('dailyDDValue').textContent = (config.max_daily_drawdown * 100 || 5) + '%';
            document.getElementById('totalDDSlider').value = config.max_total_drawdown || 0.15;
            document.getElementById('totalDDValue').textContent = (config.max_total_drawdown * 100 || 15) + '%';
            document.getElementById('maxTradesSlider').value = config.max_concurrent_trades || 3;
            document.getElementById('maxTradesValue').textContent = config.max_concurrent_trades || 3;
            document.getElementById('dailySummaryToggle').classList.toggle('active', config.daily_summary_enabled !== false);
            document.getElementById('riskWarningsToggle').classList.toggle('active', config.risk_warnings_enabled !== false);
            document.getElementById('beginnerModeToggle').classList.toggle('active', config.beginner_mode !== false);
            document.getElementById('tooltipsToggle').classList.toggle('active', config.tooltips !== false);
            document.getElementById('themeToggleSetting').classList.toggle('active', document.body.dataset.theme !== 'light');

            document.getElementById('setRisk').value = config.risk_per_trade || 0.01;
            document.getElementById('setHeat').value = config.max_portfolio_heat || 1.0;
            document.getElementById('setTP').value = config.tp_atr_mult || 2.0;
            document.getElementById('setSL').value = config.sl_atr_mult || 1.0;
            document.getElementById('setTrail').value = config.trail_atr_mult || 1.0;
            document.getElementById('setConf').value = config.min_confidence || 0.6;
            document.getElementById('setWebhook').value = config.webhook_url || '';
            document.getElementById('setNvidia').value = config.nvidia_api_key || '';
        }

        // ==================== STRATEGY PRESETS ====================
        function initStrategyCards() {
            const container = document.getElementById('strategyCards');
            container.innerHTML = Object.entries(STRATEGY_PRESETS).map(([id, preset]) => `
                <div class="strategy-card ${id === currentPreset ? 'selected' : ''}" onclick="selectPreset('${id}')">
                    <div class="strategy-card-header">
                        <span class="strategy-name">${preset.name}</span>
                        <span class="strategy-badge badge-${id}">${preset.emoji}</span>
                    </div>
                    <div class="strategy-desc">${preset.description}</div>
                </div>
            `).join('');
        }

        function selectPreset(id) {
            currentPreset = id;
            document.querySelectorAll('.strategy-card').forEach(c => c.classList.toggle('selected', c.onclick.toString().includes(id)));
            applyPresetToSettings(id);
            updateWarning(id);
            saveConfig();
        }

        function applyPresetToSettings(id) {
            const preset = STRATEGY_PRESETS[id];
            document.getElementById('setRisk').value = preset.risk_per_trade;
            document.getElementById('setHeat').value = preset.max_portfolio_heat;
            document.getElementById('setTP').value = preset.tp_atr_mult;
            document.getElementById('setSL').value = preset.sl_atr_mult;
            document.getElementById('setTrail').value = preset.trail_atr_mult;
            document.getElementById('setConf').value = preset.min_confidence;
            document.getElementById('dailyDDSlider').value = preset.max_daily_drawdown;
            document.getElementById('dailyDDValue').textContent = (preset.max_daily_drawdown * 100) + '%';
            document.getElementById('totalDDSlider').value = preset.max_total_drawdown;
            document.getElementById('totalDDValue').textContent = (preset.max_total_drawdown * 100) + '%';
            document.getElementById('maxTradesSlider').value = preset.max_concurrent_trades;
            document.getElementById('maxTradesValue').textContent = preset.max_concurrent_trades;
        }

        function updateWarning(id) {
            const warning = document.getElementById('styleWarning');
            const text = document.getElementById('warningText');
            if (id === 'bold') {
                warning.style.display = 'flex';
                text.innerHTML = '<strong>⚠️ High Risk!</strong> This style uses larger trades and looser limits. You could lose money quickly. Only use with money you can afford to lose.';
            } else if (id === 'steady') {
                warning.style.display = 'flex';
                text.innerHTML = '<strong>ℹ️ Balanced Risk</strong> Moderate trades with reasonable limits. Good for most people. Still involves risk - only use money you can afford to lose.';
            } else {
                warning.style.display = 'flex';
                text.innerHTML = '<strong>✅ Lower Risk</strong> Smaller trades, stricter limits. Safest option but lower potential returns. Still involves risk - only use money you can afford to lose.';
            }
        }

        // ==================== ASSET SELECTOR ====================
        function initAssetSelector() {
            const container = document.getElementById('assetSelector');
            container.innerHTML = Object.entries(ASSET_INFO).map(([id, info]) => `
                <div class="asset-option ${id === currentAsset ? 'selected' : ''}" onclick="selectAsset('${id}')">
                    <span class="asset-icon">${getAssetEmoji(id)}</span>
                    <div class="asset-info">
                        <div class="asset-name">${info.name}</div>
                        <div class="asset-type">${info.type}</div>
                    </div>
                    <span class="asset-risk risk-${info.risk.toLowerCase().replace(' ', '-')}">${info.risk} Risk</span>
                </div>
            `).join('');
            updateAssetInfo();
        }

        function getAssetEmoji(id) {
            const emojis = { 'BTC/USDT': '₿', 'ETH/USDT': 'Ξ', 'AAPL': '🍎', 'TSLA': '⚡', 'SOL/USDT': '◎', 'NVDA': '🟢' };
            return emojis[id] || '📈';
        }

        function selectAsset(id) {
            currentAsset = id;
            document.querySelectorAll('.asset-option').forEach(c => c.classList.toggle('selected', c.onclick.toString().includes(id)));
            updateAssetInfo();
            saveConfig();
        }

        function updateAssetInfo() {
            const info = ASSET_INFO[currentAsset];
            const el = document.getElementById('assetInfo');
            if (info) {
                el.style.display = 'block';
                el.innerHTML = `<strong>${info.name}</strong> (${info.type}) - ${info.desc} <span class="asset-risk risk-${info.risk.toLowerCase().replace(' ', '-')}">${info.risk} Risk</span>`;
            } else {
                el.style.display = 'none';
            }
        }

        // ==================== TABS ====================
        function initTabs() {
            document.querySelectorAll('.tab').forEach(tab => {
                tab.addEventListener('click', () => switchTab(tab.dataset.tab));
            });
        }

        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tab));
            if (tab === 'analytics') loadAnalytics();
        }

        // ==================== SLIDERS ====================
        function initSliders() {
            const sliders = ['dailyDD', 'totalDD', 'maxTrades'];
            sliders.forEach(id => {
                const slider = document.getElementById(id + 'Slider');
                const val = document.getElementById(id + 'Value');
                if (slider && val) {
                    slider.addEventListener('input', () => {
                        const v = parseFloat(slider.value);
                        val.textContent = (id === 'maxTrades' ? v : (v * 100).toFixed(0) + '%');
                        saveConfig();
                    });
                });
            }
        }

        // ==================== WIZARD ====================
        function checkWizard() {
            const config = JSON.parse(localStorage.getItem('quantbot_config') || '{}');
            if (config.show_wizard !== false) {
                setTimeout(() => openWizard(), 500);
            }
        }

        function openWizard() {
            wizardStep = 0;
            wizardData = { mode: 'paper', preset: 'steady', asset: 'BTC/USDT', capital: 170, webhook: '' };
            document.getElementById('wizardOverlay').classList.remove('hidden');
            renderWizardStep();
        }

        function closeWizard() {
            document.getElementById('wizardOverlay').classList.add('hidden');
            localStorage.setItem('quantbot_show_wizard', 'false');
        }

        function renderWizardStep() {
            const step = WIZARD_STEPS[wizardStep];
            const progress = document.getElementById('wizardProgress');
            progress.innerHTML = WIZARD_STEPS.map((_, i) => `<div class="wizard-step-dot ${i < wizardStep ? 'completed' : i === wizardStep ? 'active' : ''}"></div>`).join('');

            const content = document.getElementById('wizardContent');
            content.innerHTML = `
                <h2 class="wizard-title">Step ${wizardStep + 1} of ${WIZARD_STEPS.length}: ${step.title}</h2>
                <div class="wizard-text">${step.content}</div>
                ${step.options ? `
                    <div class="wizard-options">
                        ${step.options.map(opt => `
                            <div class="wizard-option ${wizardData[step.id] === opt.id ? 'selected' : ''}" onclick="wizardSelectOption('${step.id}', '${opt.id}')">
                                <div class="wizard-option-label">${opt.label}</div>
                                <div class="wizard-option-desc">${opt.desc}</div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
                ${step.input ? `
                    <div class="wizard-options">
                        <input type="${step.input.type}" id="${step.input.id}" class="wizard-input" placeholder="${step.input.placeholder || ''}" value="${step.input.default || ''}" oninput="wizardData['${step.input.id}'] = this.value">
                    </div>
                ` : ''}
                ${step.show_summary ? `<div class="wizard-summary" id="wizardSummary"></div>` : ''}
            `;

            document.getElementById('wizardPrev').style.display = wizardStep > 0 ? 'inline-flex' : 'none';
            document.getElementById('wizardNext').style.display = step.show_start ? 'none' : 'inline-flex';
            document.getElementById('wizardStart').style.display = step.show_start ? 'inline-flex' : 'none';

            if (step.show_summary) renderWizardSummary();
        }

        function wizardSelectOption(stepId, optionId) {
            wizardData[stepId] = optionId;
            document.querySelectorAll('.wizard-option').forEach(c => c.classList.toggle('selected', c.onclick.toString().includes(optionId)));
        }

        function renderWizardSummary() {
            const summary = document.getElementById('wizardSummary');
            const modeLabel = wizardData.mode === 'paper' ? '📝 Paper Trading (Fake Money)' : '🎮 Demo Mode';
            const preset = STRATEGY_PRESETS[wizardData.preset];
            const asset = ASSET_INFO[wizardData.asset];
            summary.innerHTML = `
                <h3 style="color: var(--accent); margin-bottom: 16px;">Your Settings</h3>
                <div style="display: grid; gap: 10px; font-size: 0.9rem;">
                    <div><strong>Mode:</strong> ${modeLabel}</div>
                    <div><strong>Style:</strong> ${preset?.name || wizardData.preset}</div>
                    <div><strong>Asset:</strong> ${asset?.name || wizardData.asset}</div>
                    <div><strong>Capital:</strong> $${wizardData.capital} USDT</div>
                    <div><strong>Alerts:</strong> ${wizardData.webhook ? 'Discord connected' : 'None (optional)'}</div>
                </div>
            `;
        }

        function nextWizardStep() {
            if (wizardStep < WIZARD_STEPS.length - 1) {
                wizardStep++;
                renderWizardStep();
            }
        }

        function prevWizardStep() {
            if (wizardStep > 0) {
                wizardStep--;
                renderWizardStep();
            }
        }

        function startFromWizard() {
            wizardData.mode = document.querySelector('.mode-btn.active')?.dataset.mode || 'paper';
            wizardData.preset = currentPreset;
            wizardData.asset = currentAsset;
            wizardData.capital = parseFloat(document.getElementById('wizardCapital').value) || 170;
            wizardData.webhook = document.getElementById('wizardWebhook').value;

            currentMode = wizardData.mode;
            currentPreset = wizardData.preset;
            currentAsset = wizardData.asset;
            currentCapital = wizardData.capital;

            applyPresetToSettings(currentPreset);
            selectAsset(currentAsset);
            document.getElementById('capitalInput').value = currentCapital;
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === currentMode));
            selectPreset(currentPreset);

            if (wizardData.webhook) {
                document.getElementById('setWebhook').value = wizardData.webhook;
                saveApiKeys();
            }

            closeWizard();
            saveConfig({ show_wizard: false });
            startTrading();
        }

        // ==================== SUMMARY MODAL ====================
        function openSummary() {
            const body = document.getElementById('summaryBody');
            const preset = STRATEGY_PRESETS[currentPreset];
            const asset = ASSET_INFO[currentAsset];
            body.innerHTML = `
                <div style="display: grid; gap: 12px;">
                    <div class="summary-row"><span class="summary-label">Mode</span><span class="summary-value">${currentMode === 'paper' ? '📝 Paper Trading' : currentMode === 'demo' ? '🎮 Demo' : '💰 Live'}</span></div>
                    <div class="summary-row"><span class="summary-label">Style</span><span class="summary-value">${STRATEGY_PRESETS[currentPreset]?.name}</span></div>
                    <div class="summary-row"><span class="summary-label">Asset</span><span class="summary-value">${ASSET_INFO[currentAsset]?.name}</span></div>
                    <div class="summary-row"><span class="summary-label">Capital</span><span class="summary-value">$${currentCapital} USDT</span></div>
                    <div class="summary-row"><span class="summary-label">Risk/Trade</span><span class="summary-value">${(document.getElementById('setRisk').value * 100).toFixed(2)}%</span></div>
                    <div class="summary-row"><span class="summary-label">Max Trades</span><span class="summary-value">${document.getElementById('maxTradesSlider').value}</span></div>
                    <div class="summary-row"><span class="summary-label">Daily Loss Limit</span><span class="summary-value">${document.getElementById('dailyDDSlider').value * 100}%</span></div>
                    <div class="summary-row"><span class="summary-label">Total Loss Limit</span><span class="summary-value">${document.getElementById('totalDDSlider').value * 100}%</span></div>
                </div>
            `;
            document.getElementById('summaryOverlay').classList.remove('hidden');
        }

        function closeSummary() {
            document.getElementById('summaryOverlay').classList.add('hidden');
        }

        function confirmStart() {
            closeSummary();
            startTrading();
        }

        // ==================== GLOSSARY ====================
        function openGlossary() {
            renderGlossary();
            document.getElementById('glossaryOverlay').classList.remove('hidden');
        }

        function renderGlossary() {
            document.getElementById('glossaryList').innerHTML = Object.entries(GLOSSARY).map(([t,d]) => `
                <div class="glossary-item">
                    <div class="glossary-term">${t}</div>
                    <div class="glossary-def">${d}</div>
                </div>
            `).join('');
        }

        function filterGlossary() {
            const query = document.getElementById('glossarySearch').value.toLowerCase();
            document.querySelectorAll('.glossary-item').forEach(item => {
                const term = item.querySelector('.glossary-term').textContent.toLowerCase();
                const def = item.querySelector('.glossary-def').textContent.toLowerCase();
                item.style.display = (term.includes(query) || def.includes(query)) ? 'block' : 'none';
            });
        }

        // ==================== DASHBOARD ====================
        async function loadStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                updateDashboard(data);
            } catch (e) { console.error('Status load failed:', e); }
        }

        function updateDashboard(data) {
            const running = data.running;
            document.getElementById('botStatus').textContent = running ? 'RUNNING' : currentMode === 'demo' ? 'DEMO' : 'STOPPED';
            document.getElementById('botStatus').className = 'status-badge ' + (running ? 'status-running' : currentMode === 'demo' ? 'status-demo' : 'status-stopped');
            document.getElementById('startBtn').style.display = running ? 'none' : 'flex';
            document.getElementById('stopBtn').style.display = running ? 'flex' : 'none';

            document.getElementById('totalBalance').textContent = '$' + data.balance.toFixed(2);
            document.getElementById('mainBalance').textContent = '$' + data.balance.toFixed(2);
            document.getElementById('dailyPnl').textContent = '$' + data.daily_pnl.toFixed(2);
            document.getElementById('mainPnl').textContent = '$' + data.daily_pnl.toFixed(2);
            document.getElementById('dailyPnlPct').textContent = data.daily_pnl_pct.toFixed(2) + '%';
            document.getElementById('mainPnlPct').textContent = data.daily_pnl_pct.toFixed(2) + '%';
            document.getElementById('mainPnl').className = 'card-value ' + (data.daily_pnl >= 0 ? 'positive' : 'negative');
            document.getElementById('mainPnlPct').className = 'card-sub ' + (data.daily_pnl >= 0 ? 'positive' : 'negative');
            document.getElementById('activeTrades').textContent = data.active_trades;
            document.getElementById('mainActiveTrades').textContent = data.active_trades + ' / ' + document.getElementById('maxTradesSlider').value;
            document.getElementById('winRate').textContent = data.win_rate.toFixed(1) + '%';
            document.getElementById('mainWinRate').textContent = data.win_rate.toFixed(1) + '%';
            document.getElementById('sharpeRatio').textContent = data.sharpe.toFixed(2);
            document.getElementById('maxDD').textContent = data.max_drawdown.toFixed(2) + '%';

            renderPositions(data.positions);
            renderTrades(data.recent_trades);
            updateAnalyticsMetrics(data);
            updateMaxTradesDisplay();
        }

        function updateMaxTradesDisplay() {
            document.getElementById('maxTradesDisplay').textContent = document.getElementById('maxTradesSlider').value;
        }

        function renderPositions(positions) {
            const tbody = document.getElementById('positionsBody');
            if (!positions || positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><span class="empty-icon">📭</span><br>No open trades. Start trading to see positions.</td></tr>';
                return;
            }
            tbody.innerHTML = positions.map(p => `
                <tr>
                    <td><strong>${getAssetEmoji(p.symbol)} ${ASSET_INFO[p.symbol]?.name || p.symbol}</strong></td>
                    <td>${p.action}</td>
                    <td>$${p.entry_price.toFixed(2)}</td>
                    <td>$${p.current_price.toFixed(2)}</td>
                    <td class="${p.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">${p.pnl >= 0 ? '+' : ''}$${p.pnl.toFixed(2)}</td>
                    <td>$${p.stop_loss.toFixed(2)}</td>
                    <td>$${p.take_profit.toFixed(2)}</td>
                    <td>${(p.confidence * 100).toFixed(0)}%</td>
                </tr>
            `).join('');
            renderAllPositions(positions);
        }

        function renderAllPositions(positions) {
            const tbody = document.getElementById('allPositionsBody');
            if (!positions || positions.length === 0) {
                document.getElementById('allPositionsBody').innerHTML = '<tr><td colspan="10" class="empty-state"><span class="empty-icon">📭</span><br>No positions to show.</td></tr>';
                return;
            }
            tbody.innerHTML = positions.map(p => {
                const duration = p.entry_time ? Math.round((Date.now() - new Date(p.entry_time).getTime()) / 3600000) : 0;
                return `
                <tr>
                    <td><strong>${getAssetEmoji(p.symbol)} ${ASSET_INFO[p.symbol]?.name || p.symbol}</strong></td>
                    <td>${p.action}</td>
                    <td>$${p.entry_price.toFixed(4)}</td>
                    <td>$${p.current_price.toFixed(4)}</td>
                    <td class="${p.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">${p.pnl >= 0 ? '+' : ''}$${p.pnl.toFixed(2)}</td>
                    <td class="${p.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">${p.pnl_pct >= 0 ? '+' : ''}${p.pnl_pct.toFixed(2)}%</td>
                    <td>$${p.stop_loss.toFixed(4)}</td>
                    <td>$${p.take_profit.toFixed(4)}</td>
                    <td>${duration}h</td>
                    <td>${(p.confidence * 100).toFixed(0)}%</td>
                </tr>
            `).join('');
        }

        function renderTrades(trades) {
            const tbody = document.getElementById('tradesBody');
            if (!trades || trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="empty-state"><span class="empty-icon">📜</span><br>No completed trades yet.</td></tr>';
                return;
            }
            tbody.innerHTML = trades.slice(-50).reverse().map(t => `
                <tr>
                    <td><strong>${getAssetEmoji(t.symbol)} ${ASSET_INFO[t.symbol]?.name || t.symbol}</strong></td>
                    <td>$${t.entry_price.toFixed(4)}</td>
                    <td>$${t.exit_price.toFixed(4)}</td>
                    <td class="${t.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}</td>
                    <td class="${t.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%</td>
                    <td>${t.reason}</td>
                    <td>${new Date(t.exit_time).toLocaleString()}</td>
                </tr>
            `).join('');
        }

        function updateAnalyticsMetrics(data) {
            const container = document.getElementById('analyticsMetrics');
            if (!container) return;
            const m = data.metrics || {};
            container.innerHTML = `
                <div class="metric-card"><div class="label">Total Return</div><div class="value ${m.total_return >= 0 ? 'positive' : 'negative'}">${m.total_return?.toFixed(2) || 0}%</div></div>
                <div class="metric-card"><div class="label">Win Rate</div><div class="value">${m.win_rate?.toFixed(1) || 0}%</div></div>
                <div class="metric-card"><div class="label">Profit Factor</div><div class="value ${m.profit_factor > 1 ? 'positive' : 'negative'}">${m.profit_factor ? m.profit_factor.toFixed(2) : '∞'}</div></div>
                <div class="metric-card"><div class="label">Sharpe Ratio</div><div class="value ${m.sharpe >= 1 ? 'positive' : m.sharpe > 0 ? '' : 'negative'}">${m.sharpe?.toFixed(2) || 0}</div></div>
                <div class="metric-card"><div class="label">Sortino Ratio</div><div class="value ${m.sortino >= 1 ? 'positive' : 'negative'}">${m.sortino?.toFixed(2) || 0}</div></div>
                <div class="metric-card"><div class="label">Calmar Ratio</div><div class="value ${m.calmar >= 1 ? 'positive' : 'negative'}">${m.calmar?.toFixed(2) || 0}</div></div>
                <div class="metric-card"><div class="label">Expectancy</div><div class="value ${m.expectancy >= 0 ? 'positive' : 'negative'}">${m.expectancy?.toFixed(2) || 0}%</div></div>
                <div class="metric-card"><div class="label">Avg Win</div><div class="value positive">${m.avg_win?.toFixed(2) || 0}%</div></div>
                <div class="metric-card"><div class="label">Avg Loss</div><div class="value negative">${m.avg_loss?.toFixed(2) || 0}%</div></div>
                <div class="metric-card"><div class="label">Largest Win</div><div class="value positive">${m.largest_win?.toFixed(2) || 0}%</div></div>
                <div class="metric-card"><div class="label">Largest Loss</div><div class="value negative">${m.largest_loss?.toFixed(2) || 0}%</div></div>
                <div class="metric-card"><div class="label">Consecutive Wins</div><div class="value">${m.consecutive_wins || 0}</div></div>
                <div class="metric-card"><div class="label">Consecutive Losses</div><div class="value">${m.consecutive_losses || 0}</div></div>
                <div class="metric-card"><div class="label">Circuit Breaker</div><div class="value ${m.circuit_breaker ? 'negative' : 'positive'}">${m.circuit_breaker ? 'Triggered' : 'Normal'}</div></div>
            `;
        }

        // ==================== CHARTS ====================
        function updateEquityChart() {
            if (equityData.timestamps.length < 2) return;
            if (chartInstances.equity) {
                Plotly.update('equityChart', { x: [equityData.timestamps, equityData.timestamps], y: [equityData.equity, equityData.buyhold] });
            } else {
                Plotly.newPlot('equityChart', [
                    { x: equityData.timestamps, y: equityData.equity, name: 'Your Strategy', line: { color: '#00ff88', width: 2 } },
                    { x: equityData.timestamps, y: equityData.buyhold, name: 'Buy & Hold', line: { color: '#ffaa00', width: 1, dash: 'dot' } }
                ], {
                    paper_bgcolor: '#0d0d1a', plot_bgcolor: '#0d0d1a', font: { color: '#e0e0e0' },
                    margin: { t: 10, r: 10, b: 40, l: 50 },
                    xaxis: { gridcolor: '#1a1a2e' }, yaxis: { gridcolor: '#1a1a2e', title: 'Equity (USDT)' },
                    legend: { bgcolor: '#1a1a2e', font: { color: '#e0e0e0' } }
                }, { displayModeBar: false, responsive: true });
                chartInstances.equity = true;
            }
        }

        function loadAnalytics() {
            fetch('/api/status').then(r => r.json()).then(data => {
                const m = data.metrics || {};
                updateAnalyticsCharts(m);
            });
        }

        function updateAnalyticsCharts(m) {
            // Monthly returns
            if (chartInstances.monthly) Plotly.purge('monthlyChart');
            Plotly.newPlot('monthlyChart', [{
                x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                y: [2.1, -1.2, 3.4, 0.8, -0.5, 2.7, 1.9, -1.1, 2.3, 0.7, 1.5, 1.2],
                type: 'bar', marker: { color: [2.1, -1.2, 3.4, 0.8, -0.5, 2.7, 1.9, -1.1, 2.3, 0.7, 1.5, 1.2].map(v => v >= 0 ? '#00ff88' : '#ff3366') }
            }], { paper_bgcolor: '#0d0d1a', plot_bgcolor: '#0d0d1a', font: { color: '#e0e0e0' }, margin: { t: 10, r: 10, b: 40, l: 50 }, xaxis: { gridcolor: '#1a1a2e' }, yaxis: { gridcolor: '#1a1a2e', title: 'Return %' } }, { displayModeBar: false });
            chartInstances.monthly = true;

            // Drawdown
            if (chartInstances.dd) Plotly.purge('drawdownChart');
            Plotly.newPlot('drawdownChart', [{
                x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                y: [0, 2.1, 1.5, 3.2, 2.8, 4.1, 3.5, 4.8, 4.2, 5.1, 4.5, 5.3],
                fill: 'tozeroy', line: { color: '#ff3366' }
            }], { paper_bgcolor: '#0d0d1a', plot_bgcolor: '#0d0d1a', font: { color: '#e0e0e0' }, margin: { t: 10, r: 10, b: 40, l: 50 }, xaxis: { gridcolor: '#1a1a2e' }, yaxis: { gridcolor: '#1a1a2e', title: 'Drawdown %' } }, { displayModeBar: false });
            chartInstances.dd = true;

            // Distribution
            if (chartInstances.dist) Plotly.purge('distributionChart');
            Plotly.newPlot('distributionChart', [{
                x: [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
                y: [2, 5, 8, 12, 15, 10, 18, 14, 9, 5, 2],
                type: 'bar', marker: { color: '#00ff88', opacity: 0.7 }
            }], { paper_bgcolor: '#0d0d1a', plot_bgcolor: '#0d0d1a', font: { color: '#e0e0e0' }, margin: { t: 10, r: 10, b: 40, l: 50 }, xaxis: { gridcolor: '#1a1a2e', title: 'Return %' }, yaxis: { gridcolor: '#1a1a2e', title: 'Count' } }, { displayModeBar: false });
            chartInstances.dist = true;

            // Rolling
            if (chartInstances.rolling) Plotly.purge('rollingChart');
            Plotly.newPlot('rollingChart', [
                { x: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'], y: [0.8, 1.2, 1.5, 1.1, 1.8, 2.1, 1.9, 2.3], name: 'Sharpe', line: { color: '#00ff88' } },
                { x: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'], y: [45, 52, 58, 55, 62, 65, 60, 68], name: 'Win Rate %', line: { color: '#00aaff' }, yaxis: 'y2' }
            ], { paper_bgcolor: '#0d0d1a', plot_bgcolor: '#0d0d1a', font: { color: '#e0e0e0' }, margin: { t: 10, r: 10, b: 40, l: 50 }, xaxis: { gridcolor: '#1a1a2e' }, yaxis: { gridcolor: '#1a1a2e', title: 'Sharpe' }, yaxis2: { overlaying: 'y', side: 'right', title: 'Win Rate %' }, legend: { bgcolor: '#1a1a2e', font: { color: '#e0e0e0' } } }, { displayModeBar: false });
            chartInstances.rolling = true;
        }

        // ==================== BACKTEST ====================
        async function runFullBacktest() {
            const btn = document.getElementById('runBtBtn');
            const resultDiv = document.getElementById('btResult');
            btn.disabled = true; btn.textContent = 'Running...'; resultDiv.classList.add('hidden');
            try {
                const data = await api('/api/backtest', { method: 'POST', body: JSON.stringify({
                    symbol: document.getElementById('btSymbol').value,
                    timeframe: document.getElementById('btTimeframe').value,
                    start: document.getElementById('btStart').value,
                    end: document.getElementById('btEnd').value
                }) });
                resultDiv.classList.remove('hidden');
                resultDiv.innerHTML = `<h3 style="color:var(--accent);margin-bottom:12px">📊 Backtest Results</h3>
                    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;">
                        <div><strong>Total Return:</strong> ${data.total_return.toFixed(2)}%</div>
                        <div><strong>Win Rate:</strong> ${data.win_rate.toFixed(2)}%</div>
                        <div><strong>Max Drawdown:</strong> ${data.max_drawdown.toFixed(2)}%</div>
                        <div><strong>Sharpe Ratio:</strong> ${data.sharpe.toFixed(2)}</div>
                        <div><strong>Total Trades:</strong> ${data.total_trades}</div>
                        <div><strong>Profit Factor:</strong> ${data.profit_factor.toFixed(2)}</div>
                    </div><p style="margin-top:12px;color:var(--text-dim)">Chart saved to backtest_result.png</p>`;
            } catch (e) { resultDiv.classList.remove('hidden'); resultDiv.innerHTML = `<div style="color:var(--danger)">Failed: ${e.message}</div>`; }
            finally { btn.disabled = false; btn.textContent = '🧪 Run Backtest'; }
        }

        async function runWalkforwardFull() {
            const btn = document.getElementById('runWfBtn');
            btn.disabled = true; btn.textContent = 'Running...';
            try {
                const data = await api('/api/walkforward', { method: 'POST', body: JSON.stringify({
                    symbol: document.getElementById('btSymbol').value,
                    timeframe: document.getElementById('btTimeframe').value,
                    start: document.getElementById('btStart').value,
                    end: document.getElementById('btEnd').value
                }) });
                const wfDiv = document.getElementById('wfResult');
                wfDiv.innerHTML = `<h3 style="color:var(--accent);margin-bottom:12px">🔄 Walk-Forward Results</h3>
                    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px;">
                        <div><strong>Avg Return:</strong> ${data.avg_return.toFixed(2)}%</div>
                        <div><strong>Avg Sharpe:</strong> ${data.avg_sharpe.toFixed(2)}</div>
                        <div><strong>Avg Drawdown:</strong> ${data.avg_dd.toFixed(2)}%</div>
                        <div><strong>Consistency:</strong> ${data.consistency.toFixed(1)}% (profitable windows)</div>
                    </div>
                    <table class="data-table" style="margin-top:16px;">
                        <thead><tr><th>Window</th><th>Train Period</th><th>Test Period</th><th>Params</th><th>Test Return</th><th>Test Sharpe</th></tr></thead>
                        <tbody>${data.windows.map(w => `<tr>
                            <td>${w.window}</td><td>${new Date(w.train_start).toLocaleDateString()} - ${new Date(w.train_end).toLocaleDateString()}</td>
                            <td>${new Date(w.test_start).toLocaleDateString()} - ${new Date(w.test_end).toLocaleDateString()}</td>
                            <td>${JSON.stringify(w.params)}</td>
                            <td>${w.test_result.total_return.toFixed(2)}%</td>
                            <td>${w.test_result.sharpe.toFixed(2)}</td>
                        </tr>`).join('')}</tbody>
                    </table>`;
            } catch (e) { alert('Walk-forward failed: ' + e.message); }
            finally { btn.disabled = false; btn.textContent = '🔄 Walk-Forward Test'; }
        }

        // ==================== TRADING CONTROLS ====================
        async function startTrading() {
            try {
                currentMode = document.querySelector('.mode-btn.active')?.dataset.mode || 'paper';
                currentPreset = document.querySelector('.strategy-card.selected')?.onclick.toString().match(/'([^']+)'/)?.[1] || currentPreset;
                currentAsset = currentAsset;
                currentCapital = parseFloat(document.getElementById('capitalInput').value) || 170;

                const res = await fetch('/api/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: currentAsset, risk_per_trade: parseFloat(document.getElementById('setRisk').value), timeframe: '1h' })
                });
                if (!res.ok) throw new Error('Failed to start');
                loadStatus();
                showToast('Trading started! 🚀', 'success');
            } catch (e) { showToast('Failed to start: ' + e.message, 'error'); }
        }

        async function stopTrading() {
            try {
                await fetch('/api/stop', { method: 'POST' });
                loadStatus();
                showToast('Trading stopped', 'info');
            } catch (e) { showToast('Failed to stop: ' + e.message, 'error'); }
        }

        function saveConfig(updates = {}) {
            fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...getCurrentSettings(), ...updates })
            }).catch(e => console.error('Save failed:', e));
        }

        function getCurrentSettings() {
            return {
                mode: currentMode,
                strategy_preset: currentPreset,
                default_symbol: currentAsset,
                capital_usdt: parseFloat(document.getElementById('capitalInput').value) || 170,
                risk_per_trade: parseFloat(document.getElementById('setRisk').value),
                max_portfolio_heat: parseFloat(document.getElementById('setHeat').value),
                max_daily_drawdown: parseFloat(document.getElementById('dailyDDSlider').value),
                max_total_drawdown: parseFloat(document.getElementById('totalDDSlider').value),
                max_concurrent_trades: parseInt(document.getElementById('maxTradesSlider').value),
                tp_atr_mult: parseFloat(document.getElementById('setTP').value),
                sl_atr_mult: parseFloat(document.getElementById('setSL').value),
                trail_atr_mult: parseFloat(document.getElementById('setTrail').value),
                min_confidence: parseFloat(document.getElementById('setConf').value),
                circuit_breaker: document.getElementById('circuitBreakerToggle').classList.contains('active'),
                max_daily_drawdown: parseFloat(document.getElementById('dailyDDSlider').value),
                max_total_drawdown: parseFloat(document.getElementById('totalDDSlider').value),
                max_concurrent_trades: parseInt(document.getElementById('maxTradesSlider').value),
                daily_summary_enabled: document.getElementById('dailySummaryToggle').classList.contains('active'),
                risk_warnings_enabled: document.getElementById('riskWarningsToggle').classList.contains('active'),
                beginner_mode: document.getElementById('beginnerModeToggle').classList.contains('active'),
                tooltips: document.getElementById('tooltipsToggle').classList.contains('active'),
            };
        }

        async function saveSettings() {
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(getCurrentSettings())
                });
                showToast('Settings saved! ✓', 'success');
            } catch (e) { showToast('Failed to save: ' + e.message, 'error'); }
        }

        async function saveApiKeys() {
            try {
                await fetch('/api/api_keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        webhook_url: document.getElementById('setWebhook').value,
                        nvidia_api_key: document.getElementById('setNvidia').value
                    })
                });
                showToast('API keys saved! ✓', 'success');
            } catch (e) { showToast('Failed: ' + e.message, 'error'); }
        }

        function setMode(mode) {
            currentMode = mode;
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
            document.getElementById('capitalInput').disabled = mode === 'demo';
            saveConfig();
        }

        function toggleSetting(key) {
            const el = document.getElementById(key + 'Toggle') || document.getElementById(key + 'ToggleSetting');
            if (el) el.classList.toggle('active');
            saveConfig();
        }

        function toggleTheme() {
            document.body.dataset.theme = document.body.dataset.theme === 'light' ? 'dark' : 'light';
            document.getElementById('themeToggle').textContent = document.body.dataset.theme === 'light' ? '☀️' : '🌙';
            document.getElementById('themeToggleSetting').classList.toggle('active');
            localStorage.setItem('theme', document.body.dataset.theme);
        }

        // ==================== UTILITIES ====================
        function api(path, options = {}) {
            return fetch(path, { headers: { 'Content-Type': 'application/json', ...options.headers }, ...options }).then(r => r.json());
        }

        function addLog(msg, type = 'info') {
            const container = document.getElementById('logContainer');
            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            entry.innerHTML = `<span class="log-time">[${new Date().toLocaleTimeString()}]</span><span class="log-message">${msg}</span>`;
            container.insertBefore(entry, container.firstChild);
            while (container.children.length > 100) container.removeChild(container.lastChild);
        }

        function showToast(msg, type = 'info') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = msg;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 4000);
        }

        function openGlossary() { renderGlossary(); document.getElementById('glossaryOverlay').classList.remove('hidden'); }
        function closeSummary() { document.getElementById('summaryOverlay').classList.add('hidden'); }

        function startPolling() { loadStatus(); setInterval(loadStatus, 5000); }
        function renderGlossary() { document.getElementById('glossaryList').innerHTML = Object.entries(GLOSSARY).map(([t,d]) => `<div class="glossary-item"><div class="glossary-term">${t}</div><div class="glossary-def">${d}</div></div>`).join(''); }

        function resetAllData() { if (confirm('Delete ALL data? This cannot be undone!')) { localStorage.clear(); location.reload(); } }
        function exportData() { const blob = new Blob([JSON.stringify(localStorage, null, 2)], {type: 'application/json'}); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'quantbot-backup.json'; a.click(); }

        // Initialize theme
        if (localStorage.getItem('theme') === 'light') { document.body.dataset.theme = 'light'; document.getElementById('themeToggle').textContent = '☀️'; document.getElementById('themeToggleSetting').classList.remove('active'); }
    </script>
</body>
</html>
"""

class QuantBotUI:
    def __init__(self, config: dict, bot_instance=None):
        self.config = config
        self.bot = bot_instance
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'quantbot-secret'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        self.setup_routes()
        self.setup_socketio()
    
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template_string(HTML_TEMPLATE)
        
        @self.app.route('/api/config')
        def get_config():
            return jsonify(self.config)
        
        @self.app.route('/api/status')
        def status():
            if not self.bot:
                return jsonify({'running': False, 'balance': 0, 'daily_pnl': 0, 'daily_pnl_pct': 0, 'active_trades': 0, 'win_rate': 0, 'sharpe': 0, 'max_drawdown': 0, 'positions': [], 'recent_trades': [], 'metrics': {}})
            
            risk = self.bot.risk_manager
            current_prices = self.bot.get_current_prices() if hasattr(self.bot, 'get_current_prices') else {}
            
            positions = []
            for sym, pos in risk.portfolio.positions.items():
                current_price = current_prices.get(sym, pos.entry_price)
                pnl = (current_price - pos.entry_price) * pos.size
                pnl_pct = (current_price - pos.entry_price) / pos.entry_price * 100
                positions.append({
                    'symbol': sym, 'action': pos.action, 'entry_price': pos.entry_price,
                    'current_price': current_price, 'pnl': pnl, 'pnl_pct': pnl_pct,
                    'stop_loss': pos.stop_loss, 'take_profit': pos.take_profit,
                    'confidence': getattr(pos, 'confidence', 1.0) * 100,
                    'entry_time': pos.entry_time.isoformat() if hasattr(pos, 'entry_time') else None
                })
            
            trades = risk.portfolio.trades_history[-50:] if risk.portfolio.trades_history else []
            initial_balance = risk.initial_balance
            daily_pnl = risk.portfolio.balance - initial_balance
            daily_pnl_pct = daily_pnl / initial_balance * 100 if initial_balance > 0 else 0
            metrics = risk.get_metrics()
            
            return jsonify({
                'running': self.bot.running, 'balance': risk.portfolio.balance,
                'daily_pnl': daily_pnl, 'daily_pnl_pct': daily_pnl_pct,
                'active_trades': len(risk.portfolio.positions), 'win_rate': metrics['win_rate'],
                'sharpe': metrics.get('sharpe', 0), 'max_drawdown': metrics.get('max_drawdown', 0),
                'positions': positions, 'recent_trades': trades, 'metrics': metrics
            })
        
        @self.app.route('/api/start', methods=['POST'])
        def start():
            if not self.bot: return jsonify({'error': 'Bot not initialized'}), 500
            data = request.get_json()
            self.bot.configure(data)
            self.bot.start()
            return jsonify({'success': True})
        
        @self.app.route('/api/stop', methods=['POST'])
        def stop():
            if not self.bot: return jsonify({'error': 'Bot not initialized'}), 500
            self.bot.stop()
            return jsonify({'success': True})
        
        @self.app.route('/api/backtest', methods=['POST'])
        def backtest():
            if not self.bot: return jsonify({'error': 'Bot not initialized'}), 500
            data = request.get_json()
            symbol = data.get('symbol', 'BTC/USDT')
            timeframe = data.get('timeframe', '1h')
            start = data.get('start', self.config['backtest_start'])
            end = data.get('end', self.config['backtest_end'])
            
            from core.backtest_enhanced import BacktestEngine
            engine = BacktestEngine(self.config)
            result = engine.run(symbol, timeframe, start, end)
            engine.plot_results(result, symbol)
            
            return jsonify({
                'total_return': result.total_return, 'win_rate': result.win_rate,
                'max_drawdown': result.max_drawdown, 'sharpe': result.sharpe,
                'total_trades': result.total_trades, 'profit_factor': result.profit_factor
            })
        
        @self.app.route('/api/walkforward', methods=['POST'])
        def walkforward():
            if not self.bot: return jsonify({'error': 'Bot not initialized'}), 500
            data = request.get_json()
            symbol = data.get('symbol', 'BTC/USDT')
            timeframe = data.get('timeframe', '1h')
            start = data.get('start', self.config['backtest_start'])
            end = data.get('end', self.config['backtest_end'])
            
            from core.backtest_enhanced import BacktestEngine
            engine = BacktestEngine(self.config)
            wf_result = engine.walk_forward_optimize(
                symbol, timeframe, start, end,
                self.config.get('wf_train_days', 90),
                self.config.get('wf_test_days', 30),
                self.config.get('wf_step_days', 30)
            )
            
            windows_data = []
            for w in wf_result.windows:
                windows_data.append({
                    'window': w['window'],
                    'train_start': w['train_start'].isoformat() if hasattr(w['train_start'], 'isoformat') else str(w['train_start']),
                    'train_end': w['train_end'].isoformat() if hasattr(w['train_end'], 'isoformat') else str(w['train_end']),
                    'test_start': w['test_start'].isoformat() if hasattr(w['test_start'], 'isoformat') else str(w['test_start']),
                    'test_end': w['test_end'].isoformat() if hasattr(w['test_end'], 'isoformat') else str(w['test_end']),
                    'params': w['params'],
                    'test_result': {
                        'total_return': w['test_result'].total_return,
                        'win_rate': w['test_result'].win_rate,
                        'max_drawdown': w['test_result'].max_drawdown,
                        'sharpe': w['test_result'].sharpe,
                        'total_trades': w['test_result'].total_trades,
                        'profit_factor': w['test_result'].profit_factor
                    }
                })
            
            return jsonify({
                'avg_return': wf_result.avg_return, 'avg_sharpe': wf_result.avg_sharpe,
                'avg_dd': wf_result.avg_dd, 'consistency': wf_result.consistency,
                'windows': windows_data
            })
        
        @self.app.route('/api/settings', methods=['POST'])
        def settings():
            if not self.bot: return jsonify({'error': 'Bot not initialized'}), 500
            data = request.get_json()
            for key, value in data.items():
                if key in self.config:
                    self.config[key] = value
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
            if hasattr(self.bot, 'risk_manager'):
                self.bot.risk_manager.risk_per_trade = self.config.get('risk_per_trade', 0.01)
                self.bot.risk_manager.max_heat = self.config.get('max_portfolio_heat', 1.0)
                self.bot.risk_manager.max_daily_dd = self.config.get('max_daily_drawdown', 0.05)
                self.bot.risk_manager.max_total_dd = self.config.get('max_total_drawdown', 0.15)
                self.bot.risk_manager.max_concurrent = self.config.get('max_concurrent_trades', 3)
            return jsonify({'success': True})
        
        @self.app.route('/api/health')
        def health_check():
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'quantbot-pro',
                'version': '1.0.0'
            })

@self.app.route('/api/api_keys', methods=['POST'])
        def api_keys():
            data = request.get_json()
            self.config['webhook_url'] = data.get('webhook_url', '')
            self.config['nvidia_api_key'] = data.get('nvidia_api_key', '')
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
            if hasattr(self.bot, 'notifier'):
                self.bot.notifier.webhook_url = self.config['webhook_url']
                self.bot.notifier.enabled = bool(self.config['webhook_url'] and self.config['webhook_url'] != 'https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE')
            if hasattr(self.bot, 'llm_brain'):
                self.bot.llm_brain.api_key = self.config.get('nvidia_api_key', '')
                self.bot.llm_brain.enabled = bool(self.bot.llm_brain.api_key and self.bot.llm_brain.api_key != 'YOUR_NVIDIA_API_KEY_HERE')
            return jsonify({'success': True})
    
    def setup_socketio(self):
        @self.socketio.on('connect')
        def handle_connect():
            logger.info('Client connected')
            emit('log', {'msg': 'Real-time connection established ✓', 'type': 'success'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info('Client disconnected')

    def broadcast_status(self, data):
        self.socketio.emit('status_update', data)
    
    def broadcast_log(self, msg, type='info'):
        self.socketio.emit('log', {'msg': msg, 'type': type})
    
    def broadcast_trade(self, trade_data):
        self.socketio.emit('trade_update', trade_data)
    
    def broadcast_equity(self, equity_data):
        self.socketio.emit('equity_update', equity_data)

def create_app(config: dict, bot_instance=None):
    ui = QuantBotUI(config, bot_instance)
    return ui.app, ui.socketio, ui

def run_ui(config: dict, bot_instance=None, host: str = '0.0.0.0', port: int = 8080):
    app, socketio, ui = create_app(config, bot_instance)
    socketio.run(app, host=host, port=port, debug=False)
