import { StrictMode } from "react";

import TimeAgo from "javascript-time-ago";
import en from "javascript-time-ago/locale/en";
import { createRoot } from "react-dom/client";

import App from "./page/App.tsx";

TimeAgo.addDefaultLocale(en);

export const Main = () => {
    return (
        <StrictMode>
            <App />
        </StrictMode>
    );
};

createRoot(document.getElementById("root")!).render(<Main />);
