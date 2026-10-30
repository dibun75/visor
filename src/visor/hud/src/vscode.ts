export interface VsCodeApi {
  postMessage(message: unknown): void;
}

declare global {
  interface Window {
    INITIAL_VIEW_MODE?: 'sidebar' | 'panel';
    acquireVsCodeApi?: () => VsCodeApi;
    vscodeApiInstance?: VsCodeApi;
  }
}

export function getVsCode(): VsCodeApi | null {
  if (!window.vscodeApiInstance && window.acquireVsCodeApi) {
    window.vscodeApiInstance = window.acquireVsCodeApi();
  }
  return window.vscodeApiInstance ?? null;
}
