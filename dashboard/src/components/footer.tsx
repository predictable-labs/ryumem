"use client";

import { usePathname } from "next/navigation";

export function Footer() {
    const pathname = usePathname();

    if (pathname === "/login") return null;

    return (
        <footer className="border-t border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 mt-auto">
            <div className="container flex h-14 max-w-screen-2xl items-center justify-between">
                <p className="text-sm text-muted-foreground">
                    Powered by{" "}
                    <a
                        href="https://github.com/predictable-labs/ryumem"
                        className="font-medium underline underline-offset-4 hover:text-primary"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        Ryumem
                    </a>
                    .
                </p>
                <p className="text-xs text-muted-foreground">
                    &copy; {new Date().getFullYear()} Predictable Labs.
                </p>
            </div>
        </footer>
    );
}
