/* 
  This Node.js proxy listens for WebSocket connections from your browser client.
  When a connection is established, it connects to the Azure endpoint using the API key
  in the request headers.
  Ensure you have a .env file with:
    AZURE_OPENAI_STT_TTS_KEY="your_api_key"
    AZURE_OPENAI_STT_TTS_ENDPOINT="https://your-azure-endpoint"
    PROXY_PORT=8080  (optional)
  To run:
    npm install ws dotenv
    node proxy.js
*/

const WebSocket = require('ws');
const http = require('http');
const url = require('url');
require('dotenv').config();

const PORT = process.env.PROXY_PORT || 8080;
const AZURE_ENDPOINT = process.env.AZURE_OPENAI_STT_TTS_ENDPOINT;
const API_KEY = process.env.AZURE_OPENAI_STT_TTS_KEY;

if (!AZURE_ENDPOINT || !API_KEY) {
    console.error('Azure endpoint or API key missing in .env');
    process.exit(1);
}

const server = http.createServer();
const wss = new WebSocket.Server({ server });

wss.on('connection', (clientWs, req) => {
    // Construct the Azure WebSocket URL without the API key in the URL.
    const azureWsUrl =
        AZURE_ENDPOINT.replace('https', 'wss') +
        '/openai/realtime?api-version=2025-04-01-preview&intent=transcription';

    // Connect to Azure with the API key sent as a header.
    const azureWs = new WebSocket(azureWsUrl, {
        headers: {
            'api-key': API_KEY,
        },
    });

    azureWs.on('open', () => {
        console.log('Connected to Azure speech service');
    });

    azureWs.on('message', (data) => {
        clientWs.send(data);
    });

    azureWs.on('close', (code, reason) => {
        console.log('Azure connection closed', code, reason);
        clientWs.close(code, reason);
    });

    azureWs.on('error', (error) => {
        console.error('Azure WebSocket error:', error);
        clientWs.close();
    });

    clientWs.on('message', (message) => {
        azureWs.send(message);
    });

    clientWs.on('close', (code, reason) => {
        console.log('Client connection closed', code, reason);
        azureWs.close();
    });

    clientWs.on('error', (error) => {
        console.error('Client WebSocket error:', error);
        azureWs.close();
    });
});

server.listen(PORT, () => {
    console.log(`Proxy server listening on port ${PORT}`);
});
