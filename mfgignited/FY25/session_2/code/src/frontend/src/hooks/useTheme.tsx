import { useState, useEffect } from "react";
import { Theme, createDarkTheme, createLightTheme, BrandVariants } from "@fluentui/react-components";

// Field service appropriate colors
const fieldServiceBrand: BrandVariants = {
    10: "#000810",
    20: "#001120",
    30: "#001a31",
    40: "#002241",
    50: "#002b52",
    60: "#003362",
    70: "#003c73",
    80: "#004583",
    90: "#004e94",
    100: "#0078d4", // Primary brand color - Field Service blue
    110: "#268ada",
    120: "#459ce0",
    130: "#61ade5",
    140: "#7cbdeb",
    150: "#96cef0",
    160: "#b0def5",
};

// Create custom themes for field service technicians
const fieldServiceLightTheme: Theme = createLightTheme(fieldServiceBrand);
const fieldServiceDarkTheme: Theme = createDarkTheme(fieldServiceBrand);

// Custom hook for managing theme
export default function useTheme() {
    const [darkMode, setDarkMode] = useState(() => {
        const savedTheme = localStorage.getItem('theme');
        return savedTheme ? savedTheme === 'dark' : 
            (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    });

    // Save theme preference to localStorage
    useEffect(() => {
        localStorage.setItem('theme', darkMode ? 'dark' : 'light');
    }, [darkMode]);

    // Return theme objects along with darkMode state
    return { 
        darkMode, 
        setDarkMode,
        theme: darkMode ? fieldServiceDarkTheme : fieldServiceLightTheme 
    };
}
