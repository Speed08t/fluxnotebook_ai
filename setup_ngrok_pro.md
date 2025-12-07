# ngrok Pro Plan Setup for 24/7 Hosting with Permanent URL

## Overview
This guide shows how to upgrade from ngrok free plan to Pro plan for 24/7 hosting with permanent URLs.

## Plan Comparison & Recommendations

### Personal Plan ($8/month) - RECOMMENDED
- ✅ 1 custom domain or reserved ngrok subdomain (permanent URL)
- ✅ No session time limits (24/7 hosting)
- ✅ 5 GB data transfer per month
- ✅ 20,000 HTTP requests per month
- ✅ 20,000 requests/minute rate limit
- ✅ 1 reserved TCP address

### Pro Plan ($20/month)
- All Personal features
- Multiple custom domains
- Advanced traffic policies
- Load balancing

## Step-by-Step Setup

### 1. Upgrade to Personal Plan
1. Go to https://ngrok.com/pricing
2. Click "Get started" under Personal plan ($8/month)
3. Complete payment setup

### 2. Reserve a Permanent Domain
```bash
# Login to ngrok
ngrok config add-authtoken YOUR_AUTH_TOKEN

# Reserve a subdomain (e.g., myapp-flux.ngrok.io)
ngrok api reserved-domains create --domain=myapp-flux.ngrok.io
```

### 3. Create Production Startup Script
Create `start_ngrok_pro.sh`:

```bash
#!/bin/bash

echo "🌍 Starting Collaborative Whiteboard with ngrok Pro (24/7)"
echo ""

# Check if ngrok is authenticated
if ! ngrok config check; then
    echo "❌ ERROR: ngrok not authenticated!"
    echo "Run: ngrok config add-authtoken YOUR_AUTH_TOKEN"
    exit 1
fi

echo "🚀 Starting Flask + WebSocket server..."
python3 ngrok_app.py &
SERVER_PID=$!

echo "⏳ Waiting for server to start..."
sleep 3

echo ""
echo "🌍 Starting ngrok tunnel with reserved domain..."
echo "🔗 Your permanent URL: https://myapp-flux.ngrok.io"
echo "✅ 24/7 hosting enabled - no session limits!"
echo ""

# Start ngrok with reserved domain
ngrok http --domain=myapp-flux.ngrok.io 5002

# Cleanup on exit
kill $SERVER_PID 2>/dev/null
```

### 4. Alternative: Custom Domain Setup
If you own a domain (e.g., app.yourdomain.com):

1. Add domain in ngrok dashboard
2. Create CNAME record: `app.yourdomain.com` → `xyz.ngrok-cname.com`
3. Start tunnel: `ngrok http --domain=app.yourdomain.com 5002`

## Bandwidth Calculations for Personal Plan ($8/month)

### Monthly Allowances:
- **Data Transfer**: 5 GB/month
- **HTTP Requests**: 20,000/month
- **Rate Limit**: 20,000 requests/minute

### Usage Estimation for Your App:

#### Typical Request Sizes:
- **Frontend HTML/CSS/JS**: ~500 KB initial load
- **WebSocket messages**: ~1-5 KB per message
- **AI API calls**: ~10-50 KB per request
- **File uploads**: Variable (1-10 MB)

#### Daily Usage Scenarios:

**Light Testing (10 users/day, 30 min sessions)**:
- Frontend loads: 10 × 500 KB = 5 MB
- WebSocket traffic: 10 × 30 min × 2 KB/min = 600 KB
- AI requests: 10 × 5 × 25 KB = 1.25 MB
- **Daily total**: ~7 MB
- **Monthly total**: ~210 MB (4% of 5 GB limit)

**Medium Testing (50 users/day, 45 min sessions)**:
- Frontend loads: 50 × 500 KB = 25 MB
- WebSocket traffic: 50 × 45 min × 2 KB/min = 4.5 MB
- AI requests: 50 × 8 × 25 KB = 10 MB
- **Daily total**: ~40 MB
- **Monthly total**: ~1.2 GB (24% of 5 GB limit)

**Heavy Testing (100 users/day, 60 min sessions)**:
- Frontend loads: 100 × 500 KB = 50 MB
- WebSocket traffic: 100 × 60 min × 3 KB/min = 18 MB
- AI requests: 100 × 10 × 30 KB = 30 MB
- **Daily total**: ~98 MB
- **Monthly total**: ~2.9 GB (58% of 5 GB limit)

### Request Count Analysis:
- **Light**: ~300 requests/day = 9,000/month (45% of limit)
- **Medium**: ~1,500 requests/day = 45,000/month (225% of limit) ⚠️
- **Heavy**: ~3,000 requests/day = 90,000/month (450% of limit) ⚠️

## Recommendations:

### For Light-Medium Testing:
- **Personal Plan ($8/month)** is sufficient
- Monitor usage in ngrok dashboard
- 5 GB bandwidth should handle most testing scenarios

### For Heavy Testing:
- Consider **Pro Plan ($20/month)** for higher limits
- Or implement usage optimization:
  - Cache static assets
  - Compress WebSocket messages
  - Limit AI request frequency

### Cost-Effective Alternatives:
1. **Hybrid approach**: Use Personal plan + optimize usage
2. **Time-based testing**: Concentrate testing in specific periods
3. **Local network testing**: Use `--local-network` flag for internal testing

## Implementation Priority:
1. Start with Personal Plan ($8/month)
2. Monitor usage for 1-2 weeks
3. Upgrade to Pro if needed
4. Implement optimizations if approaching limits

## Next Steps:
1. Upgrade to Personal plan
2. Reserve your permanent domain
3. Update startup scripts
4. Test 24/7 hosting
5. Monitor bandwidth usage
