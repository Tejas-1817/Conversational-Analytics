import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// Polyfill process.env for browser-bundled dependencies (e.g. react-draggable / react-grid-layout)
if (typeof (globalThis as any).process === 'undefined') {
  (globalThis as any).process = { env: {} };
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
