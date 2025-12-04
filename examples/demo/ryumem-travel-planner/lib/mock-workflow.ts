import { Message, ToolCall, MemoryEntry, PerformanceMetric, Workflow, WorkflowTool } from "./types";

// Simulate tool execution delays
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// Base delays for tools (in ms) - used for first-time execution
const BASE_DELAYS = {
  validate_destination: 400,
  check_weather: 500,
  get_exchange_rates: 450,
  calculate_travel_time: 380,
  search_flights: 800,
  check_hotel_availability: 650,
  estimate_budget: 600,
  get_local_attractions: 550,
  create_itinerary: 700,
  finalize_trip: 500,
};

// Optimized delays when using memory (76-77% faster)
const OPTIMIZED_DELAYS = {
  validate_destination: 0, // Skipped
  check_weather: 0, // Skipped
  get_exchange_rates: 0, // Skipped
  calculate_travel_time: 0, // Skipped
  search_flights: 400,
  check_hotel_availability: 0, // Skipped
  estimate_budget: 350,
  get_local_attractions: 0, // Skipped
  create_itinerary: 350,
  finalize_trip: 200,
};

// Mock flight prices
const FLIGHT_PRICES: Record<string, number> = {
  "Mumbai-Delhi": 5500,
  "Delhi-Mumbai": 5300,
  "Mumbai-Bangalore": 4200,
  "Bangalore-Delhi": 4700,
  "Delhi-Bangalore": 4600,
  "Bangalore-Mumbai": 4100,
};

// Mock itineraries
const ITINERARIES: Record<string, string[]> = {
  Delhi: ["India Gate", "Qutub Minar", "Humayun's Tomb"],
  Mumbai: ["Marine Drive", "Gateway of India", "Bandra Fort"],
  Bangalore: ["Cubbon Park", "Lalbagh", "MG Road"],
};

// Tool 1: Validate Destination (exploratory - skipped with memory)
export async function validateDestination(
  destination: string,
  useMemory: boolean = false
): Promise<{ destination: string; valid: boolean; country: string }> {
  if (useMemory) return { destination, valid: true, country: "India" };

  const delayTime = BASE_DELAYS.validate_destination;
  await delay(delayTime);
  return {
    destination,
    valid: true,
    country: "India",
  };
}

// Tool 2: Check Weather (exploratory - skipped with memory)
export async function checkWeather(
  destination: string,
  useMemory: boolean = false
): Promise<{ destination: string; temperature: number; condition: string }> {
  if (useMemory) return { destination, temperature: 28, condition: "Clear" };

  const delayTime = BASE_DELAYS.check_weather;
  await delay(delayTime);
  return {
    destination,
    temperature: 28,
    condition: "Clear",
  };
}

// Tool 3: Get Exchange Rates (exploratory - skipped with memory)
export async function getExchangeRates(
  useMemory: boolean = false
): Promise<{ currency: string; rate: number }> {
  if (useMemory) return { currency: "INR", rate: 1 };

  const delayTime = BASE_DELAYS.get_exchange_rates;
  await delay(delayTime);
  return {
    currency: "INR",
    rate: 1,
  };
}

// Tool 4: Calculate Travel Time (exploratory - skipped with memory)
export async function calculateTravelTime(
  origin: string,
  destination: string,
  useMemory: boolean = false
): Promise<{ origin: string; destination: string; duration_hours: number }> {
  if (useMemory) return { origin, destination, duration_hours: 2 };

  const delayTime = BASE_DELAYS.calculate_travel_time;
  await delay(delayTime);
  return {
    origin,
    destination,
    duration_hours: 2,
  };
}

// Tool 5: Search Flights (CORE - always used)
export async function searchFlights(
  origin: string,
  destination: string,
  useMemory: boolean = false
): Promise<{ origin: string; destination: string; flight_price: number }> {
  const delayTime = useMemory ? OPTIMIZED_DELAYS.search_flights : BASE_DELAYS.search_flights;
  await delay(delayTime);
  const key = `${origin}-${destination}`;
  return {
    origin,
    destination,
    flight_price: FLIGHT_PRICES[key] || 6000,
  };
}

// Tool 6: Check Hotel Availability (exploratory - skipped with memory)
export async function checkHotelAvailability(
  destination: string,
  nights: number,
  useMemory: boolean = false
): Promise<{ destination: string; available: boolean; avg_price: number }> {
  if (useMemory) return { destination, available: true, avg_price: 2500 };

  const delayTime = BASE_DELAYS.check_hotel_availability;
  await delay(delayTime);
  return {
    destination,
    available: true,
    avg_price: 2500,
  };
}

