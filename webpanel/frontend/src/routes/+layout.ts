/**
 * The panel is a client-side SPA served from a FastAPI backend that talks to
 * the browser's localStorage for auth. Disable SSR and prerendering so nothing
 * tries to call the API during the build.
 */
export const ssr = false;
export const prerender = false;
export const trailingSlash = 'never';
