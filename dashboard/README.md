# Ryumem Dashboard

Modern web dashboard for Ryumem - Bi-temporal Knowledge Graph Memory System.

Built with **Next.js 15**, **TypeScript**, **shadcn/ui**, and **Tailwind CSS**.

## Features

- **Secure Authentication** - API key login with session management
- **Chat Interface** - Natural language queries with hybrid search
- **Graph Visualization** - Interactive knowledge graph explorer
- **Entity Browser** - Browse, filter, and explore entities
- **Episode Management** - Add and view memories with metadata
- **Query History** - View augmented query history
- **Tool Analytics** - Track tool usage and performance metrics
- **System Settings** - Configure LLM providers, API keys, and search parameters
- **Agent Configuration** - Customize agent instructions and behavior
- **Real-time Stats** - Monitor system health and growth
- **Dark/Light Mode** - Beautiful theme support

## Quick Start

### Prerequisites

- **Node.js 18+**
- **Ryumem API server** running (see [server/README.md](../server/README.md))

### Option 1: Docker (Recommended)

```bash
# From dashboard directory
cd dashboard

# Configure environment
cp env.template .env
# Edit .env with your API URL

# Build and run
docker build -t ryumem-dashboard .
docker run -p 3000:3000 ryumem-dashboard
```

### Option 2: Local Development

```bash
# Install dependencies
cd dashboard
npm install

# Configure environment
cp env.template .env
# Edit .env if needed

# Start development server
npm run dev
```

Dashboard will be available at **http://localhost:3000**

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000` | Ryumem API server URL |
| `NEXT_PUBLIC_GITHUB_REDIRECT_URI` | No | - | GitHub OAuth redirect URI |

**Note:** All `NEXT_PUBLIC_*` variables are baked into the build at compile time. Rebuild if you change them.

## Usage

### First Time Setup

1. **Start the API Server** (in another terminal):
   ```bash
   cd server
   uvicorn main:app --reload
   ```

2. **Register a Customer** (get API key):
   ```bash
   curl -X POST http://localhost:8000/register \
     -H "Content-Type: application/json" \
     -d '{"customer_id": "my_company"}'
   ```

3. **Login to Dashboard**:
   - Open http://localhost:3000
   - Enter your API key (starts with `ryu_`)
   - Click "Sign in"

### Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Chat & Query** | Natural language search with hybrid retrieval |
| **Graph** | Interactive knowledge graph visualization (requires entity extraction) |
| **Entities** | Browse and explore entities with filtering (requires entity extraction) |
| **Episodes** | View and manage memories with metadata |
| **Queries** | View augmented query history and patterns |
| **Tool Analytics** | Track tool execution and performance |
| **Agent Settings** | Configure agent instructions and behavior |

### Settings Page

Configure system settings with hot-reload:
- **API Keys** - OpenAI and Gemini keys
- **LLM** - Provider, model, temperatures
- **Embedding** - Provider, model, dimensions
- **Search** - Strategy, thresholds
- **Entity Extraction** - Enable/disable
- **Tool Tracking** - Query augmentation
- **Community** - Detection settings

## Docker Deployment

### Build

```bash
cd dashboard
docker build -t ryumem-dashboard .
```

### Run

```bash
docker run -p 3000:3000 ryumem-dashboard
```

### Docker Compose

See the root `docker-compose.yml` for running both dashboard and server together:

```bash
# From project root
docker-compose up -d
```

## Development

### Available Scripts

```bash
npm run dev      # Start with hot-reload
npm run build    # Build for production
npm start        # Start production server
npm run lint     # Lint code
npm run format   # Format code
```

### Project Structure

```
dashboard/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── page.tsx           # Main dashboard
│   │   ├── settings/page.tsx  # Settings page
│   │   ├── login/page.tsx     # Login page
│   │   └── layout.tsx         # Root layout
│   ├── components/
│   │   ├── chat-interface.tsx # Query search UI
│   │   ├── graph-visualization.tsx
│   │   ├── entity-browser.tsx
│   │   ├── episodes-list.tsx
│   │   └── ui/                # shadcn/ui components
│   └── lib/
│       ├── api.ts             # Typed API client
│       └── utils.ts           # Utilities
├── package.json
├── tailwind.config.ts
└── next.config.js
```

### Adding Components

```bash
# Add new shadcn/ui component
npx shadcn@latest add [component-name]

# Examples
npx shadcn@latest add dialog
npx shadcn@latest add dropdown-menu
```

### Tech Stack

- **Next.js 15** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first CSS
- **shadcn/ui** - Accessible component library
- **Radix UI** - Headless UI primitives
- **Lucide Icons** - Icon library
- **React Flow** - Graph visualization
- **Next Themes** - Dark mode support

## Troubleshooting

### Common Issues

**"API connection failed"**
1. Ensure API server is running at the configured URL
2. Check `NEXT_PUBLIC_API_URL` in `.env`
3. Verify CORS is configured in server

**"Invalid API key"**
1. Register customer via `/register` endpoint
2. Use correct API key (starts with `ryu_`)

**Graph/Entity tabs not showing**
1. Check `entity_extraction.enabled` in Settings
2. Enable entity extraction and refresh

**Build errors**
```bash
# Clear cache and rebuild
rm -rf .next node_modules
npm install
npm run build
```

## License

Apache License 2.0 - See [LICENSE](../LICENSE) for details.
