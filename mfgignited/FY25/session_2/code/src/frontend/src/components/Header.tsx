import { Divider, Switch, Title2 } from "@fluentui/react-components";
import { Wrench24Filled } from "@fluentui/react-icons";

import "./Header.css";

interface Props {
    toggleMode: (mode: boolean) => void;
    darkMode: boolean;
}

export const Header = ({ toggleMode, darkMode }: Props) => {
    return (
        <>
            <div className="header" style={{ backgroundColor: darkMode ? "#1a1a1a" : "#0078d4", color: "white", padding: "12px 20px" }}>
                <div style={{ display: "flex", alignItems: "center" }}>
                    <Wrench24Filled style={{ marginRight: "10px", color: "#ffffff" }} />
                    <Title2 style={{ color: "#ffffff", margin: 0 }}> Field Service Technician Assistant</Title2>
                </div>
                <div className="header-right">
                    <Switch
                        checked={darkMode}
                        label={`Dark Mode`}
                        onChange={() => {
                            toggleMode(!darkMode);
                        }}
                    />
                </div>
            </div>
            <Divider />
        </>
    );
};