// Tool 7: Estimate Budget (CORE - always used)
export async function estimateBudget(
  flight_price: number,
  hotel_nights: number,
  useMemory: boolean = false
): Promise<{
  flight_price: number;
  hotel_nights: number;
  hotel_cost: number;
  food_cost: number;
  total_budget: number;
}> {
  const delayTime = useMemory ? OPTIMIZED_DELAYS.estimate_budget : BASE_DELAYS.estimate_budget;
  await delay(delayTime);
  const hotel_rate = 2500;
  const food_cost_per_day = 800;
  const hotel_cost = hotel_rate * hotel_nights;
  const food_cost = food_cost_per_day * hotel_nights;

  return {
    flight_price,
    hotel_nights,
    hotel_cost,
    food_cost,
    total_budget: flight_price + hotel_cost + food_cost,
  };
}

// Tool 8: Get Local Attractions (exploratory - skipped with memory)
export async function getLocalAttractions(
  destination: string,
  useMemory: boolean = false
): Promise<{ destination: string; attractions: string[]; count: number }> {
  if (useMemory) return { destination, attractions: ITINERARIES[destination] || [], count: 3 };

  const delayTime = BASE_DELAYS.get_local_attractions;
  await delay(delayTime);
  const attractions = ITINERARIES[destination] || ["Explore local sights"];
  return {
    destination,
    attractions,
    count: attractions.length,
  };
}

// Tool 9: Create Itinerary (CORE - always used)
export async function createItinerary(
  destination: string,
  budget: number,
  useMemory: boolean = false
): Promise<{ destination: string; budget: number; itinerary: string[] }> {
  const delayTime = useMemory ? OPTIMIZED_DELAYS.create_itinerary : BASE_DELAYS.create_itinerary;
  await delay(delayTime);
  return {
    destination,
    budget,
    itinerary: ITINERARIES[destination] || ["Explore local sights"],
  };
}

// Tool 10: Finalize Trip (CORE - always used)
export async function finalizeTrip(
  params: {
    origin: string;
    destination: string;
    flight_price: number;
    hotel_cost: number;
    food_cost: number;
    total_budget: number;
    itinerary_spot_1: string;
    itinerary_spot_2: string;
    itinerary_spot_3: string;
  },
  useMemory: boolean = false
): Promise<string> {
  const delayTime = useMemory ? OPTIMIZED_DELAYS.finalize_trip : BASE_DELAYS.finalize_trip;
  await delay(delayTime);

  return `✈️ Trip Summary
----------------
From: ${params.origin}
To: ${params.destination}

Flight Price: ₹${params.flight_price}
Hotel Cost: ₹${params.hotel_cost}
Food Cost: ₹${params.food_cost}
Total Budget Required: ₹${params.total_budget}

🗒️ Itinerary:
- ${params.itinerary_spot_1}
- ${params.itinerary_spot_2}
- ${params.itinerary_spot_3}

Budget Remaining After Flight: ₹${params.total_budget - params.flight_price}`;
}

// Parse user input to extract trip details
export function parseTripRequest(input: string): {
  origin: string;
  destination: string;
  nights: number;
} | null {
  const lowerInput = input.toLowerCase();

  // Common city patterns
  const cities = ["mumbai", "delhi", "bangalore"];
  const foundCities: string[] = [];

  for (const city of cities) {
    if (lowerInput.includes(city)) {
      foundCities.push(city.charAt(0).toUpperCase() + city.slice(1));
    }
  }

  // Extract number of nights
  const nightsMatch = lowerInput.match(/(\d+)\s*(night|day)/);
  const nights = nightsMatch ? parseInt(nightsMatch[1]) : 3;

  // Determine origin and destination
  let origin = "";
  let destination = "";

  if (foundCities.length >= 2) {
    // Try to determine which is from and which is to
    const fromMatch = lowerInput.indexOf("from");
    const toMatch = lowerInput.indexOf("to");

    if (fromMatch !== -1 && toMatch !== -1) {
      const cityPositions = foundCities.map((city) => ({
        city,
        pos: lowerInput.indexOf(city.toLowerCase()),
      }));

      cityPositions.sort((a, b) => a.pos - b.pos);

      if (fromMatch < toMatch) {
        origin = cityPositions[0].city;
        destination = cityPositions[1].city;
      } else {
        origin = cityPositions[1].city;
        destination = cityPositions[0].city;
      }
    } else {
      origin = foundCities[0];
      destination = foundCities[1];
    }
  } else if (foundCities.length === 1) {
    destination = foundCities[0];
    origin = "Mumbai"; // default
  } else {
    return null;
  }

  return { origin, destination, nights };
}

