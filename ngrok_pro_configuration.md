# ngrok Pro Plan Configuration Guide

## Quick Setup Checklist

### 1. Upgrade to ngrok Personal Plan ($8/month)
- [ ] Go to https://ngrok.com/pricing
- [ ] Click "Get started" under Personal plan
- [ ] Complete payment setup
- [ ] Note your auth token from dashboard

### 2. Authenticate ngrok
```bash
# Replace YOUR_AUTH_TOKEN with actual token from dashboard
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 3. Reserve a Permanent Domain
Choose one of these options:

#### Option A: Reserved ngrok Subdomain (Recommended)
```bash
# Reserve a subdomain like: myapp-flux.ngrok.io
ngrok api reserved-domains create --domain=myapp-flux.ngrok.io
```

#### Option B: Use Your Own Custom Domain
1. Add domain in ngrok dashboard: https://dashboard.ngrok.com/cloud-edge/domains
2. Create CNAME record with your DNS provider:
   - Type: CNAME
   - Name: app (or subdomain you want)
   - Value: (provided by ngrok dashboard)

### 4. Update Configuration Files
Edit the domain settings in your startup scripts:

**For Linux/Mac (start_ngrok_pro.sh):**
```bash
RESERVED_DOMAIN="myapp-flux.ngrok.io"  # Your reserved domain
CUSTOM_DOMAIN=""  # Or your custom domain like "app.yourdomain.com"
```

**For Windows (start_ngrok_pro.bat):**
```batch
set RESERVED_DOMAIN=myapp-flux.ngrok.io
set CUSTOM_DOMAIN=
```

### 5. Start 24/7 Hosting
```bash
# Linux/Mac
chmod +x start_ngrok_pro.sh
./start_ngrok_pro.sh

# Windows
start_ngrok_pro.bat
```

## Bandwidth Usage Calculator

### Personal Plan Limits ($8/month):
- **Data Transfer**: 5 GB/month
- **HTTP Requests**: 20,000/month
- **Rate Limit**: 20,000 requests/minute

### Your App's Usage Patterns:

#### Per User Session:
- **Initial Load**: ~500 KB (HTML, CSS, JS)
- **WebSocket Traffic**: ~2-3 KB/minute
- **AI Requests**: ~25 KB per request
- **File Uploads**: Variable (1-10 MB)

#### Monthly Usage Scenarios:

**Light Testing (300 user sessions/month)**:
- Frontend loads: 300 × 500 KB = 150 MB
- WebSocket: 300 × 30 min × 2 KB = 18 MB
- AI requests: 300 × 5 × 25 KB = 37.5 MB
- **Total**: ~205 MB (4% of 5 GB limit) ✅

**Medium Testing (1,500 user sessions/month)**:
- Frontend loads: 1,500 × 500 KB = 750 MB
- WebSocket: 1,500 × 45 min × 2 KB = 135 MB
- AI requests: 1,500 × 8 × 25 KB = 300 MB
- **Total**: ~1.2 GB (24% of 5 GB limit) ✅

**Heavy Testing (3,000 user sessions/month)**:
- Frontend loads: 3,000 × 500 KB = 1.5 GB
- WebSocket: 3,000 × 60 min × 3 KB = 540 MB
- AI requests: 3,000 × 10 × 30 KB = 900 MB
- **Total**: ~2.9 GB (58% of 5 GB limit) ✅

### Request Count Analysis:
- **Light**: ~9,000 requests/month (45% of limit) ✅
- **Medium**: ~45,000 requests/month (225% of limit) ⚠️
- **Heavy**: ~90,000 requests/month (450% of limit) ❌

## Optimization Strategies

### If Approaching Limits:

1. **Enable Compression**:
   ```python
   # Add to ngrok_app.py
   from flask_compress import Compress
   Compress(app)
   ```

2. **Cache Static Assets**:
   ```python
   @app.after_request
   def after_request(response):
       response.headers['Cache-Control'] = 'public, max-age=3600'
       return response
   ```

3. **Optimize WebSocket Messages**:
   - Send only changed data
   - Compress JSON messages
   - Batch multiple updates

4. **Rate Limit AI Requests**:
   ```python
   from flask_limiter import Limiter
   limiter = Limiter(app, key_func=lambda: request.remote_addr)
   
   @app.route('/api/chat', methods=['POST'])
   @limiter.limit("10 per minute")
   def chat_with_ai():
       # existing code
   ```

## Monitoring Usage

### ngrok Dashboard:
- Visit: https://dashboard.ngrok.com
- Monitor: Data transfer, request count, active tunnels
- Set up: Usage alerts

### Add Usage Logging:
```python
# Add to ngrok_app.py
import logging
from datetime import datetime

# Log requests
@app.before_request
def log_request():
    logging.info(f"Request: {request.method} {request.path} - {datetime.now()}")
```

## Troubleshooting

### Common Issues:

1. **"Domain not found" error**:
   - Ensure domain is reserved in dashboard
   - Check spelling in startup script

2. **"Authentication failed"**:
   - Verify auth token: `ngrok config check`
   - Re-authenticate if needed

3. **"Tunnel limit exceeded"**:
   - Close other ngrok processes
   - Check dashboard for active tunnels

4. **High bandwidth usage**:
   - Enable compression
   - Optimize file uploads
   - Cache static content

## Cost Analysis

### Monthly Costs:
- **Personal Plan**: $8/month
- **Pro Plan**: $20/month (if you need more features)

### Break-even Analysis:
- Personal plan supports ~1,500 moderate user sessions/month
- If you need more, consider Pro plan or usage optimization
- Alternative: Use free plan for development, Pro for production

## Next Steps:
1. ✅ Upgrade to Personal plan
2. ✅ Reserve permanent domain
3. ✅ Update startup scripts
4. ✅ Test 24/7 hosting
5. ✅ Monitor usage for optimization
