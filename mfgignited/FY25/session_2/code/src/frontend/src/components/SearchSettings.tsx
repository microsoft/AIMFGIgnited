import React, { Dispatch, SetStateAction } from "react";

import { Label, Slider, SliderOnChangeData, InfoLabel, Switch, SwitchOnChangeData } from "@fluentui/react-components";

import { OpenAIAPIMode } from "../api/models";
import "./SearchSettings.css";

interface Props {
    config: SearchConfig;
    setConfig: Dispatch<SetStateAction<SearchConfig>>;
}

export interface SearchConfig {
    chunk_count: number;
    use_semantic_ranker: boolean;
    openai_api_mode: OpenAIAPIMode;
    use_streaming: boolean;
    use_knowledge_agent: boolean;
}

const SearchSettings: React.FC<Props> = ({ config, setConfig }) => {
    const handleSwitchChange = (key: keyof typeof config, checked: boolean) => {
        setConfig(prev => {
            const newConfig = { ...prev, [key]: checked } as SearchConfig;
            // When Knowledge Agent is enabled, Semantic Ranker must also be enabled
            if (key === "use_knowledge_agent" && checked) {
                newConfig.use_semantic_ranker = true;
            }
            return newConfig;
        });
    };

    const handleSliderChange = (key: keyof typeof config, value: number) => {
        setConfig(prev => ({
            ...prev,
            [key]: value
        }));
    };

    return (
        <div className="input-container">
            <div className="input-group">
                <Label htmlFor="ChunkCountSlider">Top chunks count [{config.chunk_count}]</Label>
                <Slider
                    id="chunkCountSlider"
                    className="weightSlider"
                    value={config.chunk_count}
                    onChange={(_: React.ChangeEvent<HTMLInputElement>, data: SliderOnChangeData) => handleSliderChange("chunk_count", data.value)}
                    min={5}
                    max={50}
                    step={5}
                />
            </div>

            <Switch
                id="useSemanticRankerSwitch"
                checked={config.use_semantic_ranker}
                disabled={config.use_knowledge_agent}
                onChange={(_, data: SwitchOnChangeData) => handleSwitchChange("use_semantic_ranker", data.checked)}
                label={
                    <InfoLabel
                        label={"Use semantic ranker"}
                        info={<>Enable semantic ranker for improved results especially if your data is indexed using image verbalization technique</>}
                    />
                }
            />
            <Switch
                id="useKnowledgeAgentSwitch"
                checked={config.use_knowledge_agent}
                onChange={(_, data: SwitchOnChangeData) => handleSwitchChange("use_knowledge_agent", data.checked)}
                label={<InfoLabel label={"Use Knowledge Agent"} info={<>Enable knowledge agent for grounding answers</>} />}
            />
            <Switch
                id="useStreamingSwitch"
                checked={config.use_streaming}
                onChange={(_, data: SwitchOnChangeData) => handleSwitchChange("use_streaming", data.checked)}
                label={"Use Streaming Response"}
            />
        </div>
    );
};

export default SearchSettings;
