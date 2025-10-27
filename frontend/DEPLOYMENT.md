# Production Deployment Configuration

## Frontend API Configuration

This app uses environment-based API routing to support both local development and production deployment.

### How It Works

- **Development (Local)**: API calls default to `http://127.0.0.1:5000` when no environment variable is set
- **Production (Vercel)**: API calls use the Fly.io backend URL set via `REACT_APP_API_BASE_URL`

### Setting Up Frontend Environment Variable in Vercel

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add a new environment variable:
   - **Name**: `REACT_APP_API_BASE_URL`
   - **Value**: `https://your-fly-backend.fly.dev` (replace with your actual Fly.io backend URL)
   - **Environments**: Select "Production" (and optionally "Preview" if you want staging environments to use the production backend)
4. Save the variable
5. Redeploy your application for the changes to take effect

## Backend Redirect URL Configuration

The backend uses email redirects for authentication flows (signup, password reset, etc.). These need to point to your production frontend.

### Setting Up Backend Environment Variable in Fly.io

1. In your Fly.io backend, set the `FRONTEND_URL` environment variable:
   ```bash
   fly secrets set FRONTEND_URL=https://www.pailinabroad.com
   ```

2. This configures:
   - Email verification redirects (signup → `/onboarding`)
   - Stripe checkout success/cancel URLs
   - Stripe customer portal return URL

### Backend Files Using FRONTEND_URL

- `backend/app/routes.py`:
  - Email signup redirect → `/onboarding`
  - Magic link (OTP) redirect → `/pathway`
  - Password reset redirect → `/reset-password`
- `backend/app/stripe_routes.py`:
  - Stripe checkout success URL → `/payment-success`
  - Stripe checkout cancel URL → `/checkout`
  - Stripe customer portal return URL → `/account-settings`
- `backend/app/config.py` - Configuration file (defaults to `http://localhost:3000` for development)

### Local Development

No configuration needed! The app will automatically use `http://127.0.0.1:5000` when running locally.

### Optional: Environment Files

You can also create environment files if you prefer:

- `.env.local` - Local development (git-ignored)
  ```
  # Leave empty or omit REACT_APP_API_BASE_URL to use localhost
  ```

- `.env.production` - Production build
  ```
  REACT_APP_API_BASE_URL=https://your-fly-backend.fly.dev
  ```

Note: Vercel environment variables will override `.env.production` if both are set.

### Updated Files

The following files now use the centralized API configuration:

**Core Infrastructure:**
- `frontend/src/config/api.js` - Centralized API base URL configuration

**Components:**
- `frontend/src/Components/SubscriptionBilling.jsx` - 5 API endpoints (billing operations)
- `frontend/src/Components/SignUpModal.jsx` - 1 API endpoint (signup)
- `frontend/src/Components/ExerciseTypes/evaluateAnswer.js` - 1 API endpoint (answer evaluation)

**Pages:**
- `frontend/src/Pages/TopicLibrary.jsx` - 1 API endpoint (topic list)
- `frontend/src/Pages/TopicDetail.jsx` - 1 API endpoint (topic details)
- `frontend/src/Pages/Onboarding.jsx` - 2 API endpoints (password setup, profile update)
- `frontend/src/Pages/VerifyEmail.jsx` - 1 API endpoint (email confirmation)
- `frontend/src/Pages/ExerciseBank.jsx` - 2 API endpoints (sections, featured)
- `frontend/src/Pages/ExerciseSection.jsx` - 1 API endpoint (section details)
- `frontend/src/Pages/MyPathway.jsx` - 6 API endpoints (profile, lessons, stats, comments)
- `frontend/src/Pages/AccountSettings.jsx` - 1 API endpoint (account deletion)
- `frontend/src/Pages/LessonsIndex.jsx` - 2 API endpoints (completed lessons, level status)

**Libraries:**
- `frontend/src/lib/fetchResolvedLesson.js` - 1 API endpoint (lesson resolution)

**Total**: 25 API endpoints across 14 files
