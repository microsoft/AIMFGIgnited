import React from "react";

import { Button, Drawer, DrawerBody, DrawerHeader, DrawerHeaderTitle } from "@fluentui/react-components";
import { Dismiss20Regular } from "@fluentui/react-icons";

import { ProcessingStepsMessage } from "../api/models";
import "./ProcessingSteps.css";
import VerticalTimeline from "./VerticalTimeline";

interface Props {
    showProcessingSteps: boolean;
    processingStepMsg: Record<string, ProcessingStepsMessage[]>;
    toggleEditor: () => void;
}

const ProcessingSteps: React.FC<Props> = ({ processingStepMsg, showProcessingSteps: showProcessingSteps, toggleEditor }) => {
    return (
        <Drawer size="medium" position="end" separator open={showProcessingSteps} onOpenChange={toggleEditor}>
            <DrawerHeader>
                <DrawerHeaderTitle action={<Button appearance="subtle" aria-label="Close" icon={<Dismiss20Regular />} onClick={toggleEditor} />}>
                    Processing Steps
                </DrawerHeaderTitle>
            </DrawerHeader>

            <DrawerBody>
                <VerticalTimeline processingStepMsg={processingStepMsg} />
            </DrawerBody>
        </Drawer>
    );
};

export default ProcessingSteps;
