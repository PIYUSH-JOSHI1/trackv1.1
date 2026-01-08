# 🚀 Track-V Complete Deployment Guide

## Complete Supabase Integration & Deployment Instructions

---

## 📋 **OVERVIEW**

This guide covers:
1. ✅ Supabase Setup (Database + Auth + Storage)
2. ✅ Backend Deployment on Render
3. ✅ Frontend Deployment on GitHub Pages
4. ✅ Email Alert Configuration
5. ✅ Connecting Everything Together

---

## 🗄️ **STEP 1: SUPABASE SETUP**

### 1.1 Create Supabase Account & Project

1. Go to [https://supabase.com](https://supabase.com)
2. Click **"Start your project"** → Sign in with GitHub
3. Click **"New Project"**
4. Fill in:
   - **Name**: `track-v-traffic`
   - **Database Password**: Create strong password (SAVE IT!)
   - **Region**: Choose closest to your users
5. Click **"Create new project"** (wait 2 mins)

### 1.2 Get Your API Keys

After project creation:
1. Go to **Settings** (gear icon) → **API**
2. Copy these values (you'll need them later):

```
Project URL: https://xxxxx.supabase.co
anon/public key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx
service_role key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx
```

⚠️ **IMPORTANT**: Never expose `service_role` key in frontend!

### 1.3 Create Database Schema

1. In Supabase Dashboard, go to **SQL Editor**
2. Click **"New Query"**
3. Copy ALL contents from `supabase_schema.sql` (in your project folder)
4. Click **"Run"** (green play button)
5. You should see "Success. No rows returned"

### 1.4 Set Up Storage for Avatars

1. Go to **Storage** in left sidebar
2. Click **"New Bucket"**
3. Create bucket:
   - **Name**: `avatars`
   - **Public bucket**: ✅ Enable
4. Click **"Create bucket"**
5. Click on `avatars` bucket → **Policies** tab
6. Click **"New Policy"** → **For full customization**
7. Add these policies:

**Policy 1 - Allow uploads:**
```sql
Name: Allow authenticated uploads
Target roles: authenticated
Policy: (auth.uid() = owner)
Operations: INSERT
```

**Policy 2 - Allow public read:**
```sql
Name: Public read access
Target roles: public
Policy: true
Operations: SELECT
```

### 1.5 Enable Email Authentication

1. Go to **Authentication** → **Providers**
2. Ensure **Email** is enabled
3. Go to **Authentication** → **Email Templates**
4. Customize templates (optional)

---

## 📧 **STEP 2: GMAIL APP PASSWORD (for Email Alerts)**

### 2.1 Enable 2-Factor Authentication
1. Go to [https://myaccount.google.com](https://myaccount.google.com)
2. Click **Security** → **2-Step Verification**
3. Follow steps to enable

### 2.2 Create App Password
1. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select app: **Mail**
3. Select device: **Other** → Type "Track-V"
4. Click **Generate**
5. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)
6. Save this - you'll need it for Render

---

## ☁️ **STEP 3: DEPLOY BACKEND ON RENDER**

### 3.1 Push Backend to GitHub

1. Create new GitHub repository: `track-v-backend`
2. In your project folder, run:

```bash
cd "c:\Users\Piyush\Downloads\Track-v-backend-main (2)\Track-v-backend-main"

# Initialize git (if not already)
git init

# Create .gitignore
echo "__pycache__/" > .gitignore
echo "*.pyc" >> .gitignore
echo ".env" >> .gitignore
echo "uploaded_videos/" >> .gitignore
echo "*.mp4" >> .gitignore

# Add files
git add .
git commit -m "Initial commit - Track-V Backend"

# Add your GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/track-v-backend.git
git branch -M main
git push -u origin main
```

### 3.2 Files to Upload to GitHub (Backend)

Upload these files to your `track-v-backend` repository:

```
track-v-backend/
├── app.py                          ✅ Main Flask application
├── intelligent_traffic_optimizer.py ✅ Traffic signal optimizer
├── sort.py                         ✅ SORT tracking algorithm
├── supabase_config.py              ✅ Supabase database manager
├── supabase_routes.py              ✅ API endpoints
├── email_service.py                ✅ Email alert service
├── supabase_schema.sql             ✅ Database schema (for reference)
├── requirements.txt                ✅ Python dependencies
├── yolov8n.pt                      ✅ YOLO model (or download on startup)
├── .gitignore                      ✅ Git ignore file
└── .env.example                    ✅ Environment template
```

**DO NOT upload:**
- `.env` (contains secrets)
- `uploaded_videos/` folder
- `__pycache__/` folder
- `track-v-frontend-main/` folder (separate repo)

### 3.3 Create Render Account

1. Go to [https://render.com](https://render.com)
2. Click **"Get Started for Free"**
3. Sign up with GitHub

### 3.4 Create Render Web Service

1. In Render Dashboard, click **"New +"** → **"Web Service"**
2. Connect your GitHub repository `track-v-backend`
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `track-v-backend` |
| **Region** | Choose closest to users |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120` |
| **Instance Type** | `Starter` or higher |

### 3.5 Add Environment Variables in Render

1. In your Render service, go to **"Environment"** tab
2. Add these variables:

| Key | Value |
|-----|-------|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` |
| `SUPABASE_ANON_KEY` | `eyJhbGciOiJIUzI1NiIs...` |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJhbGciOiJIUzI1NiIs...` |
| `SMTP_SERVER` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_EMAIL` | `your-email@gmail.com` |
| `SMTP_PASSWORD` | `your-16-char-app-password` |
| `SMTP_SENDER_NAME` | `Track-V Traffic System` |
| `PYTHON_VERSION` | `3.10.0` |

3. Click **"Save Changes"**

### 3.6 Deploy

1. Click **"Manual Deploy"** → **"Deploy latest commit"**
2. Wait for build to complete (5-10 mins first time)
3. Your backend URL will be: `https://track-v-backend.onrender.com`

---

## 🌐 **STEP 4: DEPLOY FRONTEND ON GITHUB PAGES**

### 4.1 Update Frontend Configuration

Before uploading, update `supabase-client.js`:

```javascript
// Line 8-9: Replace with your actual values
const SUPABASE_URL = 'https://xxxxx.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIs...';

// Line 12: Replace with your Render URL
const BACKEND_URL = 'https://track-v-backend.onrender.com';
```

### 4.2 Update HTML Files to Include Supabase

Add these scripts to ALL HTML files (before `</head>`):

```html
<!-- In login.html, register.html, index.html, afterlogin/index.html -->
<head>
    <!-- ... existing content ... -->
    
    <!-- Add Supabase JS SDK -->
    <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
    <script src="supabase-client.js"></script>
</head>
```

For `afterlogin/index.html`, the path should be:
```html
<script src="../supabase-client.js"></script>
```

### 4.3 Push Frontend to GitHub

1. Create new GitHub repository: `track-v-frontend`
2. Upload ONLY the frontend files:

```bash
cd "track-v-frontend-main"

git init
git add .
git commit -m "Initial commit - Track-V Frontend"
git remote add origin https://github.com/YOUR_USERNAME/track-v-frontend.git
git branch -M main
git push -u origin main
```

### 4.4 Files to Upload (Frontend)

```
track-v-frontend/
├── index.html              ✅ Landing page
├── login.html              ✅ Login page
├── register.html           ✅ Registration page
├── style.css               ✅ Main styles
├── main.js                 ✅ Main JavaScript
├── supabase-client.js      ✅ Supabase client (updated!)
├── afterlogin/
│   ├── index.html          ✅ Dashboard
│   ├── script.js           ✅ Dashboard JS
│   ├── sideNav.js          ✅ Navigation
│   └── styles.css          ✅ Dashboard styles
└── video/                  ✅ Sample videos (optional)
```

### 4.5 Enable GitHub Pages

1. Go to your `track-v-frontend` repository
2. Click **Settings** → **Pages**
3. Under "Source", select:
   - **Branch**: `main`
   - **Folder**: `/ (root)`
4. Click **Save**
5. Your site will be live at: `https://YOUR_USERNAME.github.io/track-v-frontend/`

---

## 🔗 **STEP 5: CONNECT EVERYTHING**

### 5.1 Update CORS in Backend

Your backend already has CORS configured for all origins. If you want to restrict it:

In `app.py`, update:
```python
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://YOUR_USERNAME.github.io",
            "http://localhost:*"
        ]
    }
})
```

### 5.2 Test the Connection

1. Open your frontend URL: `https://YOUR_USERNAME.github.io/track-v-frontend/`
2. Open browser console (F12)
3. Check for any CORS or connection errors
4. Try registering a new account
5. Try logging in

### 5.3 Verify Backend Health

Visit: `https://track-v-backend.onrender.com/health`

You should see:
```json
{
    "status": "healthy",
    "feeds_active": 0,
    "optimizer_ready": true
}
```

---

## 📱 **FEATURE IMPLEMENTATION GUIDE**

### Video Sources (CCTV, YouTube, File Upload)

Users can set video sources through the dashboard:

```javascript
// Set YouTube video
await TrackV.updateCameraSource(junctionId, 0, 'youtube', 'https://youtube.com/watch?v=xxxxx');

// Set RTSP stream (live CCTV)
await TrackV.updateCameraSource(junctionId, 1, 'rtsp', 'rtsp://192.168.1.100:554/stream');

// Set uploaded video file
await TrackV.updateCameraSource(junctionId, 2, 'video_file', '/path/to/video.mp4');
```

### Send Alert Button

Add to your dashboard JavaScript:

```javascript
async function sendAlert(junctionId, cameraIndex) {
    const result = await TrackV.createAlert(junctionId, {
        type: 'manual',
        severity: 'high',
        title: 'Traffic Congestion Alert',
        description: 'Heavy traffic detected at camera ' + (cameraIndex + 1),
        camera_index: cameraIndex
    });
    
    if (result.success) {
        alert('Alert sent to inspector!');
    }
}
```

### Profile Settings

```javascript
// Update profile
await TrackV.updateProfile({
    full_name: 'John Doe',
    badge_number: 'TF-12345',
    phone: '+91 9876543210'
});

// Upload avatar
const fileInput = document.getElementById('avatarInput');
await TrackV.uploadAvatar(fileInput.files[0]);

// Toggle dark mode
await TrackV.toggleDarkMode(true);

// Toggle email alerts
await TrackV.toggleEmailAlerts(false);
```

### Map View with Junctions

```javascript
// Get all junction data for map
const mapData = await TrackV.getMapData();

// mapData contains:
// [{
//     id: 'uuid',
//     name: 'Junction A',
//     latitude: 19.0178,
//     longitude: 72.8478,
//     cameras: [...],
//     latest_traffic: { vehicle_count: 15, congestion_level: 'medium' }
// }, ...]

// Use with Leaflet or Google Maps
mapData.forEach(junction => {
    L.marker([junction.latitude, junction.longitude])
        .bindPopup(`<b>${junction.name}</b><br>Vehicles: ${junction.latest_traffic?.vehicle_count || 0}`)
        .addTo(map);
});
```

### Download Reports

```javascript
// Download traffic report
await TrackV.downloadReport(junctionId, 'daily', 30);
```

---

## 🔧 **TROUBLESHOOTING**

### Backend Not Starting on Render

1. Check Render logs for errors
2. Ensure all environment variables are set
3. Make sure `requirements.txt` is correct
4. Try reducing workers: `gunicorn app:app --workers 1`

### CORS Errors

1. Check backend CORS configuration
2. Ensure frontend URL matches allowed origins
3. Clear browser cache

### Email Not Sending

1. Verify Gmail app password is correct
2. Check Render logs for SMTP errors
3. Ensure email alerts are enabled in user settings

### Supabase Connection Issues

1. Verify API keys are correct
2. Check Row Level Security policies
3. Ensure user is authenticated for protected operations

---

## 📊 **ARCHITECTURE SUMMARY**

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (GitHub Pages)                  │
│  https://your-username.github.io/track-v-frontend/          │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Login   │  │Dashboard │  │   Map    │  │ Settings │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │           │
└───────┼─────────────┼─────────────┼─────────────┼───────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    SUPABASE (Database + Auth)                │
│  https://xxxxx.supabase.co                                   │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │   Auth   │  │Profiles  │  │Junctions │  │  Alerts  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Cameras  │  │Traffic   │  │ Reports  │  │ Storage  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
┌───────┴──────────────────────────────────────────┴───────┐
│                   BACKEND (Render)                        │
│  https://track-v-backend.onrender.com                    │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Flask App   │  │  YOLOv8 AI   │  │Email Service │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │SORT Tracker  │  │Signal Optim  │  │Video Process │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## ✅ **DEPLOYMENT CHECKLIST**

- [ ] Supabase project created
- [ ] Database schema executed
- [ ] Storage bucket created with policies
- [ ] Gmail app password generated
- [ ] Backend pushed to GitHub
- [ ] Render service created
- [ ] Environment variables set in Render
- [ ] Backend deployed and healthy
- [ ] Frontend `supabase-client.js` updated with keys
- [ ] Frontend pushed to GitHub
- [ ] GitHub Pages enabled
- [ ] Test registration/login
- [ ] Test video feeds
- [ ] Test alert sending
- [ ] Test profile updates

---

## 🎉 **YOU'RE DONE!**

Your Track-V Traffic Management System is now fully deployed with:
- ✅ User authentication (register/login)
- ✅ Profile management with avatar upload
- ✅ Real-time traffic monitoring
- ✅ Email alerts to inspectors
- ✅ Dark/Light mode settings
- ✅ Traffic data storage & reports
- ✅ Map view with junction locations
- ✅ Multiple video source support

**Frontend URL**: `https://YOUR_USERNAME.github.io/track-v-frontend/`
**Backend URL**: `https://track-v-backend.onrender.com`
**API Docs**: `https://track-v-backend.onrender.com/api/v1/...`

---

*Need help? Create an issue on GitHub!*
