"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Brain, LogOut, Settings, Home, User } from "lucide-react";
import { api } from "@/lib/api";

export function Header() {
    const router = useRouter();
    const pathname = usePathname();
    const [customerId, setCustomerId] = useState<string>("");

    if (pathname === "/login") return null;

    useEffect(() => {
        const loadCustomerInfo = async () => {
            try {
                const customerInfo = await api.getCustomerMe().catch(() => null);
                if (customerInfo) {
                    setCustomerId(customerInfo.customer_id);
                }
            } catch (error) {
                console.error("Failed to load customer info:", error);
            }
        };

        loadCustomerInfo();
    }, []);

    const handleSignOut = () => {
        localStorage.removeItem("ryumem_api_key");
        router.push("/login");
    };

    return (
        <header className="bg-white border-b border-gray-200 dark:bg-slate-900 dark:border-slate-800 sticky top-0 z-50">
            <div className="container mx-auto px-6 py-4 max-w-7xl">
                <div className="flex items-center justify-between">
                    {/* Logo and Title */}
                    <div className="flex items-center gap-3">
                        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
                            <div className="p-2 bg-primary/10 rounded-lg">
                                <Brain className="h-6 w-6 text-primary" />
                            </div>
                            <div>
                                <h1 className="text-xl font-bold tracking-tight">RyuMem Dashboard</h1>
                                {customerId && (
                                    <p className="text-xs text-muted-foreground">
                                        Customer: <span className="font-medium text-primary">{customerId}</span>
                                    </p>
                                )}
                            </div>
                        </Link>
                    </div>

                    {/* Navigation */}
                    <nav className="flex items-center gap-4">
                        <Link
                            href="/"
                            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md transition-colors dark:text-gray-200 dark:hover:bg-slate-800"
                        >
                            <Home className="h-4 w-4" />
                            Home
                        </Link>

                        <Link
                            href="/settings"
                            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md transition-colors dark:text-gray-200 dark:hover:bg-slate-800"
                        >
                            <Settings className="h-4 w-4" />
                            Settings
                        </Link>

                        <div className="h-6 w-px bg-gray-200 dark:bg-slate-700 mx-2"></div>

                        <button
                            onClick={handleSignOut}
                            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-md transition-colors dark:text-red-400 dark:hover:bg-red-900/20"
                        >
                            <LogOut className="h-4 w-4" />
                            Sign Out
                        </button>
                    </nav>
                </div>
            </div>
        </header>
    );
}
