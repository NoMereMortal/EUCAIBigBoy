#!/usr/bin/env node

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = process.env.PORT || 3000;
const BASE_DIR = '/app/out';

// MIME types for common file extensions
const MIME_TYPES = {
    '.html': 'text/html',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.txt': 'text/plain'
};

http.createServer((req, res) => {
    console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`);

    // Parse URL
    let pathname = url.parse(req.url).pathname;

    // Handle health checks
    if (pathname === '/health') {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end('OK');
        return;
    }

    // Normalize pathname
    if (pathname.endsWith('/')) {
        pathname += 'index.html';
    }

    // Determine the file path
    const filePath = path.join(BASE_DIR, pathname);

    // Special handling for env.js
    if (pathname === '/env.js') {
        console.log('Serving env.js with correct content type');
        fs.readFile(path.join(BASE_DIR, 'env.js'), (err, data) => {
            if (err) {
                console.error('Error reading env.js:', err);
                res.writeHead(500, { 'Content-Type': 'text/plain' });
                res.end('Error loading configuration');
                return;
            }
            // Force the correct content type for JavaScript
            res.writeHead(200, {
                'Content-Type': 'text/javascript',
                'Cache-Control': 'no-cache, no-store, must-revalidate'
            });
            res.end(data);
        });
        return;
    }

    // Read the file
    fs.readFile(filePath, (err, data) => {
        if (err) {
            if (err.code === 'ENOENT') {
                // If file not found, try serving index.html for SPA routing
                fs.readFile(path.join(BASE_DIR, 'index.html'), (indexErr, indexData) => {
                    if (indexErr) {
                        res.writeHead(404, { 'Content-Type': 'text/plain' });
                        res.end('404 Not Found');
                    } else {
                        res.writeHead(200, { 'Content-Type': 'text/html' });
                        res.end(indexData);
                    }
                });
            } else {
                // Server error
                res.writeHead(500, { 'Content-Type': 'text/plain' });
                res.end('500 Internal Server Error');
            }
            return;
        }

        // Get the file extension and determine content type
        const ext = path.extname(filePath).toLowerCase();
        const contentType = MIME_TYPES[ext] || 'application/octet-stream';

        // Send the response
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(data);
    });
}).listen(PORT, () => {
    console.log(`Static server running at http://localhost:${PORT}/`);
});
