import { Dispatch, SetStateAction, useState } from "react";

import { Button, Tooltip } from "@fluentui/react-components";
import { ChatAddRegular } from "@fluentui/react-icons";
import { Hamburger, NavDrawer, NavDrawerHeader, NavSectionHeader } from "@fluentui/react-nav-preview";

import { Chat } from "../api/models";
import "./NavBar.css";
import SearchSettings, { SearchConfig } from "./SearchSettings";

interface Props {
    config: SearchConfig;
    indexes: string[];
    chats: Chat[];
    onNewChat: () => void;
    setConfig: Dispatch<SetStateAction<SearchConfig>>;
}

export const NavBar = ({ setConfig, onNewChat, config }: Props) => {
    const [isOpen, setIsOpen] = useState(false);

    const getToolTipContent = () => {
        return isOpen ? "Close Settings" : "Open Settings";
    };

    return (
        <>
            <NavDrawer open={isOpen} type={"inline"} className="menu">
                <div className="menu-items">
                    <Button appearance="secondary" icon={<ChatAddRegular />} className="custom-menu-item new-chat" onClick={onNewChat}>
                        New Chat
                    </Button>
                    <div className="menu-item-settings">
                        <NavSectionHeader>Search Settings</NavSectionHeader>
                        <div className="custom-menu-item">
                            <SearchSettings config={config} setConfig={setConfig} />
                        </div>
                    </div>
                </div>
            </NavDrawer>
            <NavDrawerHeader style={{ width: "25px" }}>
                <Tooltip content={getToolTipContent()} relationship="label">
                    <Hamburger onClick={() => setIsOpen(!isOpen)} />
                </Tooltip>
            </NavDrawerHeader>
        </>
    );
};
