# Ryumem Dashboard

Modern web dashboard for Ryumem - Bi-temporal Knowledge Graph Memory System.

Built with **Next.js 15**, **TypeScript**, **shadcn/ui**, and **Tailwind CSS**.

## Features

✨ **Dashboard Capabilities**:
- 🔐 **Secure Authentication** - API key login with session management
- 💬 **Chat Interface** - Natural language queries with hybrid search
- 📊 **Graph Visualization** - Interactive knowledge graph explorer
- 🗂️ **Entity Browser** - Browse, filter, and explore entities
- 📝 **Episode Management** - Add and view memories with metadata
- 🔍 **Query History** - View augmented query history
- 🛠️ **Tool Analytics** - Track tool usage and performance metrics
- ⚙️ **System Settings** - Configure LLM providers, API keys, and search parameters
- 👤 **Agent Configuration** - Customize agent instructions and behavior
- 📈 **Real-time Stats** - Monitor system health and growth
- 🌓 **Dark/Light Mode** - Beautiful theme support
- 🎨 **Modern UI** - Responsive design with animations

## Dashboard Overview

### Main Tabs

The dashboard provides 7 main tabs (5 when entity extraction is disabled):
1. **Chat & Query** - Natural language search with hybrid retrieval strategies
2. **Graph** - Interactive knowledge graph visualization (requires entity extraction)
3. **Entities** - Browse and explore entities with filtering (requires entity extraction)
4. **Episodes** - View and manage memories with metadata
5. **Queries** - View augmented query history and patterns
6. **Tool Analytics** - Track tool execution and performance
7. **Agent Settings** - Configure agent instructions and behavior

### Settings Page

Configure system settings with hot-reload across 7 categories:
- **API Keys** - OpenAI and Gemini keys
- **LLM** - Provider, model, temperatures, tokens
- **Embedding** - Provider, model, dimensions
- **Search** - Strategy, RRF parameters, thresholds
- **Entity Extraction** - Enable/disable, similarity thresholds
- **Tool Tracking** - Query augmentation configuration
- **Community** - Detection settings

## Installation

### Prerequisites

- **Node.js 18+** installed
- **Ryumem API server** running (see `../server/README.md`)

### Setup

1. **Install dependencies:**

```bash
cd dashboard
npm install
```

2. **Configure environment:**

```bash
# Copy template
cp env.template .env.local

# Edit .env.local
nano .env.local
```

Set the API URL:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. **Start development server:**

```bash
npm run dev
```

Dashboard will be available at **http://localhost:3000**

## Usage

### Development Mode

```bash
# Start with hot-reload
npm run dev

# Start on different port
PORT=3001 npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint

# Format code
npm run format
```

### First Time Setup

1. **Start the API Server** (in another terminal):
   ```bash
   cd ../server
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

### Using the Dashboard

Once logged in, explore the dashboard tabs:

- **Chat & Query**: Enter natural language queries and select search strategy (Hybrid recommended)
- **Graph**: Visualize entities and relationships with interactive force-directed layout
- **Entities**: Browse, filter, and explore entities with detailed relationship views
- **Episodes**: Add new memories or view existing ones with filtering
- **Queries**: View augmented query history and pattern analysis
- **Tool Analytics**: Track tool execution statistics and performance
- **Agent Settings**: Configure agent instructions and behavior
- **Settings Page**: Configure LLM providers, API keys, search parameters, and more with hot-reload

## Architecture

```
dashboard/
├── src/
│   ├── app/                        # Next.js App Router
│   │   ├── page.tsx               # Main dashboard (7 tabs)
│   │   ├── settings/
│   │   │   └── page.tsx           # Settings page
│   │   ├── login/
│   │   │   └── page.tsx           # Login page
│   │   ├── layout.tsx             # Root layout
│   │   └── globals.css            # Global styles
│   ├── components/
│   │   ├── header.tsx             # Navigation header
│   │   ├── footer.tsx             # Footer
│   │   ├── chat-interface.tsx    # Search/query UI
│   │   ├── graph-visualization.tsx # Graph viewer
│   │   ├── entity-browser.tsx     # Entity list
│   │   ├── entity-detail-panel.tsx # Entity details
│   │   ├── episodes-list.tsx      # Episode management
│   │   ├── episode-form-modal.tsx # Add episode modal
│   │   ├── augmented-queries-viewer.tsx # Query history
│   │   ├── tool-analytics-panel.tsx # Tool analytics
│   │   ├── agent-instruction-editor.tsx # Agent config
│   │   ├── stats-panel.tsx        # Real-time stats
│   │   ├── theme-provider.tsx     # Dark/light mode
│   │   ├── theme-toggle.tsx       # Theme switcher
│   │   ├── AuthProvider.tsx       # Auth context
│   │   └── ui/                    # shadcn/ui components
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── input.tsx
│   │       ├── tabs.tsx
│   │       ├── select.tsx
│   │       ├── badge.tsx
│   │       ├── alert.tsx
│   │       └── ... (20+ components)
│   └── lib/
│       ├── api.ts                 # API client with types
│       └── utils.ts               # Utility functions
├── public/                        # Static assets
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
├── components.json                # shadcn/ui config
└── README.md                      # This file
```

## API Integration

The dashboard communicates with the Ryumem FastAPI backend via a typed API client:

```typescript
// lib/api.ts
import { api } from "@/lib/api";

