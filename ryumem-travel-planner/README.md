# Ryumem Travel Planner Demo

An interactive web demo showcasing Ryumem's **memory-assisted performance optimization** through a multi-step travel planning workflow. Watch query response times improve dramatically as the system learns from similar queries!

## Key Features

### 🚀 Performance Optimization
- **First Query**: Full tool execution (~5.5 seconds)
- **Similar Queries**: Memory-assisted execution (~1.3 seconds)
- **Up to 76-77% faster** response times with intelligent tool selection
- Real-time performance metrics and visualization

### 🔄 Workflow Management
- Auto-generated workflows reflecting actual execution (optimized workflows show disabled exploratory tools)
- **Two view modes**: Simple list view and interactive graph view
- **Graph visualization**: See tool dependencies and parallel execution paths
- Editable workflows with tool enable/disable controls
- Workflow matching for similar queries
- Visual workflow indicators in chat messages
- Custom workflow persistence and reuse

### 🎨 Flexible UI
- **Resizable sidebar**: Drag to adjust chat/sidebar split (default 70/30)
- Wider viewport for workflow visualization
- Smooth resize with minimum/maximum constraints

### 🧠 Memory Tracking
- Automatic detection of similar queries
- Context storage and retrieval
- Visual indicators for memory-assisted responses
- Query similarity matching with configurable threshold

### 🔧 Multi-Tool Workflow
Demonstrates a comprehensive 10-tool travel planning workflow with intelligent tool selection:

**Exploratory Tools** (skipped for similar queries):
1. **validate_destination** - Validates destination exists
2. **check_weather** - Retrieves weather forecast
3. **get_exchange_rates** - Fetches currency conversion rates
4. **calculate_travel_time** - Estimates travel duration
5. **check_hotel_availability** - Checks accommodation options
6. **get_local_attractions** - Finds tourist attractions

**Core Tools** (always executed, optimized for similar queries):
7. **search_flights** - Finds flight prices between cities
8. **estimate_budget** - Calculates total trip costs
9. **create_itinerary** - Generates tourist attractions
10. **finalize_trip** - Combines all data into a trip summary

### 📊 Visual Analytics
- Performance metrics dashboard showing:
  - Memory hit rate
  - Average speed improvement
  - Total time saved
  - Per-query performance timeline
- Collapsible tool execution details
- Real-time execution time tracking

## Tech Stack

- **Next.js 15** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI components
- **Lucide React** - Icons

## Getting Started

