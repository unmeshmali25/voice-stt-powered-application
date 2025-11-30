# MultiModal AI Retail App - Frontend

Modern React + TypeScript frontend for the MultiModal AI Retail App, built with Vite and shadcn/ui components.

## Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui (New York style)
- **Icons**: Lucide React

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   ├── VoiceSidebar.tsx # Collapsible sidebar with mic controls
│   │   ├── CouponCard.tsx   # Card component for displaying coupons
│   │   └── MainLayout.tsx   # Main 2-column layout
│   ├── hooks/
│   │   ├── use-mobile.tsx   # Mobile detection hook
│   │   └── useVoiceRecording.ts  # Voice recording logic
│   ├── types/
│   │   └── coupon.ts        # TypeScript type definitions
│   ├── lib/
│   │   └── utils.ts         # Utility functions (cn helper)
│   ├── App.tsx              # Root component
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles + Tailwind
├── index.html               # HTML entry point
├── vite.config.ts           # Vite configuration
├── tailwind.config.js       # Tailwind configuration
├── tsconfig.json            # TypeScript configuration
└── package.json             # Dependencies
```

## Features

### 1. Collapsible Sidebar (Left Side)
- Houses the microphone button for voice recording
- Shows recording status and transcript
- Keyboard shortcut: `Cmd/Ctrl + B` to toggle
- Space bar to start/stop recording
- Mobile-responsive with sheet overlay

### 2. Two-Column Layout (Main Screen)
- **Left Column**: Front-store offers (discounts on entire basket)
- **Right Column**: Category & Brand coupons (filtered by voice search)
- No visible separator between columns
- Responsive grid layout

### 3. Coupon Cards
Each card displays:
- Discount details (e.g., "2% off purchase")
- Category/Brand name
- Expiration date
- Terms & conditions (optional)
- Color-coded badge by type (Front-store/Category/Brand)

### 4. Voice Recording
- Web Audio API integration
- Auto-stops after 7 seconds
- Manual stop available
- Uploads to `/api/stt` endpoint
- Displays transcript and latency

## Development

### Install Dependencies
```bash
npm install
```

### Run Development Server
```bash
npm run dev
```
The dev server runs on `http://localhost:5173` with proxy to backend at `http://localhost:8000`

### Build for Production
```bash
npm run build
```
Output directory: `dist/`

### Preview Production Build
```bash
npm run preview
```

## API Integration

The frontend expects the following API endpoints:

### STT Endpoint
```
POST /api/stt
Content-Type: multipart/form-data
Body: { file: <audio blob> }

Response:
{
  "transcript": string,
  "api_duration_ms": number
}
```

## Backend Integration (TODO)

Currently uses mock data for coupons. The PostgreSQL integration will be implemented in a separate branch:

1. **Front-store offers** endpoint: `GET /api/offers/frontstore`
2. **Category/Brand search** endpoint: `POST /api/offers/search` with transcript

Expected response format:
```json
{
  "frontstore": [
    {
      "id": "string",
      "type": "frontstore",
      "discountDetails": "string",
      "expirationDate": "ISO 8601 date",
      "terms": "string (optional)"
    }
  ],
  "categoryBrand": [
    {
      "id": "string",
      "type": "category" | "brand",
      "discountDetails": "string",
      "categoryOrBrand": "string",
      "expirationDate": "ISO 8601 date",
      "terms": "string (optional)"
    }
  ]
}
```

## Configuration

### Vite Proxy
The Vite dev server proxies `/api/*` requests to `http://localhost:8000` (configured in `vite.config.ts`)

### Tailwind Theme
Uses shadcn/ui color system with CSS variables. Color palette can be customized in `src/index.css`

### TypeScript
Strict mode enabled with path aliases configured (`@/` → `./src/`)

## Components

### shadcn/ui Components Used
- `Button` - Interactive buttons
- `Card` - Card container with header, content, footer
- `Sidebar` - Collapsible sidebar with provider
- `Sheet` - Mobile overlay for sidebar
- `Separator` - Horizontal/vertical separator
- `Tooltip` - Tooltips for UI elements
- `Skeleton` - Loading placeholders
- `Input` - Form inputs

## Keyboard Shortcuts

- **Cmd/Ctrl + B**: Toggle sidebar
- **Space**: Start/Stop recording (when not in input field)

## Browser Compatibility

Requires modern browsers with support for:
- Web Audio API
- MediaRecorder API
- CSS Custom Properties
- ES2020+

## Migration from Vanilla JS

The original single-file `index.html` has been migrated to a modern React architecture while preserving:
- ✅ All voice recording functionality
- ✅ STT integration
- ✅ Color scheme (adapted to Tailwind)
- ✅ Microphone button design
- ✅ Card-based UI

The original file is backed up as `index.html.backup`
