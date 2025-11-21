"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const apiKey = localStorage.getItem("ryumem_api_key");
        const isLoginPage = pathname === "/login";

        if (!apiKey && !isLoginPage) {
            router.push("/login");
        } else if (apiKey && isLoginPage) {
            router.push("/");
        } else {
            setIsAuthenticated(!!apiKey);
        }
        setIsLoading(false);
    }, [pathname, router]);

    // Prevent flash of protected content
    if (isLoading) {
        return null; // Or a loading spinner
    }

    // If not authenticated and not on login page, don't render anything (will redirect)
    if (!isAuthenticated && pathname !== "/login") {
        return null;
    }

    return <>{children}</>;
}
