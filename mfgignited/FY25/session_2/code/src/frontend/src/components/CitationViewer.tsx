import React, { useEffect, useState } from "react";

import { Button, Drawer, DrawerBody, DrawerFooter, DrawerHeader, DrawerHeaderTitle } from "@fluentui/react-components";
import { Dismiss20Regular } from "@fluentui/react-icons";

import { getCitationDocument } from "../api/api";
import { Citation } from "../api/models";
import "./CitationViewer.css";
import PdfHighlighter from "./PdfHighlighter";

interface Props {
    show: boolean;
    citation: Citation;
    toggle: () => void;
}

const CitationViewer: React.FC<Props> = ({ show, toggle, citation }) => {
    const [pdfPath, setPDFPath] = useState<string>("");

    useEffect(() => {
        getCitationDocument(citation.title).then(response => {
            setPDFPath(response);
        });
    }, [citation]);

    return (
        <Drawer size="medium" position="end" separator open={show} onOpenChange={toggle} style={{ maxWidth: "550px" }}>
            <DrawerHeader>
                <DrawerHeaderTitle action={<Button appearance="subtle" aria-label="Close" icon={<Dismiss20Regular />} onClick={toggle} />}>
                    Citation
                </DrawerHeaderTitle>
            </DrawerHeader>

            <DrawerBody>
                <div>
                    {pdfPath && (
                        <PdfHighlighter
                            pdfPath={pdfPath}
                            pageNumber={citation.locationMetadata.pageNumber}
                            boundingPolygons={citation.locationMetadata.boundingPolygons}
                        />
                    )}
                    {citation.text ? <p>{citation.text}</p> : null}
                </div>
            </DrawerBody>
            <DrawerFooter>
                <Button appearance="primary" onClick={toggle}>
                    Close
                </Button>
            </DrawerFooter>
        </Drawer>
    );
};

export default CitationViewer;
