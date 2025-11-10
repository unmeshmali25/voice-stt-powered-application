# Authentication Setup Guide

This guide explains how to set up Supabase authentication for the VoiceOffers frontend.

## Prerequisites

1. A Supabase project (create one at https://supabase.com)
2. Your Supabase project URL and anon key

## Step 1: Environment Variables

1. Create a `.env` file in the `frontend/` directory
2. Add the following variables:

```env
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

You can find these values in your Supabase project dashboard:
- Go to Project Settings → API
- Copy the "Project URL" for `VITE_SUPABASE_URL`
- Copy the "anon public" key for `VITE_SUPABASE_ANON_KEY`

## Step 2: Configure Google OAuth (Optional)

To enable Google sign-in:

### Step 2a: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. Configure the OAuth consent screen if prompted:
   - Choose **External** (unless you have a Google Workspace)
   - Fill in the required fields (App name, User support email, Developer contact)
   - Add your email to test users if needed
6. Create OAuth client ID:
   - Application type: **Web application**
   - Name: VoiceOffers (or your preferred name)
   - Authorized redirect URIs: Add your Supabase callback URL:
     ```
     https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback
     ```
     (Replace `YOUR_PROJECT_REF` with your actual Supabase project reference)
7. Copy the **Client ID** and **Client Secret**

### Step 2b: Enable Google Provider in Supabase

1. Go to your Supabase project dashboard
2. Navigate to **Authentication** → **Providers**
3. Find **Google** in the list and click to expand
4. Toggle **Enable Google provider** to ON
5. Enter your **Google Client ID** and **Client Secret** from Step 2a
6. Click **Save**

### Step 2c: Verify Redirect URL

The redirect URL in your Google OAuth credentials should match:
```
https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback
```

You can find your project reference in Supabase Dashboard → Settings → API → Project URL (it's the part after `https://` and before `.supabase.co`)

### Troubleshooting Google OAuth

**Error: "provider is not enabled"**
- Make sure you've enabled the Google provider in Supabase Dashboard → Authentication → Providers
- Verify the toggle is ON and you've saved the credentials

**Error: "redirect_uri_mismatch"**
- Check that the redirect URI in Google Cloud Console exactly matches: `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`
- Make sure there are no trailing slashes or typos

**Error: "invalid_client"**
- Verify your Client ID and Client Secret are correct in Supabase
- Make sure you copied them from the correct Google Cloud project

## Step 3: Backend Configuration

Ensure your backend has the following environment variables set:

```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_role_key  # Different from anon key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret
```

You can find the JWT secret in:
- Supabase Dashboard → Project Settings → API → JWT Settings → JWT Secret

## Step 4: Test Authentication

1. Start the frontend development server:
   ```bash
   cd frontend
   npm run dev
   ```

2. You should see the signup/login page when you visit the app
3. Try creating an account or signing in
4. Once authenticated, you should see the main application

## Troubleshooting

### "Missing Supabase environment variables" error
- Make sure your `.env` file exists in the `frontend/` directory
- Verify the variable names start with `VITE_`
- Restart the development server after creating/updating `.env`

### Google OAuth not working
- Verify Google provider is enabled in Supabase dashboard
- Check that redirect URLs are correctly configured
- Ensure your Google OAuth credentials are valid

### 401 Unauthorized errors
- Check that your backend has the correct `SUPABASE_JWT_SECRET`
- Verify the token is being sent in the Authorization header
- Check browser console for detailed error messages