// Execute the complete workflow
export async function executeTravelWorkflow(
  userInput: string,
  onToolStart: (toolCall: ToolCall) => void,
  onToolComplete: (toolCall: ToolCall) => void,
  useMemory: boolean = false,
  workflow?: Workflow
): Promise<string> {
  const tripDetails = parseTripRequest(userInput);

  if (!tripDetails) {
    return "I couldn't understand your trip request. Please specify your origin, destination, and number of nights. For example: 'Plan a trip from Mumbai to Delhi for 3 nights'";
  }

  const { origin, destination, nights } = tripDetails;

  // Helper to check if a tool should run based on workflow
  const shouldRunTool = (toolName: string): boolean => {
    if (workflow) {
      const tool = workflow.tools.find(t => t.name === toolName);
      return tool ? tool.enabled : true;
    }
    return !useMemory || ['search_flights', 'estimate_budget', 'create_itinerary', 'finalize_trip'].includes(toolName);
  };

  try {
    let toolResults: any = {};

    // Step 1: Validate Destination (SKIP if using memory or disabled in workflow)
    if (shouldRunTool('validate_destination')) {
      const validateTool: ToolCall = {
        id: `tool-${Date.now()}-1`,
        name: "validate_destination",
        status: "running",
        input: { destination },
        timestamp: new Date(),
      };
      onToolStart(validateTool);
      toolResults.validate = await validateDestination(destination, false);
      validateTool.status = "completed";
      validateTool.output = toolResults.validate;
      onToolComplete(validateTool);
    }

    // Step 2: Check Weather (SKIP if using memory or disabled in workflow)
    if (shouldRunTool('check_weather')) {
      const weatherTool: ToolCall = {
        id: `tool-${Date.now()}-2`,
        name: "check_weather",
        status: "running",
        input: { destination },
        timestamp: new Date(),
      };
      onToolStart(weatherTool);
      toolResults.weather = await checkWeather(destination, false);
      weatherTool.status = "completed";
      weatherTool.output = toolResults.weather;
      onToolComplete(weatherTool);
    }

    // Step 3: Get Exchange Rates (SKIP if using memory or disabled in workflow)
    if (shouldRunTool('get_exchange_rates')) {
      const exchangeTool: ToolCall = {
        id: `tool-${Date.now()}-3`,
        name: "get_exchange_rates",
        status: "running",
        input: {},
        timestamp: new Date(),
      };
      onToolStart(exchangeTool);
      toolResults.exchange = await getExchangeRates(false);
      exchangeTool.status = "completed";
      exchangeTool.output = toolResults.exchange;
      onToolComplete(exchangeTool);
    }

    // Step 4: Calculate Travel Time (SKIP if using memory or disabled in workflow)
    if (shouldRunTool('calculate_travel_time')) {
      const travelTimeTool: ToolCall = {
        id: `tool-${Date.now()}-4`,
        name: "calculate_travel_time",
        status: "running",
        input: { origin, destination },
        timestamp: new Date(),
      };
      onToolStart(travelTimeTool);
      toolResults.travelTime = await calculateTravelTime(origin, destination, false);
      travelTimeTool.status = "completed";
      travelTimeTool.output = toolResults.travelTime;
      onToolComplete(travelTimeTool);
    }

    // Step 5: Search Flights (CORE - always execute)
    const flightTool: ToolCall = {
      id: `tool-${Date.now()}-5`,
      name: "search_flights",
      status: "running",
      input: { origin, destination },
      timestamp: new Date(),
    };
    onToolStart(flightTool);
    const flightData = await searchFlights(origin, destination, useMemory || !!workflow);
    flightTool.status = "completed";
    flightTool.output = flightData;
    onToolComplete(flightTool);

    // Step 6: Check Hotel Availability (SKIP if using memory or disabled in workflow)
    if (shouldRunTool('check_hotel_availability')) {
      const hotelTool: ToolCall = {
        id: `tool-${Date.now()}-6`,
        name: "check_hotel_availability",
        status: "running",
        input: { destination, nights },
        timestamp: new Date(),
      };
      onToolStart(hotelTool);
      toolResults.hotel = await checkHotelAvailability(destination, nights, false);
      hotelTool.status = "completed";
      hotelTool.output = toolResults.hotel;
      onToolComplete(hotelTool);
    }

    // Step 7: Estimate Budget (CORE - always execute)
    const budgetTool: ToolCall = {
      id: `tool-${Date.now()}-7`,
      name: "estimate_budget",
      status: "running",
      input: { flight_price: flightData.flight_price, hotel_nights: nights },
      timestamp: new Date(),
    };
    onToolStart(budgetTool);
    const budgetData = await estimateBudget(flightData.flight_price, nights, useMemory || !!workflow);
    budgetTool.status = "completed";
    budgetTool.output = budgetData;
    onToolComplete(budgetTool);

    // Step 8: Get Local Attractions (SKIP if using memory or disabled in workflow)
    if (shouldRunTool('get_local_attractions')) {
      const attractionsTool: ToolCall = {
        id: `tool-${Date.now()}-8`,
        name: "get_local_attractions",
        status: "running",
        input: { destination },
        timestamp: new Date(),
      };
      onToolStart(attractionsTool);
      toolResults.attractions = await getLocalAttractions(destination, false);
      attractionsTool.status = "completed";
      attractionsTool.output = toolResults.attractions;
      onToolComplete(attractionsTool);
    }

    // Step 9: Create Itinerary (CORE - always execute)
    const itineraryTool: ToolCall = {
      id: `tool-${Date.now()}-9`,
      name: "create_itinerary",
      status: "running",
      input: { destination, budget: budgetData.total_budget },
      timestamp: new Date(),
    };
    onToolStart(itineraryTool);
    const itineraryData = await createItinerary(
      destination,
      budgetData.total_budget,
      useMemory || !!workflow
    );
    itineraryTool.status = "completed";
    itineraryTool.output = itineraryData;
    onToolComplete(itineraryTool);

    // Step 10: Finalize Trip (CORE - always execute)
    const finalizeTool: ToolCall = {
      id: `tool-${Date.now()}-10`,
      name: "finalize_trip",
      status: "running",
      input: {
        origin,
        destination,
        flight_price: budgetData.flight_price,
        hotel_cost: budgetData.hotel_cost,
        food_cost: budgetData.food_cost,
        total_budget: budgetData.total_budget,
        itinerary_spot_1: itineraryData.itinerary[0],
        itinerary_spot_2: itineraryData.itinerary[1],
        itinerary_spot_3: itineraryData.itinerary[2],
      },
      timestamp: new Date(),
    };
    onToolStart(finalizeTool);

    const summary = await finalizeTrip({
      origin,
      destination,
      flight_price: budgetData.flight_price,
      hotel_cost: budgetData.hotel_cost,
      food_cost: budgetData.food_cost,
      total_budget: budgetData.total_budget,
      itinerary_spot_1: itineraryData.itinerary[0],
      itinerary_spot_2: itineraryData.itinerary[1],
      itinerary_spot_3: itineraryData.itinerary[2],
    }, useMemory || !!workflow);
    finalizeTool.status = "completed";
    finalizeTool.output = { summary };
    onToolComplete(finalizeTool);

    return summary;
  } catch (error) {
    return `Error processing your request: ${error}`;
  }
}

