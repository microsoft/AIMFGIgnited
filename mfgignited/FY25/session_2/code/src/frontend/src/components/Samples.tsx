import React from "react";

import { Button } from "@fluentui/react-components";
import "./Samples.css";
import { Chat20Regular } from "@fluentui/react-icons";
import samplesData from "../content/samples.json";

interface Props {
    handleQuery: (q: string, isNew?: boolean) => void;
}

const newQuery = "New query...";

const Samples: React.FC<Props> = ({ handleQuery }) => {
    const samples: string[] = samplesData.queries;

    return (
        <div className="samples-container">
            <div className="samples-wrapper">
                {samples &&
                    samples.map((sample, index) => (
                        <Button
                            style={{ backgroundColor: "rgba(221, 217, 217, 0.8)" }}
                            size="large"
                            key={index}
                            onClick={() => handleQuery(sample, sample === newQuery)}
                            className="samples"
                            icon={<Chat20Regular alignmentBaseline="alphabetic" />}
                            iconPosition="after"
                        >
                            {sample}
                        </Button>
                    ))}
            </div>
        </div>
    );
};

export default Samples;