// All methods are fully typed with TypeScript

// Authentication
await api.login("ryu_abc123...");
const customer = await api.getCustomerMe();

// Episodes
await api.addEpisode({
  content: "Alice works at Google",
  user_id: "user_123",
  source: "text"
});
const episodes = await api.getEpisodes({ user_id: "user_123", limit: 50 });

// Search
const results = await api.search({
  query: "Where does Alice work?",
  user_id: "user_123",
  strategy: "hybrid",
  limit: 10
});

// Settings (Hot-reload)
const settings = await api.getSettings(false);
await api.updateSettings({
  "llm.provider": "gemini",
  "entity_extraction.enabled": false
});

// Stats
const stats = await api.getStats("user_123");
const users = await api.getUsers();

// Entities & Graph
const entities = await api.getEntitiesList("user_123");
const graphData = await api.getGraphData("user_123");
const entityContext = await api.getEntityContext("Alice", "user_123");
```

All API calls include:
- TypeScript type safety
- Automatic error handling
- API key authentication
- Response type validation

## Conditional Features

### Entity Extraction Toggle

When `entity_extraction.enabled` is set to `false`:
- **Graph tab** - Hidden
- **Entities tab** - Hidden
- **Tab layout** - Adjusts from 7 to 5 columns
- **Settings** - Still accessible to re-enable

This saves ~30-50% on LLM tokens when entity extraction isn't needed.

## Customization

### Styling

**Tailwind CSS** configuration:
- Edit `tailwind.config.ts` for theme customization
- Modify CSS variables in `globals.css`
- Change color schemes (`:root` and `.dark`)

**Theme Colors:**
```css
/* Light mode */
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 222.2 47.4% 11.2%;
  /* ... */
}

/* Dark mode */
.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --primary: 210 40% 98%;
  /* ... */
}
```

### Adding Components

```bash
# Add new shadcn/ui component
npx shadcn-ui@latest add [component-name]