1. Install dependencies:
   ```bash
   cd examples/demo/ryumem-travel-planner
   npm install
   ```

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Open [http://localhost:3000](http://localhost:3000) in your browser

## Try It Out

The demo provides **6 preset query buttons**. Click any query to execute it and watch the performance metrics:

### Available Queries
1. "Plan a trip from Mumbai to Bangalore for 2 nights"
2. "Plan a trip from Mumbai to Bangalore for 3 nights"
3. "I want to visit Bangalore from Mumbai for 2 nights"
4. "Plan a trip from Delhi to Mumbai for 3 nights"
5. "Plan a trip from Delhi to Mumbai for 2 nights"
6. "I need a 3-night trip to Mumbai from Delhi"

### How to Use
1. Click any query button to execute it
2. The first query will take ~5.5 seconds (full execution with 10 tools)
3. An **optimized workflow is automatically generated** showing all 10 tools enabled
4. **Resize the sidebar** by dragging the divider between chat and sidebar for better visibility
5. **Toggle between List and Graph views** using the buttons in the Workflows panel
   - **List view**: Traditional list with tool toggles
   - **Graph view**: Visual DAG showing tool dependencies and parallel execution paths
6. Click on the Settings icon in the workflow to edit it (enable/disable exploratory tools)
7. Click a similar query (e.g., another Mumbai to Bangalore trip)
8. Watch it complete in ~1.3 seconds with optimized execution (76-77% faster!)
9. The **new workflow shows only 4 enabled tools** (exploratory tools disabled) - reflecting actual execution
10. Observe the performance metrics update in real-time
11. Click **"Reset Demo"** in the top-right to start fresh

## How It Works

### Memory-Assisted Optimization

When you ask a similar query, Ryumem:

1. **Detects Similarity**: Analyzes query keywords and structure
2. **Retrieves Context**: Pulls relevant cached information
3. **Intelligent Tool Selection**: Skips 6 exploratory tools, executes only 4 core tools
4. **Optimizes Execution**: Reduces tool execution time by 50-90% per tool
5. **Tracks Performance**: Records metrics for visualization

### Performance Comparison

| Tool | First Query | With Workflow | Improvement |
|------|-------------|---------------|-------------|
| **Exploratory Tools** | | | |
| validate_destination | 400ms | Skipped | 100% ↓ |
| check_weather | 500ms | Skipped | 100% ↓ |
| get_exchange_rates | 450ms | Skipped | 100% ↓ |
| calculate_travel_time | 380ms | Skipped | 100% ↓ |
| check_hotel_availability | 650ms | Skipped | 100% ↓ |
| get_local_attractions | 550ms | Skipped | 100% ↓ |
| **Core Tools** | | | |
| search_flights | 800ms | 400ms | 50% ↓ |
| estimate_budget | 600ms | 350ms | 42% ↓ |
| create_itinerary | 700ms | 350ms | 50% ↓ |
| finalize_trip | 500ms | 200ms | 60% ↓ |
| **Total** | **~5.5s** | **~1.3s** | **76-77% ↓** |

## Project Structure

```
├── app/
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Main page
│   └── globals.css             # Global styles
├── components/
│   ├── chat-interface.tsx      # Main chat UI with performance tracking
│   ├── tool-call-card.tsx      # Collapsible tool execution display
│   ├── memory-panel.tsx        # Memory visualization
│   ├── performance-panel.tsx   # Performance metrics dashboard
│   ├── workflow-panel.tsx      # Workflow management UI
│   └── ui/                     # shadcn components (Switch, Badge, etc.)
├── lib/
│   ├── types.ts                # TypeScript types
│   ├── mock-workflow.ts        # Mock tool execution with timing logic
│   └── utils.ts                # Utility functions
└── public/                     # Static assets
```

## User Interface

### Preset Query Buttons
The demo uses **6 clickable query buttons** arranged in a 2-column grid:
- Click any button to execute that query
- All buttons disabled during processing
- Simple, clean interface focused on performance comparison

### Visual Indicators
The demo uses color-coded badges to show query performance:
- 🟣 **Purple Badge**: Custom workflow applied
- 🟡 **Amber Badge**: Workflow generated
- 🟢 **Green Badge**: Memory-assisted query (fast)
- 🔵 **Blue Badge**: First-time query (baseline)
- 🟡 **Yellow Badge**: Similar queries found
- ⚡ **Lightning Icon**: Memory hit indicator

## Mock Implementation

This is a **mock demo** for demonstration purposes. It simulates:

- Tool execution with realistic delays
- Memory storage and similarity matching
- Performance optimization based on cached context
- Query tracking and analytics

The actual Ryumem library provides these capabilities with real backend integration.

## Key Takeaways

1. **Workflow Management**: Auto-generated workflows can be customized and reused for similar queries
2. **Intelligent Tool Selection**: System uses 10 tools initially, then only 4 relevant tools with custom workflows
3. **Dramatic Speed Improvements**: Similar queries execute 76-77% faster with optimized workflows
4. **Cumulative Savings**: Time savings add up across many queries
5. **Smart Caching**: System learns from query patterns and optimizes tool execution
6. **Real-time Insights**: Performance metrics and workflow indicators update live

## Learn More

- [Ryumem GitHub](https://github.com/Predictable-org/ryumem)
- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui](https://ui.shadcn.com/)

---

## License

GNU Affero General Public License v3.0 (AGPL-3.0) - See [LICENSE](../LICENSE) for details.

---

**Note**: This demo simulates Ryumem's core value proposition - showing how memory-assisted execution and workflow management dramatically improves response times through intelligent tool selection and optimized execution. The system learns which tools are necessary for similar queries, skipping exploratory work and focusing on core operations. Users can customize workflows to further optimize performance based on their specific needs. In a production environment, these optimizations would apply to real API calls, database queries, and computational tasks.

