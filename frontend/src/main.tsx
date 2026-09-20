import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import '@fontsource-variable/dm-sans';
import '@fontsource-variable/manrope';
import './styles.css';
const client = new QueryClient({
  defaultOptions: { queries: { staleTime: 20000, retry: 1, refetchOnWindowFocus: false } },
});
class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  render() {
    return this.state.error ? (
      <div className="empty">
        <h1>Let’s try that again.</h1>
        <p>Something unexpected happened. Your saved work is safe.</p>
        <button className="btn primary" onClick={() => location.reload()}>
          Reload SmartHire
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
ReactDOM.createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </ErrorBoundary>,
);