# Examples
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add dropdown-menu
npx shadcn-ui@latest add tooltip
```

### Custom API Methods

Extend the API client:

```typescript
// src/lib/api.ts
class RyumemAPI {
  // Add new endpoint
  async customMethod(params: any) {
    return this.request('/custom-endpoint', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Ryumem API server URL | http://localhost:8000 |

**Note:** All `NEXT_PUBLIC_*` variables are exposed to the browser.

## Development

### Tech Stack

- **Next.js 15** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first CSS
- **shadcn/ui** - Accessible component library
- **Radix UI** - Headless UI primitives
- **Lucide Icons** - Icon library
- **React Flow** - Graph visualization
- **Next Themes** - Dark mode support

### Project Structure

- **App Router**: Server Components by default
- **Client Components**: Use `"use client"` directive
- **API Routes**: External FastAPI backend (no Next.js API routes)
- **Strict TypeScript**: Full type safety

### Adding New Features

1. Create component in `src/components/`
2. Add types to `src/lib/api.ts` if needed
3. Use component in pages
4. Add to navigation if needed
5. Test responsive layout
6. Ensure accessibility (ARIA labels, keyboard nav)

## Deployment

### Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

**Environment variables in Vercel:**
- `NEXT_PUBLIC_API_URL` → Your production API URL (e.g., https://api.ryumem.io)

### Docker

The dashboard uses a multi-stage build for optimized production images.

**1. Configure environment:**

Create a `.env` file from the template before building:
```bash
cp env.template .env
# Edit .env with your configuration
```

Required `.env` variables:
```bash
NEXT_PUBLIC_API_URL=http://your-server:8000
NEXT_PUBLIC_GITHUB_REDIRECT_URI=http://your-domain/login
```

> **Note:** `NEXT_PUBLIC_*` variables are baked into the build at compile time, so you must rebuild when changing them.

**2. Build:**
```bash
cd dashboard
docker build -t ryumem-dashboard .
```

**3. Run:**
```bash
docker run -p 3000:3000 ryumem-dashboard
```

**Docker Compose example:**
```yaml
services:
  dashboard:
    build: ./dashboard
    ports:
      - "3000:3000"
    depends_on:
      - server

  server:
    build:
      context: .
      dockerfile: server/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - server/.env
    environment:
      - RYUMEM_DB_FOLDER=/app/data
    volumes:
      - ./server/data:/app/data
```

### Other Platforms

- **Netlify** - Use Next.js plugin
- **Railway** - Auto-deploy from Git
- **Cloudflare Pages** - Requires `@cloudflare/next-on-pages`
- **AWS Amplify** - Full Next.js support
- **Self-hosted** - `npm run build && npm start`

## Troubleshooting

### Common Issues

**"API connection failed"**
1. Ensure API server is running:
   ```bash
   cd ../server && uvicorn main:app --reload
   ```
2. Check `NEXT_PUBLIC_API_URL` in `.env.local`
3. Verify CORS configured in `server/main.py`

**"Invalid API key" / "Unauthorized"**
1. Register customer via `/register` endpoint
2. Use correct API key (starts with `ryu_`)
3. Check API key in browser localStorage

**No results when searching**
1. Add episodes first via "Episodes" tab
2. Wait a few seconds for processing
3. Try different search strategies
4. Check API server logs

**Graph/Entity tabs not showing**
1. Check `entity_extraction.enabled` in Settings
2. Enable entity extraction
3. Refresh page after enabling

**Settings changes not applying**
1. Hot-reload happens automatically
2. Check validation errors in UI
3. Verify API keys when switching providers
4. Check server logs for errors

**Build errors**
```bash
# Clear cache
rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Rebuild
npm run build
```

**Styling issues**
1. Check Tailwind config includes content paths
2. Verify `globals.css` imported in `layout.tsx`
3. Clear browser cache
4. Check for CSS conflicts

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

Requires JavaScript enabled.

## Performance

- **First Load**: ~200-300ms (optimized bundle)
- **Page Transitions**: Instant (client-side routing)
- **API Calls**: Depends on backend latency
- **Bundle Size**: ~180KB gzipped

**Optimizations:**
- Static generation where possible
- Image optimization via Next.js
- Lazy loading of components
- Code splitting by route
- Tailwind CSS purging
- React Server Components

## Accessibility

- Keyboard navigation support
- ARIA labels and roles
- Screen reader compatible
- Focus management
- High contrast mode support
- Responsive touch targets

## Contributing

To contribute to the dashboard:

1. Follow code style (use Prettier)
2. Write TypeScript with strict types
3. Test responsive layouts (mobile, tablet, desktop)
4. Ensure accessibility (ARIA labels, keyboard navigation)
5. Add JSDoc comments for complex functions
6. Test dark mode compatibility

## Support

For issues or questions:
- Check [main README](../README.md)
- Review [Server documentation](../server/README.md)
- Check browser console for errors
- Verify API server is running at configured URL
- Check network tab for API call failures

## License

MIT License - Same as Ryumem parent project

---

**Built with ❤️ using:**
- [Next.js](https://nextjs.org/) - React framework
- [shadcn/ui](https://ui.shadcn.com/) - Component library
- [Tailwind CSS](https://tailwindcss.com/) - Styling
- [Radix UI](https://www.radix-ui.com/) - Primitives
- [Lucide Icons](https://lucide.dev/) - Icons
- [React Flow](https://reactflow.dev/) - Graph visualization
