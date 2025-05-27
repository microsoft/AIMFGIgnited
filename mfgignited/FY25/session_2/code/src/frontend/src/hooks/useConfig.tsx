import { useEffect, useState } from "react";
import { listIndexes } from "../api/api";
import { OpenAIAPIMode } from "../api/models";
import { SearchConfig } from "../components/SearchSettings";

export default function useConfig() {
    const [config, setConfig] = useState<SearchConfig>({
        use_semantic_ranker: true,
        chunk_count: 10,
        openai_api_mode: OpenAIAPIMode.ChatCompletions,
        use_streaming: true,
        use_knowledge_agent: false
    });

    const [indexes, setIndexes] = useState<string[]>([]);

    useEffect(() => {
        const fetchIndexes = async () => {
            const indexes = await listIndexes();
            setIndexes(indexes);
        };

        fetchIndexes();
    }, []);

    return { config, setConfig, indexes };
}