// Calculate total execution time
export function calculateTotalExecutionTime(useMemory: boolean): number {
  if (useMemory) {
    // Only count non-zero delays (skipped tools have 0 delay)
    return Object.values(OPTIMIZED_DELAYS).reduce((sum, delay) => sum + delay, 0);
  }
  return Object.values(BASE_DELAYS).reduce((sum, delay) => sum + delay, 0);
}

// Generate workflow from executed tool calls
export function generateWorkflowFromExecution(
  query: string,
  toolCalls: ToolCall[],
  queryId: string
): Workflow {
  const allTools: WorkflowTool[] = [
    {
      name: "validate_destination",
      enabled: true,
      category: "exploratory",
      order: 1,
      description: "Validate the destination city"
    },
    {
      name: "check_weather",
      enabled: true,
      category: "exploratory",
      order: 2,
      description: "Check weather conditions"
    },
    {
      name: "get_exchange_rates",
      enabled: true,
      category: "exploratory",
      order: 3,
      description: "Get currency exchange rates"
    },
    {
      name: "calculate_travel_time",
      enabled: true,
      category: "exploratory",
      order: 4,
      description: "Calculate travel duration"
    },
    {
      name: "search_flights",
      enabled: true,
      category: "core",
      order: 5,
      description: "Search available flights"
    },
    {
      name: "check_hotel_availability",
      enabled: true,
      category: "exploratory",
      order: 6,
      description: "Check hotel availability"
    },
    {
      name: "estimate_budget",
      enabled: true,
      category: "core",
      order: 7,
      description: "Estimate total trip budget"
    },
    {
      name: "get_local_attractions",
      enabled: true,
      category: "exploratory",
      order: 8,
      description: "Get local attractions list"
    },
    {
      name: "create_itinerary",
      enabled: true,
      category: "core",
      order: 9,
      description: "Create trip itinerary"
    },
    {
      name: "finalize_trip",
      enabled: true,
      category: "core",
      order: 10,
      description: "Finalize trip details"
    }
  ];

  return {
    id: `workflow-${Date.now()}`,
    name: `Workflow for "${query.substring(0, 30)}${query.length > 30 ? '...' : ''}"`,
    queryPattern: query,
    tools: allTools,
    createdFrom: [queryId],
    timestamp: new Date(),
    isCustom: false,
    matchCount: 0
  };
}

