import { Caption1, FluentProvider } from "@fluentui/react-components";
import { Title1 } from "@fluentui/react-components";

import "./App.css";
import ChatContent from "../components/ChatContent";
import { Header } from "../components/Header";
import { NavBar } from "../components/NavBar";
import Samples from "../components/Samples";
import SearchInput from "../components/SearchInput";
import useChat from "../hooks/useChat";
import useConfig from "../hooks/useConfig";
import useTheme from "../hooks/useTheme";
import { IntroTitle } from "../api/defaults";
import { useState } from "react";

function App() {
    const { config, setConfig, indexes } = useConfig();
    const { thread, processingStepsMessage, chats, isLoading, handleQuery, onNewChat } = useChat(config);
    const { darkMode, setDarkMode, theme } = useTheme();
    const [newQ, setnewQ] = useState(false);

    return (
        <FluentProvider theme={theme}>
            <div className="container">
                <Header darkMode={darkMode} toggleMode={setDarkMode} />

                <div className="content-wrapper">
                    {thread.length || newQ ? (
                        <>
                            <NavBar config={config} indexes={indexes} setConfig={setConfig} onNewChat={onNewChat} chats={Object.values(chats || {})} />

                            <div className="content">
                                {thread.length ? <ChatContent thread={thread} processingStepMsg={processingStepsMessage} /> : <></>}
                                <div className="search-footer">
                                    <SearchInput onSearch={handleQuery} isLoading={isLoading} />
                                </div>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="intro-card">
                                <Title1 block align="center">
                                    {IntroTitle}
                                </Title1>
                                <br />
                                <Caption1 style={{ fontWeight: "bold" }} block align="center">
                                    How can I help you with field service tasks today?
                                </Caption1>
                                <Samples
                                    handleQuery={(q, isNew) => {
                                        if (isNew) {
                                            setnewQ(true);
                                        } else {
                                            handleQuery(q);
                                        }
                                    }}
                                />
                                <div className="search-footer">
                                    <div className="intro">
                                        <SearchInput onSearch={handleQuery} isLoading={isLoading} />
                                    </div>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </FluentProvider>
    );
}

export default App;
