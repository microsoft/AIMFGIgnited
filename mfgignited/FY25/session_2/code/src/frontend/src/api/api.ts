import { EventSourceMessage, fetchEventSource } from "@microsoft/fetch-event-source";

import { SearchConfig } from "../components/SearchSettings";

const sendChatApi = async (
    message: string,
    requestId: string,
    chatThread: Array<{ role: string; content: Array<{ text: string; type: string }> }>,
    config: SearchConfig,
    onMessage: (message: EventSourceMessage) => void,
    onError?: (err: unknown) => void,
    imageData?: string
) => {
    const endpoint = "/chat";

    await fetchEventSource(endpoint, {
        openWhenHidden: true,
        method: "POST",
        body: JSON.stringify({
            query: message,
            request_id: requestId,
            chatThread: chatThread,
            config,
            imageData
        }),
        onerror: onError,
        onmessage: onMessage
    });
};

const listIndexes = async () => {
    const response = await fetch(`/list_indexes`);

    return await response.json();
};

const getCitationDocument = async (fileName: string) => {
    const response = await fetch(`/get_citation_doc`, {
        method: "POST",
        body: JSON.stringify({ fileName })
    });

    return await response.json();
};

export { sendChatApi, listIndexes, getCitationDocument };
