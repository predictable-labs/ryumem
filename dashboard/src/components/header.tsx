"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Brain, LogOut, Settings, Home } from "lucide-react";
import { api } from "@/lib/api";
import ThemeToggle from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export function Header() {
    const router = useRouter();
    const pathname = usePathname();
    const [customerId, setCustomerId] = useState<string>("");

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

    if (pathname === "/login") return null;

    const handleSignOut = () => {
        localStorage.removeItem("ryumem_api_key");
        router.push("/login");
    };

    return (
        <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-14 max-w-screen-2xl items-center">
                <div className="mr-4 flex">
                    <Link href="/" className="mr-6 flex items-center space-x-2">
                        <Brain className="h-6 w-6" />
                        <span className="hidden font-bold sm:inline-block">
                            RyuMem
                        </span>
                    </Link>
                    {customerId && (
                        <div className="hidden md:flex items-center text-sm text-muted-foreground">
                            <span className="mr-2">Customer:</span>
                            <code className="relative rounded bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm font-semibold">
                                {customerId}
                            </code>
                        </div>
                    )}
                </div>

                <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
                    <nav className="flex items-center gap-2">
                        <Button variant="ghost" asChild size="sm">
                            <Link href="/">
                                <Home className="mr-2 h-4 w-4" />
                                Home
                            </Link>
                        </Button>
                        <Button variant="ghost" asChild size="sm">
                            <Link href="/settings">
                                <Settings className="mr-2 h-4 w-4" />
                                Settings
                            </Link>
                        </Button>

                        <div className="mx-2 h-4 w-[1px] bg-border" />

                        <ThemeToggle />

                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleSignOut}
                            className="text-destructive hover:text-destructive hover:bg-destructive/10 dark:text-red-400 dark:bg-red-400/10 dark:hover:bg-red-400/20"
                        >
                            <LogOut className="mr-2 h-4 w-4" />
                            Sign Out
                        </Button>
                    </nav>
                </div>
            </div>
        </header>
    );
}
