"use client";

import { usePathname } from "next/navigation";

export function Footer() {
    const pathname = usePathname();

    if (pathname === "/login") return null;

    return (
        <footer className="bg-white border-t border-gray-200 dark:bg-slate-900 dark:border-slate-800 mt-auto">
            <div className="container mx-auto px-6 py-8 max-w-7xl">
                <div className="text-center text-sm text-muted-foreground">
                    <p>
                        Powered by{" "}
                        <a
                            href="https://github.com/predictable-labs/ryumem"
                            className="underline hover:text-primary font-medium"
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            Ryumem
                        </a>{" "}
                        - Memory layer for your agentic workflow.
                    </p>
                    <p className="mt-2 text-xs text-gray-400">
                        &copy; {new Date().getFullYear()} Predictable Labs. All rights reserved.
                    </p>
                </div>
            </div>
        </footer>
    );
}
