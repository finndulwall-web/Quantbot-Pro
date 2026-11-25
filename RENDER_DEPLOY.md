# QuantBot Pro - Render.com Deployment Guide

## 🚀 Quick Deploy to Render (Free Tier)

### Prerequisites
- [Render.com account](https://render.com) (Free tier available)
- [GitHub account](https://github.com) with this repo forked
- [Discord Webhook](https://discord.com/developers/docs/resources/webhook) for notifications (optional)
- [NVIDIA API Key](https://ngc.nvidia.com/) for AI analysis (optional)

---

## 🚀 One-Click Deploy

### Option 1: Render Blueprint (Recommended)
1. Fork this repository to your GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml` and deploy

### Option 2: Manual Web Service
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo
4. Configure:
   - **Name**: `quantbot-pro`
   - **Environment**: Python 3
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements-render.txt`
   - **Start Command**: `python main.py --mode paper --symbol BTC/USDT`
   - **Plan**: Free
   - **Health Check Path**: `/api/health`

---

## ⚙️ Environment Variables

Set these in Render Dashboard → Environment Variables:

| Variable | Value | Required |
|----------|-------|----------|
| `MODE` | `paper` | ✅ |
| `SYMBOL` | `BTC/USDT` | ✅ |
| `CAPITAL_USDT` | `170.0` | ✅ |
| `RISK_PER_TRADE` | `0.01` | ✅ |
| `MAX_CONCURRENT_TRADES` | `3` | ✅ |
| `MAX_PORTFOLIO_HEAT` | `1.0` | ✅ |
| `MAX_DAILY_DRAWDOWN` | `0.05` | ✅ |
| `MAX_TOTAL_DRAWDOWN` | `0.15` | ✅ |
| `STRATEGY_PRESET` | `steady` | ✅ |
| `WEBHOOK_URL` | `your-discord-webhook-url` | Optional |
| `NVIDIA_API_KEY` | `your-nvidia-api-key` | Optional |
| `PORT` | `10000` | Auto-set by Render |
| `RENDER` | `true` | Auto-set |
| `PORT` | `10000` | Auto-set by Render |

---

## 🔄 Keep Alive with UptimeRobot

### Setup UptimeRobot (Free)
1. Create [UptimeRobot account](https://uptimerobot.com)
2. Add **New Monitor**:
   - **Monitor Type**: HTTPS
   - **URL**: `https://your-app-name.onrender.com/api/health`
   - **Monitoring Interval**: 5 minutes (free tier)
   - **Alert Contacts**: Your email/Discord
2. This prevents Render from spinning down your free tier service

---

## 🔧 Configuration Files Created

| File | Purpose |
|------|---------|
| `render.yaml` | Render Blueprint for auto-deploy |
| `Dockerfile` | Docker image for container deploy |
| `requirements-render.txt` | Render-optimized dependencies |
| `start_render.py` | Render-optimized startup script |
| `.env.example` | Environment variables template |
| `.github/workflows/render-deploy.yml` | CI/CD pipeline |

---

## 🚀 Deploy Steps

### 1. Push to GitHub
```bash
git add .
git commit -m "Add Render deployment config"
git push origin main
```

### 2. Deploy to Render
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Blueprint"
3. Connect your GitHub repo
4. Render auto-detects `render.yaml`
4. Click "Apply"

### 3. Add Environment Variables
In Render Dashboard → Your Service → Environment:
- Add all variables from `.env.example`
- Set `WEBHOOK_URL` and `NVIDIA_API_KEY` if using

### 4. Setup UptimeRobot
1. Go to [UptimeRobot](https://uptimerobot.com)
2. Add Monitor: `https://your-app.onrender.com/api/health`
3. Set interval: 5 minutes
4. Add alert contacts

---

## 📊 Monitor & Debug

### View Logs
```bash
# Render Dashboard → Your Service → Logs
# Or via CLI:
render logs -s quantbot-pro --tail
```

### Check Health
```bash
curl https://your-app.onrender.com/api/health
# Returns: {"status":"healthy","timestamp":"...","service":"quantbot-pro"}
```

### View Logs
```bash
# Render Dashboard → Your Service → Logs
# Or view bot.log in Render shell
```

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Build fails | Check `requirements-render.txt` compatibility |
| Port binding error | Render uses `PORT` env var (default 10000) |
| Health check fails | Ensure `/api/health` returns 200 |
| Out of memory | Reduce `lookback_candles` in config |
| Build timeout | Reduce dependencies in `requirements-render.txt` |

---

## 📊 Free Tier Limits (Render)

| Resource | Limit |
|----------|-------|
| RAM | 512 MB |
| CPU | Shared |
| Build Time | 15 min/month |
| Bandwidth | 100 GB/month |
| Spin Down | After 15 min inactivity |

**Use UptimeRobot to prevent spin-down!**

---

## 🎯 Next Steps

1. **Test locally**: `docker build -t quantbot . && docker run -p 10000:10000 quantbot`
2. **Deploy to Render**: Push to GitHub → Render auto-deploys
3. **Monitor**: Check Render logs and UptimeRobot
5. **Scale Up**: Upgrade to Starter plan ($7/mo) for no spin-down

---

## 📞 Support

- **Render Docs**: https://render.com/docs
- **UptimeRobot**: https://uptimerobot.com
- **QuantBot Issues**: GitHub Issues

---

*Built with ❤️ for automated trading*
