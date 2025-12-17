"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

    useEffect(() => {
        const apiKey = localStorage.getItem("ryumem_api_key");
        const isLoginPage = pathname === "/login";

        if (!apiKey && !isLoginPage) {
            // Not authenticated and not on login - redirect
            window.location.replace("/login");
            return;
        }

        if (apiKey && isLoginPage) {
            // Already authenticated but on login page - redirect to home
            window.location.replace("/");
            return;
        }

        // Set auth state
        setIsAuthenticated(!!apiKey);
    }, [pathname]);

    // Still checking auth - show nothing briefly
    if (isAuthenticated === null) {
        return null;
    }

    return <>{children}</>;
}