// Mock memory storage with similarity search
export class MockMemoryStore {
  private memories: MemoryEntry[] = [];
  private performanceMetrics: PerformanceMetric[] = [];
  private workflows: Workflow[] = [];

  addMemory(query: string, context: string, executionTime: number): void {
    this.memories.push({
      id: `mem-${Date.now()}`,
      query,
      context,
      timestamp: new Date(),
      executionTime,
    });
  }

  addPerformanceMetric(metric: PerformanceMetric): void {
    this.performanceMetrics.push(metric);
  }

  findSimilar(query: string, threshold: number = 0.3): MemoryEntry[] {
    // Simple keyword-based similarity (mock)
    const queryWords = query.toLowerCase().split(/\s+/);

    return this.memories
      .map((mem) => {
        const memWords = mem.query.toLowerCase().split(/\s+/);
        const commonWords = queryWords.filter((word) =>
          memWords.includes(word)
        );
        const similarity = commonWords.length / Math.max(queryWords.length, memWords.length);

        return { ...mem, similarity };
      })
      .filter((mem) => mem.similarity && mem.similarity >= threshold)
      .sort((a, b) => (b.similarity || 0) - (a.similarity || 0))
      .slice(0, 5);
  }

  getAll(): MemoryEntry[] {
    return [...this.memories].reverse();
  }

  getPerformanceMetrics(): PerformanceMetric[] {
    return [...this.performanceMetrics];
  }

  getAverageTimeSaved(): number {
    const metrics = this.performanceMetrics.filter(m => m.usedMemory);
    if (metrics.length === 0) return 0;
    return metrics.reduce((sum, m) => sum + m.timeSaved, 0) / metrics.length;
  }

  getTotalTimeSaved(): number {
    return this.performanceMetrics
      .filter(m => m.usedMemory)
      .reduce((sum, m) => sum + m.timeSaved, 0);
  }

  // Workflow management methods
  addWorkflow(workflow: Workflow): void {
    this.workflows.push(workflow);
  }

  getAllWorkflows(): Workflow[] {
    return [...this.workflows].reverse().slice(0, 5); // Return max 5 most recent
  }

  findMatchingWorkflow(query: string, threshold: number = 0.6): Workflow | undefined {
    const queryWords = query.toLowerCase().split(/\s+/).filter(w => w.length > 2);

    let bestMatch: { workflow: Workflow; similarity: number } | undefined;

    for (const workflow of this.workflows) {
      const patternWords = workflow.queryPattern.toLowerCase().split(/\s+/).filter(w => w.length > 2);
      const commonWords = queryWords.filter(word => patternWords.includes(word));
      const similarity = commonWords.length / Math.max(queryWords.length, patternWords.length);

      if (similarity >= threshold && (!bestMatch || similarity > bestMatch.similarity)) {
        bestMatch = { workflow, similarity };
      }
    }

    return bestMatch?.workflow;
  }

  updateWorkflow(workflowId: string, updatedTools: WorkflowTool[]): void {
    const workflowIndex = this.workflows.findIndex(w => w.id === workflowId);
    if (workflowIndex !== -1) {
      this.workflows[workflowIndex].tools = updatedTools;
      this.workflows[workflowIndex].isCustom = true;
    }
  }

  incrementWorkflowMatchCount(workflowId: string): void {
    const workflow = this.workflows.find(w => w.id === workflowId);
    if (workflow) {
      workflow.matchCount++;
    }
  }
}
