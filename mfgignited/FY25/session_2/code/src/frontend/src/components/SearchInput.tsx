import React, { useState, useRef } from "react";

import { Button, Caption1, Spinner } from "@fluentui/react-components";
import { Search20Filled, Image20Regular, Dismiss12Regular } from "@fluentui/react-icons";

import "./SearchInput.css";
// import VoiceControl from "./VoiceControl";

interface SearchInputProps {
    isLoading: boolean;
    onSearch: (query: string, imageData?: string) => void;
}

const SearchInput: React.FC<SearchInputProps> = ({ isLoading, onSearch }) => {
    const [query, setQuery] = useState("");
    const [uploadedImage, setUploadedImage] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setQuery(e.target.value);
    };

    const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = event => {
                setUploadedImage(event.target?.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    const clearImage = () => {
        setUploadedImage(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const handleSearch = () => {
        if (query.trim() || uploadedImage) {
            onSearch(query.trim(), uploadedImage || undefined);
            setQuery("");
            setUploadedImage(null);
        }
    };

    // const handleTranscript = (text: string) => {
    //     setQuery(text);
    //     if (text.trim()) {
    //         onSearch(text.trim(), uploadedImage || undefined);
    //     }
    // };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            handleSearch();
        }
    };

    return (
        <>
            {isLoading && <div className="loading">Generating answer, please wait...</div>}

            {uploadedImage && (
                <div className="image-preview">
                    <img src={uploadedImage} alt="Uploaded" />
                    <Button appearance="subtle" icon={<Dismiss12Regular />} onClick={clearImage} title="Remove image" className="remove-image-btn" />
                </div>
            )}

            <div className="search-container" style={{ boxShadow: "0px 4px 6px rgba(0, 0, 0, 0.1)" }}>
                {/* <VoiceControl onTranscript={handleTranscript} responseText={null} isProcessing={isLoading} /> */}
                <input
                    disabled={isLoading}
                    className="input"
                    type="text"
                    placeholder="Ask about your equipment or upload an image..."
                    value={query}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                />
                <div className="search-controls">
                    <input
                        type="file"
                        id="image-upload"
                        ref={fileInputRef}
                        accept="image/*"
                        style={{ display: "none" }}
                        onChange={handleImageUpload}
                        disabled={isLoading}
                        aria-label="Upload image"
                        title="Upload image"
                    />
                    <Button
                        disabled={isLoading}
                        shape="circular"
                        size="medium"
                        appearance="subtle"
                        icon={<Image20Regular />}
                        onClick={() => fileInputRef.current?.click()}
                        title="Upload image"
                    />
                    <Button
                        disabled={isLoading}
                        shape="circular"
                        size="large"
                        appearance="primary"
                        icon={isLoading ? <Spinner size="extra-small" /> : <Search20Filled />}
                        onClick={handleSearch}
                    />
                </div>
            </div>
            <Caption1 style={{ marginTop: "5px", color: "lightgray" }} block align="center" italic>
                AI-generated content may be incorrect
            </Caption1>
        </>
    );
};

export default SearchInput;
