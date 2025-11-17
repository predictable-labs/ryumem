# Ryumem Dashboard

Modern web dashboard for Ryumem - Bi-temporal Knowledge Graph Memory System.

Built with **Next.js 14**, **TypeScript**, and **shadcn/ui**.

## Features

✨ **Dashboard Features**:
- 📝 **Add Episodes** - Store new memories with automatic entity & relationship extraction
- 🔍 **Query Interface** - Search the knowledge graph with multiple strategies
- 📊 **Real-time Stats** - View counts of episodes, entities, relationships, and communities
- 🎨 **Modern UI** - Beautiful interface built with shadcn/ui components
- ⚡ **Fast & Responsive** - Optimized Next.js performance
- 🌓 **Dark Mode Ready** - Built-in dark mode support

## Screenshots

### Chat & Query Interface
Search your knowledge graph using hybrid search (semantic + BM25 + graph traversal):
- View entities with type badges and relevance scores
- Explore facts and relationships
- Multiple search strategies (hybrid, semantic, BM25, graph)

### Add Episodes
Add new memories to the knowledge graph:
- Simple text input
- Source type selection (text, message, JSON)
- Example episodes for quick testing
- Real-time feedback

### Stats Dashboard
Monitor your knowledge graph growth:
- Total episodes stored
- Number of entities extracted
- Relationship count
- Community clusters detected

## Installation

### Prerequisites

1. **Node.js 18+** installed
2. **Ryumem API server** running (see `../server/README.md`)

### Setup

1. **Install dependencies:**

```bash
cd dashboard
npm install
```

2. **Configure environment variables:**

```bash
# Copy the template
cp env.template .env.local

# Edit .env.local
nano .env.local
```

Set the API URL:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. **Start the development server:**

```bash
npm run dev
```

The dashboard will be available at **http://localhost:3000**

## Usage

### Starting the Dashboard

```bash
# Development mode with hot reload
npm run dev

# Production build
npm run build
npm start

# Linting
npm run lint
```

### Using the Dashboard

#### 1. Add Episodes

Navigate to the "Add Episodes" tab:

1. Enter text content (e.g., "Alice works at Google as a Software Engineer")
2. Select source type (text, message, or JSON)
3. Click "Add Episode"
4. Entities and relationships are automatically extracted

**Example episodes provided:**
- Click on example buttons to quickly populate the form
- Try different types of information (people, places, organizations, relationships)

#### 2. Query Knowledge Graph

Navigate to the "Chat & Query" tab:

1. Enter a question (e.g., "Where does Alice work?")
2. Select search strategy:
   - **Hybrid** (recommended): Combines all search methods
   - **Semantic**: Embedding-based similarity
   - **BM25**: Keyword matching
   - **Graph**: Relationship navigation
3. Click search or press Enter
4. View results organized by entities and facts

**Example queries provided:**
- Click on examples to quickly test search
- Try natural language questions
- Experiment with different search strategies

#### 3. Monitor Statistics

The stats panel shows real-time metrics:
- **Episodes**: Total memories stored
- **Entities**: People, places, things extracted
- **Relationships**: Facts and connections
- **Communities**: Detected clusters

Stats automatically refresh when you add new episodes.

## Architecture

```
dashboard/
├── src/
│   ├── app/                    # Next.js app directory
│   │   ├── page.tsx           # Main dashboard page
│   │   ├── layout.tsx         # Root layout with Toaster
│   │   └── globals.css        # Global styles (Tailwind + shadcn)
│   ├── components/
│   │   ├── episode-form.tsx   # Episode submission form
│   │   ├── chat-interface.tsx # Search/query interface
│   │   ├── stats-panel.tsx    # Statistics display
│   │   └── ui/                # shadcn/ui components
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── input.tsx
│   │       ├── textarea.tsx
│   │       ├── select.tsx
│   │       ├── badge.tsx
│   │       ├── tabs.tsx
│   │       ├── label.tsx
│   │       ├── toast.tsx
│   │       ├── toaster.tsx
│   │       └── use-toast.ts
│   └── lib/
│       ├── api.ts             # API client for Ryumem backend
│       └── utils.ts           # Utility functions
├── public/                    # Static assets
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
├── components.json            # shadcn/ui config
└── README.md                  # This file
```

## API Integration

The dashboard communicates with the Ryumem FastAPI backend:

```typescript
// lib/api.ts
import { api } from "@/lib/api";

// Add episode
await api.addEpisode({
  content: "Alice works at Google",
  user_id: "user_123",
  source: "text"
});

// Search
const results = await api.search({
  query: "Where does Alice work?",
  user_id: "user_123",
  strategy: "hybrid",
  limit: 10
});

// Get stats
const stats = await api.getStats("user_123");
```

All API calls are typed with TypeScript for safety and autocomplete.

## Customization

### Styling

The dashboard uses **Tailwind CSS** and **shadcn/ui** components:

- Edit `tailwind.config.ts` for theme customization
- Modify `src/app/globals.css` for global styles
- Change color schemes in CSS variables (`:root` and `.dark`)

### Components

All components are customizable:

```typescript
// src/components/episode-form.tsx
// Modify form fields, validation, examples

// src/components/chat-interface.tsx
// Customize search UI, result display

// src/components/stats-panel.tsx
// Add new statistics, change layout
```

### API Client

Extend the API client in `src/lib/api.ts`:

```typescript
class RyumemAPI {
  // Add new methods
  async customEndpoint() {
    return this.request('/custom-endpoint');
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Ryumem API server URL | http://localhost:8000 |

**Note:** All variables prefixed with `NEXT_PUBLIC_` are exposed to the browser.

## Development

### Adding New shadcn/ui Components

```bash
# Install new shadcn/ui component
npx shadcn-ui@latest add [component-name]

# Example: add dialog
npx shadcn-ui@latest add dialog
```

### Project Structure

- **App Router**: Uses Next.js 14 App Router
- **Server Components**: Page-level components are Server Components by default
- **Client Components**: Interactive components use `"use client"` directive
- **API Routes**: Not used (external FastAPI backend)

### TypeScript

The project uses strict TypeScript:

```json
{
  "compilerOptions": {
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true
  }
}
```

## Deployment

### Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

Set environment variable in Vercel dashboard:
- `NEXT_PUBLIC_API_URL` → Your production API URL

### Docker

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
```

Build and run:
```bash
docker build -t ryumem-dashboard .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://api:8000 ryumem-dashboard
```

### Other Platforms

The dashboard can be deployed to:
- **Netlify**: Use Next.js plugin
- **Railway**: Auto-deploys from git
- **Cloudflare Pages**: Requires @cloudflare/next-on-pages
- **AWS Amplify**: Full Next.js support
- **Self-hosted**: Use `npm run build && npm start`

## Troubleshooting

### "API connection failed"

1. Ensure the Ryumem API server is running:
   ```bash
   cd ../server
   uvicorn main:app --reload
   ```

2. Check `NEXT_PUBLIC_API_URL` in `.env.local`

3. Verify CORS is configured in server (see `server/main.py`)

### "No results found" when searching

1. Add some episodes first using the "Add Episodes" tab
2. Wait a few seconds for processing
3. Try different search strategies
4. Check API server logs for errors

### Styling issues

1. Ensure Tailwind CSS is properly configured
2. Check `tailwind.config.ts` includes all content paths
3. Verify `globals.css` is imported in `layout.tsx`

### Build errors

```bash
# Clear Next.js cache
rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Rebuild
npm run build
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

Requires JavaScript enabled.

## Performance

- **First Load**: ~200-300ms
- **Page Transitions**: Instant (client-side routing)
- **API Calls**: Depends on backend latency
- **Bundle Size**: ~150KB gzipped

Optimizations:
- Static generation where possible
- Image optimization via Next.js
- Lazy loading of components
- Code splitting by route

## Contributing

To contribute to the dashboard:

1. Follow the code style (use Prettier)
2. Write TypeScript with strict types
3. Test responsive layouts (mobile, tablet, desktop)
4. Ensure accessibility (ARIA labels, keyboard navigation)

## Support

For issues or questions:
- Check the main [Ryumem README](../README.md)
- Review [Server documentation](../server/README.md)
- Check browser console for errors
- Verify API server is running and accessible

## License

MIT License - Same as Ryumem parent project

---

**Built with ❤️ using:**
- [Next.js](https://nextjs.org/)
- [shadcn/ui](https://ui.shadcn.com/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Radix UI](https://www.radix-ui.com/)
- [Lucide Icons](https://lucide.dev/)

