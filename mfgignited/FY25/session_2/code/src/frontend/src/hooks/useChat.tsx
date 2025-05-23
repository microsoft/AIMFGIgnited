import { useState, useEffect } from "react";
import { sendChatApi } from "../api/api";
import { Thread, ProcessingStepsMessage, Chat, ThreadType, RoleType } from "../api/models";
import { SearchConfig } from "../components/SearchSettings";

// Custom hook for managing chat state
export default function useChat(config: SearchConfig) {
    const [chatId, setChatId] = useState<string>();
    const [thread, setThread] = useState<Thread[]>([]);
    const [processingStepsMessage, setProcessingStepsMessage] = useState<Record<string, ProcessingStepsMessage[]>>({});
    const [chats, setChats] = useState<Record<string, Chat>>();
    const [isLoading, setIsLoading] = useState<boolean>(false);

    const refreshChats = async () => {
        setChats({});
    };
    const handleQuery = async (query: string, imageData?: string) => {
        setIsLoading(true);
        try {
            const request_id = new Date().getTime().toString();

            if (!chatId) setChatId(request_id);
            const chatThread = thread
                .filter(message => message.role === "user" || message.role === "assistant")
                .map(msg => ({
                    role: msg.role,
                    content: [
                        {
                            text: msg.role === "assistant" ? msg.answerPartial?.answer || "" : msg.message || "",
                            type: "text"
                        }
                    ]
                }));

            setThread(prevThread => {
                const newThread = [
                    ...prevThread,
                    {
                        request_id,
                        type: ThreadType.Message,
                        message: query,
                        role: RoleType.User,
                        imageData
                    }
                ];
                return newThread;
            });

            refreshChats();
            await sendChatApi(
                query,
                request_id,
                chatThread,
                config,
                message => {
                    if (message.event === "processing_step") {
                        setProcessingStepsMessage(steps => {
                            const newStep = JSON.parse(message.data);
                            const updatedSteps = { ...steps };
                            updatedSteps[newStep.request_id] = [...(steps[newStep.request_id] || []), newStep];
                            return updatedSteps;
                        });
                    } else if (message.event === "[END]") {
                        setIsLoading(false);
                    } else {
                        const data = JSON.parse(message.data);
                        data.type = message.event;

                        setThread(prevThread => {
                            const index = prevThread.findIndex(msg => msg.message_id === data.message_id);
                            const newThread = index !== -1 ? [...prevThread] : [...prevThread, data];
                            if (index !== -1) newThread[index] = data;

                            newThread.sort((a, b) => new Date(a.request_id).getTime() - new Date(b.request_id).getTime());
                            refreshChats();

                            return newThread;
                        });
                    }
                },
                err => {
                    console.error(err);
                    throw err;
                },
                imageData
            );
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    const onNewChat = () => {
        setChatId(undefined);
        setThread([]);
    };

    useEffect(() => {
        refreshChats();
    }, [config]);

    return { chatId, thread, processingStepsMessage, chats, isLoading, handleQuery, onNewChat };
}
